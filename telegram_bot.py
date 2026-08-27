import asyncio
import logging
import os
import sys

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from core import parse_account_line, process_account

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_NAME = "LillysStore Netflix Checker"
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


def get_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set.")
        sys.exit(1)
    return token


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


def main() -> None:
    token = get_bot_token()
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Starting %s...", BOT_NAME)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
