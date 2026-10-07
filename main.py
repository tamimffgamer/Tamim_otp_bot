import os
import asyncio
import logging
import urllib.request
import json
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
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"

# আপনার OTP/notification group ID
OTP_GROUP_CHAT_ID = -1004436883235

# আপনার Telegram username / Group link
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_LINK = "https://t.me/+YourGroupInviteLink"

# Mino SMS Base URL
MINO_BASE_URL = "https://minosms.com"

# Global application instance & User target ranges
application = None
user_ranges = {} # user_id -> range

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN পাওয়া যায়নি। Render Environment Variables-এ BOT_TOKEN দিন।")


# =========================================================
# KEYBOARDS
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
# BACKGROUND OTP CHECKER
# =========================================================

async def check_mino_otp_loop():
    await asyncio.sleep(10)
    while True:
        try:
            # ডিফল্ট বা সেভ করা রেঞ্জ দিয়ে চেক করা
            target_number = "+88017XXXXXXXX"
            url = f"{MINO_BASE_URL}/check.php?api_key={MINO_API_KEY}&number={target_number}"
            
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    if data and "message" in data:
                        msg = data.get("message")
                        text = (
                            "🚨 **NEW OTP RECEIVED!** 🚨\n\n"
                            "📱 **Admin / Panel:** SMM NUMBER PANEL\n"
                            "🌍 **Country:** CM (Cameroon)\n"
                            "🎯 **Range:** 23762XXX\n"
                            f"✉️ **Message:**\n{msg}"
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
    return "Bot is running successfully."

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
        "🤖 **Welcome to SMM NUMBER PANEL bot!**\n\n"
        "Please select an option from the menu below:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # যদি ব্যবহারকারী রেঞ্জ সেট করার মোডে থাকে
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
        keyboard = [
            [InlineKeyboardButton("🇹🇬 +22896325908", callback_data="copy_num_1")],
            [InlineKeyboardButton("🇹🇬 +22896495705", callback_data="copy_num_2")],
            [InlineKeyboardButton("🔔 OTP GROUP", url=OTP_GROUP_LINK), InlineKeyboardButton("🔄 Change", callback_data="change_num")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ **Number:** 🇹🇬 Togo", parse_mode="Markdown", reply_markup=reply_markup)

    elif "Set Range" in text:
        context.user_data["waiting_for_range"] = True
        await update.message.reply_text("🔴 Please send your target number range (e.g. 22896):")

    elif "Live Traffic" in text:
        keyboard = [
            [InlineKeyboardButton("👀 Explore Call Of Duty Range (1)", callback_data="tr_cod")],
            [InlineKeyboardButton("👀 Explore Facebook Range (86)", callback_data="tr_fb")],
            [InlineKeyboardButton("👀 Explore Imo Range (3)", callback_data="tr_imo")],
            [InlineKeyboardButton("👀 Explore Instagram Range (6)", callback_data="tr_insta")],
            [InlineKeyboardButton("👀 Explore Whatsapp Range (4)", callback_data="tr_wa")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"), InlineKeyboardButton("❌ Close", callback_data="close_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📊 **Live Traffic Panel**\nTotal OTP: 100\nSelect a service below:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    elif "Balance" in text:
        keyboard = [
            [InlineKeyboardButton("💳 Withdraw (bKash/Binance)", callback_data="withdraw_menu")],
            [InlineKeyboardButton("📱 Set bKash Number", callback_data="set_bkash"), InlineKeyboardButton("🔴 Set Binance ID", callback_data="set_binance")],
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
        keyboard = [[InlineKeyboardButton("💬 সাপোর্টে যোগাযোগ করুন", url=f"https://t.me/{SUPPORT_USERNAME})")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text_sup = (
            "💬 **সাপোর্ট সেন্টার**\n\n"
            "যেকোনো সমস্যা বা প্রশ্ন থাকলে নিচের বাটনে ক্লিক করে সরাসরি আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন।\n\n"
            "⏱️ দ্রুত সাড়া দেওয়া হবে ইনশাআল্লাহ।"
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
    elif data == "change_num":
        await query.message.edit_text("🔄 নতুন নাম্বার লোড করা হচ্ছে...")
    elif data == "refresh_traffic":
        await query.message.edit_text("🔄 Live traffic রিফ্রেশ করা হয়েছে।")
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
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        raise
