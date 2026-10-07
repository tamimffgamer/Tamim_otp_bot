import os
import asyncio
import logging
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
MINO_API_KEY = os.environ.get("MINO_API_KEY")

# আপনার OTP/notification group ID
OTP_GROUP_CHAT_ID = -1004436883235

# আপনার Telegram username
SUPPORT_USERNAME = "tmtamimmia"

# আপনার Render Webhook URL
WEBHOOK_URL = "https://tamim-otp-bot.onrender.com/webhook/otp"

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

if not MINO_API_KEY:
    logger.warning(
        "MINO_API_KEY পাওয়া যায়নি। Panel API-এর কাজগুলো বন্ধ থাকবে।"
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
            parse_mode="Markdown"
        )

        logger.info("Group notification sent successfully.")
        return True

    except Exception as e:
        logger.exception("Group notification failed: %s", e)
        return False


# =========================================================
# RENDER HEALTH & WEBHOOK SERVER
# =========================================================

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return f"Bot is running successfully. Webhook is active at: {WEBHOOK_URL}"


@flask_app.route("/health")
def health():
    return "OK"


# প্যানেল থেকে OTP রিসিভ করার জন্য Webhook Endpoint
@flask_app.route("/webhook/otp", methods=["POST"])
def receive_otp():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400

        # প্যানেল থেকে পাঠানো ডেটা
        service_name = data.get("service", "OTP Service")
        country = data.get("country", "N/A")
        range_val = data.get("range", "N/A")
        message = data.get("message", "No message content")

        # গ্রুপে পাঠানোর জন্য সুন্দর ফরম্যাট তৈরি
        text = (
            f"📦 **SMM NUMBER PANEL**\n"
            f"Admin\n"
            f"OTP\t\t\tAdmin\n"
            f"📘 **{service_name}**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🇹🇯 Country : {country}\n"
            f"🎯 Range : {range_val}\n"
            f"🗣️ Language : English\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✉️ Message :\n{message}"
        )

        # Async function-টি Flask thread থেকে নিরাপদে চালানোর জন্য
        future = asyncio.run_coroutine_threadsafe(
            send_group_notification(text),
            application.loop
        )
        future.result(timeout=10)

        return jsonify({"status": "success", "message": "OTP sent to group"}), 200

    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


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
        f"User ID: `{user_id}`\n"
        f"Chat ID: `{chat_id}`"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


async def test_group_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text("⏳ Group connection পরীক্ষা করছি...")

    success = await send_group_notification(
        "🟢 **Bot Group Test**\n\n"
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
        f"🌐 Webhook URL: `{WEBHOOK_URL}`\n"
        "🌐 Render server & Webhook: ✅ Running"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


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
    logger.info("Render health & webhook server started.")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        raise
