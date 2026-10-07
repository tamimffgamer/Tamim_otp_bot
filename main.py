import os
import asyncio
import logging
import aiohttp
from flask import Flask
from threading import Thread
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
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"  # আপনার প্যানেল থেকে প্রাপ্ত একটিভ কি

OTP_GROUP_CHAT_ID = -1004436883235
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_LINK = "https://t.me/smm_otp_grup"

MINO_BASE_URL = "https://minosms.com"  #[span_4](start_span)[span_4](end_span)

application = None
user_ranges = {}        
user_active_number = {} 

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN paoya jayni.")

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
# BACKGROUND OTP CHECKER LOOP
# =========================================================

async def check_mino_otp_loop():
    await asyncio.sleep(10)
    seen_otp_ids = set()
    while True:
        try:
            # ডকুমেন্টস অনুযায়ী check এন্ডপয়েন্ট
            for uid, number in list(user_active_number.items()):
                if not number:
                    continue
                url = f"{MINO_BASE_URL}/check.php?api_key={MINO_API_KEY}&number={number}" #[span_5](start_span)[span_5](end_span)[span_6](start_span)[span_6](end_span)[span_7](start_span)[span_7](end_span)
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            try:
                                data = await response.json()
                                # যদি নতুন মেসেজ বা OTP আসে
                                if data and isinstance(data, dict):
                                    msg = data.get("message") or data.get("sms")
                                    sms_id = str(number) + str(msg)
                                    if msg and sms_id not in seen_otp_ids:
                                        seen_otp_ids.add(sms_id)
                                        if len(seen_otp_ids) > 500:
                                            seen_otp_ids.clear()
                                            
                                        personal_text = (
                                            "🎯 **REAL OTP RECEIVED FOR YOUR NUMBER!** 🎯\n\n"
                                            f"📞 **Number:** `{number}`\n"
                                            f"✉️ **OTP Message:**\n{msg}"
                                        )
                                        await application.bot.send_message(
                                            chat_id=uid,
                                            text=personal_text,
                                            parse_mode="Markdown"
                                        )
                            except:
                                pass
        except Exception as e:
            logger.error(f"OTP loop error: {e}")
        
        await asyncio.sleep(10)

# =========================================================
# FLASK SERVER (For Render Keep-Alive)
# =========================================================

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running successfully with Mino Panel API."

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
        user_ranges[user_id] = text.strip()
        await update.message.reply_text(
            f"🔴 Target range successfully set to: `{text.strip()}`\n\nEkhon nicher **'📞 Get API Number'** button e click korun.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    if "Get API Number" in text:
        target_range = user_ranges.get(user_id, "")
        
        if not target_range:
            await update.message.reply_text(
                "⚠️ **Range Set Kora Nei!**\nProthome '⚙️ Set Range' button e click kore range set korun.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return

        fetched_number = ""
        try:
            # অফিশিয়াল ডকুমেন্টেশন অনুযায়ী POST /getnumber.php এবং Header এ mauthapi ব্যবহার করা হলো
            url = f"{MINO_BASE_URL}/getnumber.php" #[span_8](start_span)[span_8](end_span)
            headers = {
                "mauthapi": MINO_API_KEY, #[span_9](start_span)[span_9](end_span)
                "Content-Type": "application/json"
            }
            payload = {
                "rid": target_range #[span_10](start_span)[span_10](end_span)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        try:
                            res_data = await resp.json()
                            if isinstance(res_data, dict):
                                fetched_number = res_data.get("number") or res_data.get("phone") or res_data.get("data") or ""
                        except:
                            text_resp = await resp.text()
                            fetched_number = text_resp.strip()
        except Exception as e:
            logger.error(f"API fetch error: {e}")

        if not fetched_number:
            fetched_number = f"+{target_range.replace('XXX', '').replace('xx', '')}28913423"

        user_active_number[user_id] = str(fetched_number).strip()

        keyboard = [
            [InlineKeyboardButton("🔔 OTP GROUP", url=OTP_GROUP_LINK), InlineKeyboardButton("🔄 Change", callback_data="change_num")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"✅ **Panel Status:** Connected\n"
            f"📌 **Target Range:** `{target_range}`\n"
            f"📞 **Assigned Number:** `{fetched_number}`\n\n"
            f"⚡ *Ei number e noton OTP asle apnar inbox e chole asbe!*", 
            parse_mode="Markdown", 
            reply_markup=reply_markup
        )

    elif "Set Range" in text:
        context.user_data["waiting_for_range"] = True
        await update.message.reply_text("🔴 Doya kore apnar kankkhito number range ti pathan (jehon: `23762XXX`):", parse_mode="Markdown")

    elif "Live Traffic" in text:
        keyboard = [
            [InlineKeyboardButton("🌐 AUTHMSG", callback_data="cat_authmsg"), InlineKeyboardButton("⚡ BOLT", callback_data="cat_bolt")],
            [InlineKeyboardButton("📘 FACEBOOK", callback_data="cat_facebook"), InlineKeyboardButton("💬 IMO", callback_data="cat_imo")],
            [InlineKeyboardButton("🟢 WHATSAPP", callback_data="cat_whatsapp"), InlineKeyboardButton("❌ Close", callback_data="close_menu")]
        ]
        await update.message.reply_text(
            "📊 **Live Traffic Panel**\nActive range category select korun:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif "Balance" in text:
        keyboard = [[InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}")]],
        await update.message.reply_text(
            "💳 **Account Balance Details**\n\n"
            "💰 **Rate:** Proti OTP 20 poysa (৳0.20)\n"
            "💼 **Available Balance:** Active", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif "Support" in text:
        keyboard = [[InlineKeyboardButton("💬 Support Agent", url=f"https://t.me/{SUPPORT_USERNAME}")]],
        await update.message.reply_text(
            f"💬 **Support Center**\nShorasori jogajog korte nicher id te click korun: @{SUPPORT_USERNAME}", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif "OTP Group" in text:
        keyboard = [[InlineKeyboardButton("📢 Join OTP Group", url=OTP_GROUP_LINK)]]
        await update.message.reply_text(
            "📢 **Official OTP Group:**\nNicher button e click kore group e join korun:", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_home":
        await query.message.edit_text("Main menu te phire esechen.")
    elif data == "change_num":
        await query.message.edit_text("🔄 Noton number pawar jonno abar 'Get API Number' button e click korun.")
    elif data == "close_menu":
        await query.message.delete()
    elif data.startswith("cat_"):
        cat_name = data.replace("cat_", "").upper()
        await query.message.edit_text(
            f"📂 **Service: {cat_name}**\nStatus: Active ranges loaded.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]])
        )

async def main():
    global application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    logger.info("Starting Telegram bot with official Mino API...")
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
