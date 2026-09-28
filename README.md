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
