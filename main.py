import os
import asyncio
import logging
import urllib.request
import json
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

# আপনার OTP/notification group ID
OTP_GROUP_CHAT_ID = -1004436883235

# আপনার Telegram username
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
        "BOT_TOKEN পাওয়া যায়নি। Render Environment Variables-এ BOT_TOKEN দিন।"
    )


# =========================================================
# TELEGRAM GROUP NOTIFICATION HELPER
# =========================================================

async def send_group_notification(text: str):
    """
    Telegram group-এ notification পাঠানোর function।
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
# BACKGROUND OTP CHECKER (Using built-in urllib)
# =========================================================

async def check_mino_otp_loop():
    """
    Mino API থেকে active number বা OTP চেক করার background task।
    """
    await asyncio.sleep(10)
    while True:
        try:
            # এখানে আপনার নির্দিষ্ট নাম্বার বা রেঞ্জ বসাতে হবে
            target_number = "+88017XXXXXXXX"
            url = f"{MINO_BASE_URL}/check.php?api_key={MINO_API_KEY}&number={target_number}"
            
            # Request পাঠানো
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    if data and "message" in data:
                        msg = data.get("message")
                        text = (
                            "📦 SMM NUMBER PANEL (Mino)\n"
                            "━━━━━━━━━━━━━━━━━━━\n"
                            f"✉️ Message :\n{msg}"
                        )
                        await send_group_notification(text)
        except Exception as e:
            # যদি কোনো রেসপন্স না থাকে বা নাম্বার একটিভ না থাকে তবে লুপ থামবে না
            pass
        
        # প্রতি ৩০ সেকেন্ড পর পর চেক করবে
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
        "🆔 /id - আপনার Telegram ID দেখুন\n"
        "🧪 /testgroup - Group connection পরীক্ষা করুন\n"
        "ℹ️ /status - Bot status দেখুন"
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
    context: ContextTypes.DEFAULT_URL if 'DEFAULT_URL' in globals() else ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text("⏳ Group connection পরীক্ষা করছি...")

    success = await send_group_notification(
        "🟢 Bot Group Test\n\n"
        "Telegram group connection successfully working."
    )

    if success:
        await update.message.reply_text("✅ Group test সফল হয়েছে। গ্রুপে নোটিফিকেশন পাঠানো হয়েছে।")
    else:
        await update.message.reply_text("❌ Group test ব্যর্থ হয়েছে। Render Logs দেখুন।")


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

    # Background task শুরু করা
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
