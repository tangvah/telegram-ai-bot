# Telegram AI Bot (24/7 on Railway, free-model-first)

Long-polling Telegram bot with a swappable OpenAI-compatible brain.
Starts on keyless free models; switch to Grok (or any provider) with env vars only.

## Run locally

```powershell
pip install -r requirements.txt
$env:BOT_TOKEN = "<token from @BotFather>"
python bot.py
```

Open Telegram, message your bot, send `/start`.

## Env vars

| Var | Required | Default | Notes |
| --- | --- | --- | --- |
| `BOT_TOKEN` | yes | — | From @BotFather. Never commit it. |
| `ADMIN_IDS` | for tools | empty (tools off) | Your numeric Telegram ID (`/whoami`). Enables `/py`, `/fetch` only for you |
| `MODEL_API_BASE` | no | `https://text.pollinations.ai/openai` | Any OpenAI-compatible chat endpoint |
| `MODEL_API_KEY` | no | empty | Bearer key when the endpoint needs one |
| `MODEL_NAME` | no | `openai` | Model id for the endpoint |
| `SYSTEM_PROMPT` | no | friendly assistant | Custom personality |
| `REQUEST_TIMEOUT` | no | `60` | Seconds per model call |

Switch to Grok later: set `MODEL_API_BASE=https://api.x.ai/v1`,
`MODEL_API_KEY=<xAI key>`, `MODEL_NAME=grok-...`. No code change.

## Deploy on Railway (24/7)

1. Push this folder to a GitHub repo.
2. Railway dashboard → **New → GitHub Repo** → pick the repo.
3. Add variable `BOT_TOKEN` (Service → Variables). Keep the free-model
   defaults, or set Grok vars above.
4. Ensure **1 replica** (Telegram polling allows exactly one poller per token).
5. Optional: set a usage limit (Workspace → Usage) so spend can never surprise you.
6. Deploy. Watch logs for `bot starting`, then `/start` your bot on Telegram.

Stop your local test copy before going live — two pollers with one token
fight each other and both error out.

## Action tools (owner-only)

- `/whoami` — anyone can use; shows their numeric Telegram ID.
- `/py <code>` — runs Python in the bot container (10s limit, output
  returned). Only IDs in `ADMIN_IDS`.
- `/fetch <url> [question]` — downloads a page and AI-summarizes it.
  Only IDs in `ADMIN_IDS`.
- Chat remembers the last few exchanges per conversation (`HISTORY_LEN`,
  default 8); `/reset` forgets.

To enable tools: message the bot `/whoami`, copy your ID, add Railway
variable `ADMIN_IDS=<your id>`. Never add strangers — `/py` is code
execution inside your container.
