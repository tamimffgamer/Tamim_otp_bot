import os
import asyncio
import logging
import aiohttp
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"

# Apnar OTP/notification group ID
OTP_GROUP_CHAT_ID = -1004436883235

# Apnar Telegram username
SUPPORT_USERNAME = "tmtamimmia"

# Mino SMS Base URL
MINO_BASE_URL = "https://minosms.com"

# Global application instance
application = None

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# ENV CHECK
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN paowa jayni. Render Environment Variables-e BOT_TOKEN din."
    )


# =========================================================
# TELEGRAM GROUP NOTIFICATION HELPER
# =========================================================

async def send_group_notification(text: str):
    """
    Telegram group-e notification pathanor function (Plain Text)।
    """
    try:
        if not application or not application.bot:
            logger.error("Bot instance not initialized yet.")
            return False

        await application.bot.send_message(
            chat_id=OTP_GROUP_CHAT_ID,
            text=text,
        )

        logger.info("Group notification sent successfully.")
        return True

    except Exception as e:
        logger.exception("Group notification failed: %s", e)
        return False


# =========================================================
# BACKGROUND OTP CHECKER (Mino SMS API Integration)
# =========================================================

async def check_mino_otp_loop():
    """
    Mino API theke active number ba OTP check korar background task.
    """
    await asyncio.sleep(10) # Bot start howar 10 second por cholbe
    while True:
        try:
            # Apni ekhane apnar target number ba active range diye check korte paren
            # Udahoron sस्वरूप: /check.php?api_key=...&number=...
            # Ekhane amra ekta example endpoint hit korchi
            async with aiohttp.ClientSession() as session:
                url = f"{MINO_BASE_URL}/check.php"
                params = {
                    "api_key": MINO_API_KEY,
                    "number": "+88017XXXXXXXX" # Ekhane apnar number ba range dite paren
                }
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Jodi kono notun message ba OTP ashe tahole group e pathabe
                        if data and "message" in data:
                            msg = data.get("message")
                            text = (
                                "📦 SMM NUMBER PANEL (Mino)\n"
                                "━━━━━━━━━━━━━━━━━━━\n"
                                f"✉️ Message :\n{msg}"
                            )
                            await send_group_notification(text)
        except Exception as e:
            logger.error("Mino API check error: %s", e)
        
        # Proti 30 second por por check korbe
        await asyncio.sleep(30)


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "Bot is running successfully with Mino API."


@flask_app.route("/health")
def health():
    return "OK"


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


# =========================================================
# TELEGRAM COMMANDS (/START, /ID, /TESTGROUP, /STATUS)
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    name = user.first_name if user else "User"

    text = (
        f"👋 Hello {name}!\n\n"
        "🤖 Bot is online.\n\n"
        "Available commands:\n"
        "🆔 /id - Apnar Telegram ID dekhun\n"
        "🧪 /testgroup - Group connection porikkha korun\n"
        "ℹ️ /status - Bot status dekhun"
    )

    await update.message.reply_text(text)


async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🆔 Telegram Information\n\n"
        f"User ID: {user_id}\n"
        f"Chat ID: {chat_id}"
    )

    await update.message.reply_text(text)


async def test_group_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text("⏳ Group connection porikkha korchi...")

    success = await send_group_notification(
        "🟢 Bot Group Test\n\n"
        "Telegram group connection successfully working."
    )

    if success:
        await update.message.reply_text("✅ Group test shofol hoyeche. Group-e notification pathano hoyeche.")
    else:
        await update.message.reply_text("❌ Group test byartho hoyeche. Render Logs dekhun.")


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    token_status = "✅ Set" if BOT_TOKEN else "❌ Missing"
    api_status = "✅ Set" if MINO_API_KEY else "❌ Missing"

    text = (
        "📊 Bot Status\n\n"
        f"🤖 BOT_TOKEN: {token_status}\n"
        f"🔑 MINO_API_KEY: {api_status}\n"
        f"👥 Group ID: {OTP_GROUP_CHAT_ID}\n"
        "🌐 Render server: ✅ Running"
    )

    await update.message.reply_text(text)


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.exception("Telegram error:", exc_info=context.error)


# =========================================================
# MAIN
# =========================================================

async def main():
    global application

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("testgroup", test_group_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_error_handler(error_handler)

    logger.info("Starting Telegram bot...")

    await application.initialize()
    await application.start()

    logger.info("Telegram bot started successfully.")

    # Background task shuru kora jate Mino API theke OTP check kora jay
    asyncio.create_task(check_mino_otp_loop())

    await application.updater.start_polling(drop_pending_updates=True)

    # Keep running
    while True:
        await asyncio.sleep(3600)


# =========================================================
# START EVERYTHING
# =========================================================

if __name__ == "__main__":
    # Render web server thread
    web_thread = Thread(
        target=run_web_server,
        daemon=True,
    )
    web_thread.start()
    logger.info("Render health server started.")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        raise
