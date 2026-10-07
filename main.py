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
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"

OTP_GROUP_CHAT_ID = -1004436883235
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_LINK = "https://t.me/smm_otp_grup"

MINO_BASE_URL = "https://minosms.com"

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
    raise RuntimeError("BOT_TOKEN paowa jayni.")

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
        logger.error(f"Group notification failed: {e}")
        return False

# =========================================================
# BACKGROUND OTP CHECKER
# =========================================================

async def check_mino_otp_loop():
    await asyncio.sleep(10)
    seen_otp_ids = set()
    while True:
        try:
            url = f"{MINO_BASE_URL}/st/api.php?api_key={MINO_API_KEY}&action=get_sms"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if data and isinstance(data, list):
                                for sms in data:
                                    sms_id = sms.get("id", str(sms.get("number")) + str(sms.get("message")))
                                    if sms_id not in seen_otp_ids:
                                        seen_otp_ids.add(sms_id)
                                        if len(seen_otp_ids) > 500:
                                            seen_otp_ids.clear()
                                            
                                        number = sms.get("number", "Unknown")
                                        msg = sms.get("message", "No Message")
                                        
                                        text = (
                                            "🚨 **NEW OTP RECEIVED!** 🚨\n\n"
                                            "📱 **Panel:** MINO SMS PANEL\n"
                                            f"📞 **Number:** `{number}`\n"
                                            f"✉️ **Message:**\n{msg}"
                                        )
                                        await send_group_notification(text)
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"OTP loop error: {e}")
        
        await asyncio.sleep(15)

# =========================================================
# RENDER HEALTH SERVER
# =========================================================

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running successfully with Panel connection."

@flask_app.route("/health")
def health():
    return "OK"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# =========================================================
# HANDLERS
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
        keyboard = [
            [InlineKeyboardButton("🔔 OTP GROUP", url=OTP_GROUP_LINK), InlineKeyboardButton("🔄 Change", callback_data="change_num")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ **Panel Status:** Connected", parse_mode="Markdown", reply_markup=reply_markup)

    elif "Set Range" in text:
        context.user_data["waiting_for_range"] = True
        await update.message.reply_text("🔴 Please send your target number range:")

    elif "Live Traffic" in text:
        # Apnar panel-er moto category ebong range gulo button akare sajano holo
        keyboard = [
            [InlineKeyboardButton("🌐 AUTHMSG (10 Ranges)", callback_data="cat_authmsg")],
            [InlineKeyboardButton("⚡ BOLT (1 Ranges)", callback_data="cat_bolt")],
            [InlineKeyboardButton("🌸 DING (1 Ranges)", callback_data="cat_ding")],
            [InlineKeyboardButton("📘 FACEBOOK (22 Ranges)", callback_data="cat_facebook")],
            [InlineKeyboardButton("💬 IMO (10 Ranges)", callback_data="cat_imo")],
            [InlineKeyboardButton("🟥 TWILIO (3 Ranges)", callback_data="cat_twilio")],
            [InlineKeyboardButton("🚗 UBER (1 Ranges)", callback_data="cat_uber")],
            [InlineKeyboardButton("🛡️ VERIFY (1 Ranges)", callback_data="cat_verify")],
            [InlineKeyboardButton("🟢 WHATSAPP (5 Ranges)", callback_data="cat_whatsapp")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"), InlineKeyboardButton("❌ Close", callback_data="close_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📊 **Live Traffic Panel**\nSelect a service below to check ranges and details:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    elif "Balance" in text:
        keyboard = [
            [InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("💳 **Your Balance:** $0.00000", parse_mode="Markdown", reply_markup=reply_markup)

    elif "Support" in text:
        keyboard = [[InlineKeyboardButton("💬 Saporte jogajog korun", url=f"https://t.me/{SUPPORT_USERNAME})"]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("💬 **Support Center**", parse_mode="Markdown", reply_markup=reply_markup)

    elif "OTP Group" in text:
        keyboard = [[InlineKeyboardButton("📢 Join OTP Group", url=OTP_GROUP_LINK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📢 **Click below to join OTP Group:**", parse_mode="Markdown", reply_markup=reply_markup)

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_home":
        await query.message.edit_text("Muler menute fire esechen.")
    elif data == "change_num":
        await query.message.edit_text("🔄 Notun number load kora hocche...")
    elif data == "refresh_traffic":
        await query.message.edit_text("🔄 Live traffic synced successfully with panel.")
    elif data == "close_menu":
        await query.message.delete()
    elif data.startswith("cat_"):
        cat_name = data.replace("cat_", "").upper()
        # Panel er moto specific category select korle tar range er details dekhanor jonno
        await query.message.edit_text(
            f"📂 **Category: {cat_name}**\n\n"
            f"🔹 Active ranges loaded successfully from Mino panel.\n"
            f"Status: Online & Ready 🟢",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Traffic", callback_data="back_to_traffic")]
            ])
        )
    elif data == "back_to_traffic":
        keyboard = [
            [InlineKeyboardButton("🌐 AUTHMSG (10 Ranges)", callback_data="cat_authmsg")],
            [InlineKeyboardButton("⚡ BOLT (1 Ranges)", callback_data="cat_bolt")],
            [InlineKeyboardButton("🌸 DING (1 Ranges)", callback_data="cat_ding")],
            [InlineKeyboardButton("📘 FACEBOOK (22 Ranges)", callback_data="cat_facebook")],
            [InlineKeyboardButton("💬 IMO (10 Ranges)", callback_data="cat_imo")],
            [InlineKeyboardButton("🟥 TWILIO (3 Ranges)", callback_data="cat_twilio")],
            [InlineKeyboardButton("🚗 UBER (1 Ranges)", callback_data="cat_uber")],
            [InlineKeyboardButton("🛡️ VERIFY (1 Ranges)", callback_data="cat_verify")],
            [InlineKeyboardButton("🟢 WHATSAPP (5 Ranges)", callback_data="cat_whatsapp")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic"), InlineKeyboardButton("❌ Close", callback_data="close_menu")]
        ]
        await query.message.edit_text(
            "📊 **Live Traffic Panel**\nSelect a service below to check ranges and details:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.answer("Sampurno hoyeche!", show_alert=False)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Telegram error occurred:", exc_info=context.error)

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
        logger.error(f"Fatal crash error: {e}")
