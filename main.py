import os
import asyncio
import logging
import aiohttp
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# =========================================================
# CONFIG (Panel Connected)
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"

# Group & Support Info
OTP_GROUP_CHAT_ID = -1004436883235
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_LINK = "https://t.me/smm_otp_grup"

# Mino SMS Base URL
MINO_BASE_URL = "https://minosms.com"

# Global application instance
application = None
user_ranges = {}

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN paowa jayni. Render Environment Variables-e BOT_TOKEN din.")


# =========================================================
# KEYBOARD
# =========================================================

def get_main_keyboard():
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
            return False
        await application.bot.send_message(
            chat_id=OTP_GROUP_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
        return True
    except Exception as e:
        logger.exception("Group notification failed: %s", e)
        return False


# =========================================================
# MINO PANEL API HELPERS
# =========================================================

async def fetch_panel_numbers():
    """Panel theke live numbers fetch korar function"""
    url = f"{MINO_BASE_URL}/st/api.php?api_key={MINO_API_KEY}&action=get_numbers"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
    except Exception as e:
        logger.error(f"Failed to fetch numbers from panel: {e}")
    return None


async def check_mino_otp_loop():
    """Background-e continuous panel theke OTP check korar loop"""
    await asyncio.sleep(5)
    while True:
        try:
            url = f"{MINO_BASE_URL}/st/api.php?api_key={MINO_API_KEY}&action=get_sms"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Jodi panel theke notun SMS/OTP ashe
                        if data and isinstance(data, list):
                            for sms in data:
                                number = sms.get("number", "Unknown")
                                msg = sms.get("message", "No Message")
                                text = (
                                    "🚨 **NEW OTP RECEIVED!** 🚨\n\n"
                                    "📱 **Panel:** MINO SMS PANEL\n"
                                    f"📞 **Number:** `{number}`\n"
                                    f"✉️ **Message:**\n{msg}"
                                )
                                await send_group_notification(text)
        except Exception as e:
            logger.error(f"OTP check loop error: {e}")
        
        await asyncio.sleep(15)


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is connected with Mino Panel and running successfully."

@flask_app.route("/health")
def health():
    return "OK"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# =========================================================
# HANDLERS & BUTTON LOGIC
# =========================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **Welcome to SMM NUMBER PANEL!**\n\n"
        "Connected with Mino Panel. Select an option below:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if context.user_data.get("waiting_for_range"):
        context.user_data["waiting_for_range"] = False
        user_ranges[user_id] = text
        await update.message.reply_text(
            f"🔴 Target range updated to: `{text}`",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    if "Get API Number" in text:
        # Panel theke live number ana ba default inline button dewa
        keyboard = [
            [InlineKeyboardButton("🌍 Fetch Live Number from Panel", callback_data="fetch_live_num")],
            [InlineKeyboardButton("🔔 OTP GROUP", url=OTP_GROUP_LINK), InlineKeyboardButton("🔄 Change", callback_data="change_num")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ **Panel Status:** Connected\nClick below to load numbers:", parse_mode="Markdown", reply_markup=reply_markup)

    elif "Set Range" in text:
        context.user_data["waiting_for_range"] = True
        await update.message.reply_text("🔴 Please send your target number range (e.g. 22896):")

    elif "Live Traffic" in text:
        keyboard = [
            [InlineKeyboardButton("👀 Check Active Traffic", callback_data="refresh_traffic")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"), InlineKeyboardButton("❌ Close", callback_data="close_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📊 **Live Traffic Panel (Mino)**\nConnected & Syncing live data...",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    elif "Balance" in text:
        keyboard = [
            [InlineKeyboardButton("💳 Withdraw (bKash/Binance)", callback_data="withdraw_menu")],
            [InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text_bal = (
            "💳 **Your Balance:** $0.00000\n"
            "📁 **Payout Info:** Not Set\n\n"
            "📌 Minimum withdraw is $1.00"
        )
        await update.message.reply_text(text_bal, parse_mode="Markdown", reply_markup=reply_markup)

    elif "Support" in text:
        keyboard = [[InlineKeyboardButton("💬 সাপোর্টে যোগাযোগ করুন", url=f"https://t.me/{SUPPORT_USERNAME}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text_sup = (
            "💬 **সাপোর্ট সেন্টার**\n\n"
            "যেকোনো সমস্যা বা প্রশ্ন থাকলে নিচের বাটনে ক্লিক করে সরাসরি আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন।"
        )
        await update.message.reply_text(text_sup, parse_mode="Markdown", reply_markup=reply_markup)

    elif "OTP Group" in text:
        keyboard = [[InlineKeyboardButton("📢 Join OTP Group", url=OTP_GROUP_LINK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📢 **Click the button below to join our official OTP Group:**", parse_mode="Markdown", reply_markup=reply_markup)


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_home":
        await query.message.edit_text("মূল মেনুতে ফিরে এসেছেন। নিচের বাটনগুলো ব্যবহার করুন।")
    elif data == "fetch_live_num":
        await query.message.edit_text("🔄 Connecting to Mino panel for live numbers...")
        numbers = await fetch_panel_numbers()
        if numbers:
            await query.message.edit_text(f"✅ Panel Response Received Successfully!\nData: {str(numbers)[:100]}...")
        else:
            await query.message.edit_text("⚠️ Panel theke data ana sombhob hoyni. API Key check korun.")
    elif data == "change_num":
        await query.message.edit_text("🔄 নতুন নাম্বার লোড করা হচ্ছে...")
    elif data == "refresh_traffic":
        await query.message.edit_text("🔄 Live traffic synced with Mino panel.")
    elif data == "close_menu":
        await query.message.delete()
    else:
        await query.answer("কার্যকর করা হয়েছে!", show_alert=False)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Telegram error:", exc_info=context.error)


# =========================================================
# MAIN
# =========================================================

async def main():
    global application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    application.add_error_handler(error_handler)

    logger.info("Starting Telegram bot connected with Mino panel...")
    await application.initialize()
    await application.start()

    # Background-e panel theke OTP check korar loop start kora holo
    asyncio.create_task(check_mino_otp_loop())

    await application.updater.start_polling(drop_pending_updates=True)

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        raise
