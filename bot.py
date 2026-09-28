"""Telegram AI bot — long polling, OpenAI-compatible brain (free-first).

Env vars:
  BOT_TOKEN        Telegram token from @BotFather (required)
  MODEL_API_BASE   Chat-completions base URL (default: Pollinations, keyless)
  MODEL_API_KEY    Bearer key for the model API (optional, empty for Pollinations)
  MODEL_NAME       Model id (default: openai)
  SYSTEM_PROMPT    System prompt for the assistant
  REQUEST_TIMEOUT  Seconds for one model call (default: 60)
"""
import asyncio
import logging
import os

import requests
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("tg-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MODEL_API_BASE = os.environ.get("MODEL_API_BASE", "https://text.pollinations.ai/openai")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "openai")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "You are a helpful, friendly assistant chatting on Telegram. "
    "Keep replies concise unless asked for detail.",
)
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "60"))
TG_LIMIT = 4096


def ask_model(prompt: str) -> str:
    """Blocking call — run it in a thread so polling never stalls."""
    headers = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    resp = requests.post(
        f"{MODEL_API_BASE.rstrip('/')}/chat/completions",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! I'm online 24/7. Just send me any message and I'll answer.\n"
        "Commands: /start /help"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send any text and I'll reply with AI.\n"
        "/start — wake me up\n"
        "/help — this message"
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        reply = await asyncio.to_thread(ask_model, text)
    except Exception as exc:  # network / model errors -> friendly message, never crash
        log.warning("model call failed: %s", exc)
        await update.message.reply_text(
            "My brain is unreachable right now (free-tier hiccup). Try again in a bit."
        )
        return
    if len(reply) > TG_LIMIT:
        reply = reply[: TG_LIMIT - 1] + "…"
    await update.message.reply_text(reply)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.warning("update failed: %s", context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN env var is required.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_error_handler(on_error)
    log.info("bot starting (model=%s @ %s)", MODEL_NAME, MODEL_API_BASE)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
