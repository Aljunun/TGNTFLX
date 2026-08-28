import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

try:
    from core import parse_account_line, process_account
except ImportError:
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


def _process_input(text: str) -> list[dict]:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        lines = [text.strip()]
    return _process_lines(lines)


def _results_to_json(results: list[dict]) -> dict:
    items = []
    for index, result in enumerate(results, start=1):
        items.append(
            {
                "index": index,
                "email": result.get("email") or "",
                "status": result["status"],
                "login_url": result.get("login_url"),
                "expiry": result.get("expiry_str"),
                "error": result.get("error"),
            }
        )
    return {
        "success": any(item["status"] == "SUCCESS" for item in items),
        "count": len(items),
        "results": items,
    }


def _check_api_key(provided_key: str | None) -> bool:
    required = os.environ.get("API_KEY", "").strip()
    if not required:
        return True
    return provided_key == required


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


def get_cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "https://netfdel.com",
        "https://www.netfdel.com",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def get_firebase_db_url() -> str:
    return os.environ.get(
        "FIREBASE_DATABASE_URL",
        "https://astro-782c4-default-rtdb.firebaseio.com",
    ).rstrip("/")


def fetch_rtdb(path: str):
    import requests as req

    url = f"{get_firebase_db_url()}/{path.lstrip('/')}.json"
    try:
        response = req.get(url, timeout=15)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception as exc:
        logger.warning("Firebase fetch failed for %s: %s", path, exc)
        return None


def get_env_fallback_accounts() -> list[str]:
    raw = os.environ.get("FALLBACK_ACCOUNTS", "").strip()
    if not raw:
        return []
    return [
        line.strip()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def collect_redeem_candidates(code: str) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []

    def add_account(data: str) -> None:
        cleaned = (data or "").strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            candidates.append(cleaned)

    voucher = fetch_rtdb(f"vouchers/{code.strip().upper()}")
    if isinstance(voucher, dict):
        add_account(voucher.get("data", ""))

    pool = fetch_rtdb("accountPool")
    if isinstance(pool, dict):
        for entry in pool.values():
            if isinstance(entry, dict):
                add_account(entry.get("data", ""))

    for line in get_env_fallback_accounts():
        add_account(line)

    return candidates


def extract_nftoken(login_url_or_token: str) -> str:
    value = (login_url_or_token or "").strip()
    marker = "nftoken="
    idx = value.find(marker)
    if idx != -1:
        return value[idx + len(marker) :]
    return value


DEVICE_PREFIXES = {
    "pc": "https://www.netflix.com/account?nftoken=",
    "phone": "https://www.netflix.com/unsupported?nftoken=",
    "tv": "https://www.netflix.com/tv9?nftoken=",
}


def build_device_link(login_url_or_token: str, device: str = "pc") -> str:
    token = extract_nftoken(login_url_or_token)
    if not token:
        return ""
    prefix = DEVICE_PREFIXES.get(device, DEVICE_PREFIXES["pc"])
    return prefix + token


def redeem_first_success(candidates: list[str]) -> dict | None:
    import random

    if not candidates:
        return None

    primary = candidates[0]
    rest = candidates[1:]
    random.shuffle(rest)
    ordered = [primary, *rest]

    for cookies in ordered:
        results = _process_input(cookies)
        for result in results:
            if result.get("status") == "SUCCESS" and result.get("login_url"):
                return result
    return None


def run_webhook_server(token: str) -> None:
    import uvicorn
    from fastapi import FastAPI, Header, HTTPException, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field

    global ptb_application

    class GenerateRequest(BaseModel):
        cookies: str = Field(..., min_length=1)

    class RedeemRequest(BaseModel):
        code: str = Field(..., min_length=1)
        device: str = Field(default="pc")

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

    app = FastAPI(title=BOT_NAME, lifespan=lifespan)
    cors_origins = get_cors_origins()
    logger.info("CORS allowed origins: %s", cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    async def run_generate(cookies: str) -> dict:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, _process_input, cookies)
        if not results:
            raise HTTPException(status_code=400, detail="Could not parse cookies. Include NetflixId=...")
        return _results_to_json(results)

    @app.get("/")
    async def health():
        return JSONResponse({
            "status": "ok",
            "bot": BOT_NAME,
            "api": {
                "get": "/api/generate?cookies=YOUR_COOKIES",
                "post": "/api/generate",
                "redeem": "/api/redeem",
            },
        })

    @app.get("/api/generate")
    async def api_generate_get(
        cookies: str | None = Query(None, description="Netflix cookie string"),
        input: str | None = Query(None, alias="input", description="Alias for cookies"),
        api_key: str | None = Query(None, alias="api_key"),
        x_api_key: str | None = Header(None, alias="X-API-Key"),
    ):
        if not _check_api_key(api_key or x_api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")

        cookie_text = cookies or input
        if not cookie_text or not cookie_text.strip():
            raise HTTPException(status_code=400, detail="Missing cookies query parameter")
        return await run_generate(cookie_text.strip())

    @app.post("/api/generate")
    async def api_generate_post(
        body: GenerateRequest,
        api_key: str | None = Query(None, alias="api_key"),
        x_api_key: str | None = Header(None, alias="X-API-Key"),
    ):
        if not _check_api_key(api_key or x_api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")
        return await run_generate(body.cookies.strip())

    @app.post("/api/redeem")
    async def api_redeem_post(
        body: RedeemRequest,
        api_key: str | None = Query(None, alias="api_key"),
        x_api_key: str | None = Header(None, alias="X-API-Key"),
    ):
        if not _check_api_key(api_key or x_api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")

        loop = asyncio.get_running_loop()
        candidates = await loop.run_in_executor(None, collect_redeem_candidates, body.code)
        if not candidates:
            raise HTTPException(status_code=404, detail="Invalid voucher code")

        result = await loop.run_in_executor(None, redeem_first_success, candidates)
        if not result:
            raise HTTPException(status_code=503, detail="No working account available")

        device = body.device if body.device in DEVICE_PREFIXES else "pc"
        login_url = build_device_link(result["login_url"], device)
        if not login_url:
            raise HTTPException(status_code=503, detail="No working account available")

        return JSONResponse(
            {
                "success": True,
                "login_url": login_url,
                "expiry": result.get("expiry_str"),
                "device": device,
                "attempted": len(candidates),
            }
        )

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(request: Request):
        if ptb_application is None:
            return JSONResponse({"error": "bot not ready"}, status_code=503)

        data = await request.json()
        update = Update.de_json(data, ptb_application.bot)
        await ptb_application.process_update(update)
        return JSONResponse({"ok": True})

    port = int(os.environ.get("PORT", "10000"))
    logger.info("Starting %s webhook + API server on port %s...", BOT_NAME, port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def main() -> None:
    token = get_bot_token()
    if use_webhook_mode():
        run_webhook_server(token)
    else:
        run_polling(token)


if __name__ == "__main__":
    main()
