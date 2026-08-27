import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from nftoken_core import parse_account_line, process_account

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_NAME = "LillysStore Netflix Checker"
WEBHOOK_PATH = "/webhook"
WELCOME_TEXT = (
    f"🎬 Welcome to {BOT_NAME} 🎬\n\n"
    "Send Netflix cookies and I'll reply with an NFToken login link.\n\n"
    "Supported formats:\n"
    "• NetflixId=...; SecureNetflixId=...\n"
    "• email:password:NetflixId=...; SecureNetflixId=...\n"
    "• email:password:country:NetflixId=...\n"
    "• JSON cookie export\n"
    "• .txt file with one or more accounts\n\n"
    "Commands:\n"
    "/start - Show this message\n"
    "/help - Usage help"
)

HELP_TEXT = (
    "How to use:\n\n"
    "1. Paste your cookie string in chat, or\n"
    "2. Send a .txt file with cookie lines\n\n"
    "Example:\n"
    "NetflixId=v%3D3%26ct%3D...; SecureNetflixId=v%3D3...\n\n"
    "The bot returns a https://netflix.com/?nftoken=... link when cookies are valid."
)

ptb_application: Application | None = None


def get_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set.")
        sys.exit(1)
    return token


def use_webhook_mode() -> bool:
    mode = os.environ.get("BOT_MODE", "").strip().lower()
    if mode == "polling":
        return False
    if mode == "webhook":
        return True
    return bool(os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL"))


def get_webhook_base_url() -> str:
    base = os.environ.get("WEBHOOK_URL") or os.environ.get("RENDER_EXTERNAL_URL") or ""
    return base.rstrip("/")


def build_application(token: str) -> Application:
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


def _process_lines(lines: list[str]) -> list[dict]:
    results = []
    for line in lines:
        parsed = parse_account_line(line)
        if parsed:
            results.append(process_account(parsed))
    return results


def _format_results(results: list[dict]) -> str:
    if not results:
        return "❌ Could not parse any valid cookie input.\n\nMake sure NetflixId is included."

    parts = []
    for index, result in enumerate(results, start=1):
        prefix = f"[{index}] " if len(results) > 1 else ""

        if result["status"] == "SUCCESS":
            parts.append(
                f"{prefix}✅ NFToken generated\n"
                f"🔗 {result['login_url']}\n"
                f"⏰ Expires: {result['expiry_str']}"
            )
        else:
            label = result["email"] or f"Line {index}"
            parts.append(f"{prefix}❌ {label}\nError: {result['error']}")

    return "\n\n".join(parts)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return

    status_msg = await update.message.reply_text("⏳ Generating NFToken link...")

    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        lines = [text]

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, _process_lines, lines)
    reply = _format_results(results)

    await status_msg.edit_text(reply)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    if not document:
        return

    filename = (document.file_name or "").lower()
    if not filename.endswith(".txt"):
        await update.message.reply_text("Please send a .txt file with cookie lines.")
        return

    status_msg = await update.message.reply_text("⏳ Reading file and generating links...")

    telegram_file = await document.get_file()
    raw_bytes = await telegram_file.download_as_bytearray()
    content = raw_bytes.decode("utf-8", errors="replace")

    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        await status_msg.edit_text("❌ The file is empty or has no valid lines.")
        return

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, _process_lines, lines)
    reply = _format_results(results)

    if len(reply) > 4000:
        reply = reply[:3990] + "\n...(truncated)"

    await status_msg.edit_text(reply)


def run_polling(token: str) -> None:
    application = build_application(token)
    logger.info("Starting %s in polling mode...", BOT_NAME)
    application.run_polling(drop_pending_updates=True)


def run_webhook_server(token: str) -> None:
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    global ptb_application

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global ptb_application
        ptb_application = build_application(token)
        await ptb_application.initialize()
        await ptb_application.start()

        base_url = get_webhook_base_url()
        if not base_url:
            logger.error("Set WEBHOOK_URL or deploy on Render (RENDER_EXTERNAL_URL).")
            sys.exit(1)

        webhook_url = f"{base_url}{WEBHOOK_PATH}"
        await ptb_application.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
        )
        logger.info("Webhook registered: %s", webhook_url)
        yield
        await ptb_application.bot.delete_webhook(drop_pending_updates=False)
        await ptb_application.stop()
        await ptb_application.shutdown()

    app = FastAPI(lifespan=lifespan)

    @app.get("/")
    async def health():
        return JSONResponse({"status": "ok", "bot": BOT_NAME})

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(request: Request):
        if ptb_application is None:
            return JSONResponse({"error": "bot not ready"}, status_code=503)

        data = await request.json()
        update = Update.de_json(data, ptb_application.bot)
        await ptb_application.process_update(update)
        return JSONResponse({"ok": True})

    port = int(os.environ.get("PORT", "10000"))
    logger.info("Starting %s webhook server on port %s...", BOT_NAME, port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def main() -> None:
    token = get_bot_token()
    if use_webhook_mode():
        run_webhook_server(token)
    else:
        run_polling(token)


if __name__ == "__main__":
    main()
