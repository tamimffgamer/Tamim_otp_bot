import os
import asyncio
import logging
from threading import Thread
from flask import Flask
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
MINO_API_KEY = os.environ.get("MINO_API_KEY")

# আপনার OTP/notification group ID
OTP_GROUP_CHAT_ID = -1004436883235

# আপনার Telegram username
SUPPORT_USERNAME = "tmtamimmia"

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
        "BOT_TOKEN পাওয়া যায়নি। Render Environment Variables-এ BOT_TOKEN দিন।"
    )

if not MINO_API_KEY:
    logger.warning(
        "MINO_API_KEY পাওয়া যায়নি। Panel API-এর কাজগুলো বন্ধ থাকবে।"
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "Bot is running successfully."


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
# TELEGRAM GROUP TEST
# =========================================================

async def send_group_notification(text: str):
    """
    Telegram group-এ সাধারণ notification পাঠানোর function।
    OTP/verification code পাঠানোর জন্য নয়।
    """

    try:
        bot = application.bot

        await bot.send_message(
            chat_id=OTP_GROUP_CHAT_ID,
            text=text,
        )

        logger.info("Group notification sent successfully.")
        return True

    except Exception as e:
        logger.exception("Group notification failed: %s", e)
        return False


# =========================================================
# /START
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user
    chat = update.effective_chat

    name = user.first_name if user else "User"

    text = (
        f"👋 Hello {name}!\n\n"
        "🤖 Bot is online.\n\n"
        "Available commands:\n"
        "🆔 /id - আপনার Telegram ID দেখুন\n"
        "🧪 /testgroup - Group connection পরীক্ষা করুন\n"
        "ℹ️ /status - Bot status দেখুন"
    )

    await update.message.reply_text(text)


# =========================================================
# /ID
# =========================================================

async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🆔 Telegram Information\n\n"
        f"User ID: `{user_id}`\n"
        f"Chat ID: `{chat_id}`"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# =========================================================
# /TESTGROUP
# =========================================================

async def test_group_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "⏳ Group connection পরীক্ষা করছি..."
    )

    success = await send_group_notification(
        "🟢 Bot Group Test\n\n"
        "Telegram group connection successfully working."
    )

    if success:
        await update.message.reply_text(
            "✅ Group test সফল হয়েছে।\n\n"
            "গ্রুপে test notification পাঠানো হয়েছে।"
        )
    else:
        await update.message.reply_text(
            "❌ Group test ব্যর্থ হয়েছে।\n\n"
            "Render Logs দেখুন।"
        )


# =========================================================
# /STATUS
# =========================================================

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


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.exception(
        "Telegram error:",
        exc_info=context.error,
    )


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
    application.add_handler(
        CommandHandler("start", start_command)
    )

    application.add_handler(
        CommandHandler("id", id_command)
    )

    application.add_handler(
        CommandHandler("testgroup", test_group_command)
    )

    application.add_handler(
        CommandHandler("status", status_command)
    )

    application.add_error_handler(error_handler)

    logger.info("Starting Telegram bot...")

    # Start polling
    await application.initialize()
    await application.start()

    logger.info("Telegram bot started successfully.")

    await application.updater.start_polling(
        drop_pending_updates=True
    )

    # Keep running
    while True:
        await asyncio.sleep(3600)


# =========================================================
# START EVERYTHING
# =========================================================

if __name__ == "__main__":

    # Render web server
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
        logger.exception(
            "Fatal error: %s",
            e,
        )
        raise
