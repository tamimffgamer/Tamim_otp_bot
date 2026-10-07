import os
import asyncio
import logging
import urllib.request
import json
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"

# আপনার OTP/notification group ID
OTP_GROUP_CHAT_ID = -1004436883235

# আপনার Telegram username / Group link
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_LINK = "https://t.me/+YourGroupInviteLink" # আপনার গ্রুপের লিঙ্ক এখানে দিতে পারেন

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
# KEYBOARD HELPER
# =========================================================

def get_main_keyboard():
    """
    বটের নিচে যে বাটনগুলো দেখা যায় (Custom Reply Keyboard)
    """
    keyboard = [
        ["📞 Get API Number", "⚙️ Set Range"],
        ["🟢 Live Traffic", "💳 Balance"],
        ["💬 Support", "📢 OTP Group"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# =========================================================
# TELEGRAM GROUP NOTIFICATION HELPER
# =========================================================

async def send_group_notification(text: str):
    try:
        if not application or not application.bot:
            logger.error("Bot instance not initialized yet.")
            return False

        await application.bot.send_message(
            chat_id=OTP_GROUP_CHAT_ID,
            text=text,
        )
        return True
    except Exception as e:
        logger.exception("Group notification failed: %s", e)
        return False


# =========================================================
# BACKGROUND OTP CHECKER
# =========================================================

async def check_mino_otp_loop():
    await asyncio.sleep(10)
    while True:
        try:
            target_number = "+88017XXXXXXXX"
            url = f"{MINO_BASE_URL}/check.php?api_key={MINO_API_KEY}&number={target_number}"
            
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
        except Exception:
            pass
        
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
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# =========================================================
# TELEGRAM COMMANDS & BUTTON HANDLERS
# =========================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user else "User"

    text = (
        f"👋 Hello {name}!\n\n"
        "🤖 Bot is online.\n\n"
        "নিচের বাটনগুলো ব্যবহার করে আপনার প্যানেল নিয়ন্ত্রণ করুন:"
    )

    await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "Get API Number" in text:
        reply_text = (
            "📞 **API Number Info:**\n\n"
            f"আপনার API Key সক্রিয় আছে। Mino প্যানেল থেকে নাম্বার সংগ্রহ করতে ওয়েবসাইট ভিজিট করুন:\n"
            f"{MINO_BASE_URL}"
        )
        await update.message.reply_text(reply_text, parse_mode="Markdown")

    elif "Set Range" in text:
        reply_text = (
            "⚙️ **Set Range:**\n\n"
            "নাম্বার বা রেঞ্জ সেট করতে আপনার Mino প্যানেলের ড্যাশবোর্ড ব্যবহার করুন।"
        )
        await update.message.reply_text(reply_text, parse_mode="Markdown")

    elif "Live Traffic" in text:
        reply_text = (
            "🟢 **Live Traffic:**\n\n"
            "বর্তমানে প্যানেলের লাইভ ট্রাফিক দেখতে Mino ওয়েবসাইটে লগইন করুন।"
        )
        await update.message.reply_text(reply_text, parse_mode="Markdown")

    elif "Balance" in text:
        # এখানে চাইলে API থেকে রিয়েল ব্যালেন্স ফেচ করা যাবে
        reply_text = (
            "💳 **Account Balance:**\n\n"
            f"আপনার প্যানেল ব্যালেন্স দেখতে Mino প্যানেলে প্রবেশ করুন।"
        )
        await update.message.reply_text(reply_text, parse_mode="Markdown")

    elif "Support" in text:
        reply_text = (
            "💬 **Support:**\n\n"
            f"যেকোনো প্রয়োজনে যোগাযোগ করুন: @{SUPPORT_USERNAME}"
        )
        await update.message.reply_text(reply_text)

    elif "OTP Group" in text:
        reply_text = (
            "📢 **OTP Group:**\n\n"
            "সব OTP নোটিফিকেশন পেতে আমাদের অফিশিয়াল গ্রুপে যুক্ত থাকুন।"
        )
        await update.message.reply_text(reply_text)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = f"🆔 Telegram Information\n\nUser ID: {user_id}\nChat ID: {chat_id}"
    await update.message.reply_text(text)


async def test_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Group connection পরীক্ষা করছি...")
    success = await send_group_notification("🟢 Bot Group Test: Connection successfully working.")
    if success:
        await update.message.reply_text("✅ Group test সফল হয়েছে।")
    else:
        await update.message.reply_text("❌ Group test ব্যর্থ হয়েছে।")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token_status = "✅ Set" if BOT_TOKEN else "❌ Missing"
    api_status = "✅ Set" if MINO_API_KEY else "❌ Missing"
    text = (
        f"📊 Bot Status\n\nBOT_TOKEN: {token_status}\n"
        f"MINO_API_KEY: {api_status}\nGroup ID: {OTP_GROUP_CHAT_ID}"
    )
    await update.message.reply_text(text)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Telegram error:", exc_info=context.error)


# =========================================================
# MAIN
# =========================================================

async def main():
    global application

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands & Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("testgroup", test_group_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Text buttons handler (বাটনগুলোর লেখা ম্যাচ করার জন্য)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    application.add_error_handler(error_handler)

    logger.info("Starting Telegram bot...")
    await application.initialize()
    await application.start()

    asyncio.create_task(check_mino_otp_loop())

    await application.updater.start_polling(drop_pending_updates=True)

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("Render health server started.")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        raise
