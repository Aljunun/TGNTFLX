# Netflix NFToken Telegram Bot

Telegram bot that accepts Netflix cookies and returns NFToken login links.

## Folder contents (upload all of these to GitHub)

```
telegram-bot/
├── telegram_bot.py      # Bot entry point
├── nftoken_core.py      # Token generator engine
├── requirements.txt     # Python dependencies
├── render.yaml          # Render deploy config
├── runtime.txt          # Python version
├── .env.example         # Environment variable template
└── README.md
```

## Deploy on Render

1. Create a **new GitHub repo** and upload **everything inside this `telegram-bot` folder** (not the parent project).
2. Go to [render.com](https://render.com) → **New** → **Web Service**.
3. Connect your repo.
4. Render should auto-detect settings from `render.yaml`. If not, use:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python telegram_bot.py`
   - **Health check path:** `/`
5. Add environment variable:
   - `TELEGRAM_BOT_TOKEN` = your bot token from [@BotFather](https://t.me/BotFather)
6. Deploy.

## Run locally

```bash
pip install -r requirements.txt
set TELEGRAM_BOT_TOKEN=your_token_here
set BOT_MODE=polling
python telegram_bot.py
```

## Usage

Send cookies to the bot:

```
NetflixId=v%3D3%26ct%3D...; SecureNetflixId=v%3D3...
```

Or send a `.txt` file with multiple cookie lines.
