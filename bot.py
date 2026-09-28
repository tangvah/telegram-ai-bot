"""Telegram AI bot — long polling, OpenAI-compatible brain (free-first).

Chat + memory + owner-only action tools (/py, /fetch).

Env vars:
  BOT_TOKEN        Telegram token from @BotFather (required)
  ADMIN_IDS        Comma-separated Telegram numeric IDs allowed to use tools.
                   Get yours via /whoami. Empty = tools disabled for everyone.
  MODEL_API_BASE   Chat-completions base URL (default: Pollinations, keyless)
  MODEL_API_KEY    Bearer key for the model API (optional, empty for Pollinations)
  MODEL_NAME       Model id (default: openai)
  SYSTEM_PROMPT    System prompt for the assistant
  REQUEST_TIMEOUT  Seconds for one model call (default: 60)
  HISTORY_LEN      Remembered exchanges per chat (default: 8)
"""
import asyncio
import html
import logging
import os
import re
import subprocess
import sys
from collections import defaultdict, deque

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("tg-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = {
    x.strip() for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()
}
MODEL_API_BASE = os.environ.get("MODEL_API_BASE", "https://text.pollinations.ai/openai")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "openai")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "You are a helpful, friendly assistant chatting on Telegram. "
    "Keep replies concise unless asked for detail.",
)
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "60"))
HISTORY_LEN = int(os.environ.get("HISTORY_LEN", "8"))
TG_LIMIT = 4096

history: dict[int, deque] = defaultdict(lambda: deque(maxlen=HISTORY_LEN * 2))


def ask_model(messages: list[dict]) -> str:
    """Blocking call — run it in a thread so polling never stalls."""
    headers = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
    }
    resp = requests.post(
        f"{MODEL_API_BASE.rstrip('/')}/chat/completions",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def run_python(code: str, timeout: int = 10) -> str:
    """Run a snippet in a subprocess. Owner-only by routing, never public."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s (output discarded)."
    out = (proc.stdout or "") + (proc.stderr or "")
    out = out.strip() or "(no output)"
    if len(out) > 3000:
        out = out[:3000] + "\n…(truncated)"
    return f"exit={proc.returncode}\n{out}"


def fetch_page(url: str, timeout: int = 15, max_chars: int = 12000) -> str:
    """Download a page and reduce it to plain text for the model."""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "http://" + url
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; tg-bot/1.0)"},
        timeout=timeout,
    )
    resp.raise_for_status()
    content = resp.content[:400_000]
    text = content.decode(resp.encoding or "utf-8", errors="ignore")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)  # drop code/CSS
    text = re.sub(r"(?s)<[^>]+>", " ", text)  # drop tags
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:max_chars]


def is_admin(user_id: int) -> bool:
    return bool(ADMIN_IDS) and str(user_id) in ADMIN_IDS


def remember(chat_id: int, role: str, content: str) -> None:
    history[chat_id].append({"role": role, "content": content[:2000]})


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! I'm online 24/7.\n"
        "• Just chat — I remember this conversation.\n"
        "• /py <code> — run Python (owner only)\n"
        "• /fetch <url> [question] — read & summarize a page (owner only)\n"
        "• /reset — forget this chat • /whoami — show your Telegram ID"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Your Telegram ID: {user.id}\n"
        "Send it to the bot owner to unlock action tools."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    history.pop(update.effective_chat.id, None)
    await update.message.reply_text("Forgotten. Fresh start.")


async def py_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "Owner-only and not enabled for you. Send /whoami to the owner."
        )
        return
    code = update.message.text_partition(" ")[2].strip()
    if not code:
        await update.message.reply_text("Usage: /py print(2 + 2)")
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        result = await asyncio.to_thread(run_python, code)
    except Exception as exc:
        result = f"Runner error: {exc}"
    if len(result) > TG_LIMIT:
        result = result[: TG_LIMIT - 1] + "…"
    await update.message.reply_text(f"```\n{result}\n```")


async def fetch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "Owner-only and not enabled for you. Send /whoami to the owner."
        )
        return
    args = (update.message.text_partition(" ")[2] or "").split(None, 1)
    if not args:
        await update.message.reply_text("Usage: /fetch <url> [what to find]")
        return
    url, question = args[0], (args[1] if len(args) > 1 else "Summarize this page.")
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        page = await asyncio.to_thread(fetch_page, url)
        answer = await asyncio.to_thread(
            ask_model,
            [
                {
                    "role": "user",
                    "content": f"Page content:\n{page}\n\nTask: {question}",
                }
            ],
        )
    except Exception as exc:
        log.warning("fetch failed: %s", exc)
        await update.message.reply_text(f"Couldn't read that page: {exc}")
        return
    if len(answer) > TG_LIMIT:
        answer = answer[: TG_LIMIT - 1] + "…"
    await update.message.reply_text(answer)


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return
    chat_id = update.effective_chat.id
    await update.message.chat.send_action(ChatAction.TYPING)
    messages = [*history[chat_id], {"role": "user", "content": text}]
    try:
        reply = await asyncio.to_thread(ask_model, messages)
    except Exception as exc:
        log.warning("model call failed: %s", exc)
        await update.message.reply_text(
            "My brain is unreachable right now (free-tier hiccup). Try again in a bit."
        )
        return
    remember(chat_id, "user", text)
    remember(chat_id, "assistant", reply)
    if len(reply) > TG_LIMIT:
        reply = reply[: TG_LIMIT - 1] + "…"
    await update.message.reply_text(reply)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.warning("update failed: %s", context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN env var is required.")
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS empty — /py and /fetch disabled for everyone.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("py", py_cmd))
    app.add_handler(CommandHandler("fetch", fetch_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_error_handler(on_error)
    log.info("bot starting (model=%s @ %s)", MODEL_NAME, MODEL_API_BASE)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
