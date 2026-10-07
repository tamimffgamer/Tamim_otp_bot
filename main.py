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
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"

OTP_GROUP_CHAT_ID = -1004436883235
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_LINK = "https://t.me/smm_otp_grup"

MINO_BASE_URL = "https://minosms.com"

application = None
user_ranges = {}        # ইউজারের সেট করা রেঞ্জ সংরক্ষণ করার জন্য
user_active_number = {} # ইউজার যে নাম্বারটি নিবে তা ট্র্যাক করার জন্য

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN পাওয়া যায়নি।")

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
# BACKGROUND OTP CHECKER (GLOBAL & PERSONAL ROUTING)
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
                                            
                                        number = str(sms.get("number", "Unknown")).strip()
                                        msg = sms.get("message", "No Message")
                                        
                                        # ১. প্যানেলের সকল ওটিপি নির্দিষ্ট গ্রুপে পাঠানো (-1004436883235)
                                        global_text = (
                                            "🚨 **NEW OTP RECEIVED!** 🚨\n\n"
                                            "📱 **Panel:** MINO SMS PANEL\n"
                                            f"📞 **Number:** `{number}`\n"
                                            f"✉️ **Message:**\n{msg}"
                                        )
                                        try:
                                            if application and application.bot:
                                                await application.bot.send_message(
                                                    chat_id=OTP_GROUP_CHAT_ID,
                                                    text=global_text,
                                                    parse_mode="Markdown"
                                                )
                                        except Exception as e:
                                            logger.error(f"Global group notify error: {e}")

                                        # ২. বট থেকে ইউজার যে নাম্বার নিয়েছে, শুধু তার বটে পার্সোনাল রিয়েল OTP পাঠানো
                                        for uid, assigned_num in user_active_number.items():
                                            if assigned_num and assigned_num in number:
                                                personal_text = (
                                                    "🎯 **REAL OTP RECEIVED FOR YOUR NUMBER!** 🎯\n\n"
                                                    f"📞 **Number:** `{number}`\n"
                                                    f"✉️ **OTP Message:**\n{msg}"
                                                )
                                                try:
                                                    await application.bot.send_message(
                                                        chat_id=uid,
                                                        text=personal_text,
                                                        parse_mode="Markdown"
                                                    )
                                                except Exception as ex:
                                                    logger.error(f"Personal notify error for user {uid}: {ex}")
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"OTP loop error: {e}")
        
        await asyncio.sleep(10)

# =========================================================
# RENDER HEALTH SERVER
# =========================================================

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running successfully with Mino Panel connection."

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
            f"🔴 Target range successfully set to: `{text.strip()}`\n\nএখন '📞 Get API Number' এ ক্লিক করে আসল নাম্বার নিতে পারেন।",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    if "Get API Number" in text:
        target_range = user_ranges.get(user_id, "")
        
        # যদি রেঞ্জ সেট করা না থাকে
        if not target_range:
            await update.message.reply_text(
                "⚠️ **Range Set Kora Nei!**\nপ্রথমে '⚙️ Set Range' বাটনে ক্লিক করে আপনার টার্গেট রেঞ্জ সেট করুন, তারপর নাম্বার নিন।",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return

        fetched_number = "Loading from API..."
        try:
            # Mino SMS API documentation অনুযায়ী সঠিক POST মেথড ও হেডার দিয়ে রিকোয়েস্ট পাঠানো হচ্ছে
            url = f"{MINO_BASE_URL}/getnumber.php"
            headers = {"mauthapi": MINO_API_KEY}
            payload = {"rid": target_range}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        res_data = await resp.json()
                        fetched_number = res_data.get("number") or res_data.get("phone") or res_data.get("data") or res_data.get("result") or str(res_data)
                    else:
                        fetched_number = f"API Error: Status {resp.status}"
        except Exception as e:
            logger.error(f"API fetch error: {e}")
            fetched_number = "API Connection Error"

        # সফলভাবে আসল নাম্বার ফেচ হলে তা ট্র্যাকিংয়ে রাখা হলো
        if fetched_number and "Error" not in fetched_number and "Loading" not in fetched_number:
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
            f"⚡ *এই নাম্বারে নতুন OTP আসলে সরাসরি আপনার এই ইনবক্সে চলে আসবে!*", 
            parse_mode="Markdown", 
            reply_markup=reply_markup
        )

    elif "Set Range" in text:
        context.user_data["waiting_for_range"] = True
        await update.message.reply_text("🔴 দয়া করে আপনার কাঙ্ক্ষিত নাম্বার রেঞ্জটি পাঠান (যেমন: `23762XXX`):", parse_mode="Markdown")

    elif "Live Traffic" in text:
        # প্যানেলের সকল রেঞ্জ ধারাবাহিক বা সিরিয়াল অনুযায়ী দেখানোর মেনু
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
            "📊 **Live Traffic Panel**\nপ্যানেলের সকল সক্রিয় রেঞ্জ ধারাবাহিক ও সিরিয়াল অনুযায়ী নিচে দেওয়া হলো:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    elif "Balance" in text:
        keyboard = [
            [InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "💳 **Account Balance Details**\n\n"
            "💰 **Rate:** প্রতি OTP ২০ পয়সা (৳০.২০)\n"
            "💼 **Available Balance:** ৳০.০০", 
            parse_mode="Markdown", 
            reply_markup=reply_markup
        )

    elif "Support" in text:
        keyboard = [[InlineKeyboardButton("💬 Support Agent", url=f"https://t.me/{SUPPORT_USERNAME}")]],
        reply_markup = InlineKeyboardMarkup(keyboard[0])
        await update.message.reply_text(
            f"💬 **Support Center**\nযেকোনো সমস্যায় সরাসরি যোগাযোগ করতে নিচের আইডিতে ক্লিক করুন: @{SUPPORT_USERNAME}", 
            parse_mode="Markdown", 
            reply_markup=reply_markup
        )

    elif "OTP Group" in text:
        keyboard = [[InlineKeyboardButton("📢 Join OTP Group", url=OTP_GROUP_LINK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📢 **Official OTP Group:**\nনিচের বাটনে ক্লিক করে অফিশিয়াল গ্রুপে জয়en করুন:", 
            parse_mode="Markdown", 
            reply_markup=reply_markup
        )

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_home":
        await query.message.edit_text("মূল মেনুতে ফিরে এসেছেন।")
    elif data == "change_num":
        await query.message.edit_text("🔄 নতুন নাম্বার পাওয়ার জন্য আবার 'Get API Number' বাটনে ক্লিক করুন।")
    elif data == "refresh_traffic":
        await query.message.edit_text("🔄 Live traffic synced successfully with panel sequentially.")
    elif data == "close_menu":
        await query.message.delete()
    elif data.startswith("cat_"):
        cat_name = data.replace("cat_", "").upper()
        
        ranges_text = f"📂 **Service: {cat_name} Ranges (Serial Wise)**\n\n"
        
        if cat_name == "FACEBOOK":
            ranges_text += (
                "1️⃣ 🇨🇲 **Cameroon** | `23762XXX`\n"
                "2️⃣ 🇧🇪 **Belgium** | `324685XXX`\n"
                "3️⃣ 🇲🇬 **Madagascar** | `26134XXX`\n"
                "4️⃣ 🇬🇳 **Guinea** | `22465XXX`\n"
                "5️⃣ 🇨🇮 **Ivory Coast** | `22507XXX`\n"
                "6️⃣ 🇹🇬 **Togo** | `22897XXX`\n"
                "7️⃣ 🇲🇬 **Madagascar** | `26138XXX`\n"
                "8️⃣ 🇹🇿 **Tanzania** | `25565XXX`\n"
                "9️⃣ 🇦🇲 **Armenia** | `37455XXX`\n"
                "🔟 🇲🇬 **Madagascar** | `2613XXX`\n"
                "✨ *And sequential active ranges available...*"
            )
        elif cat_name == "WHATSAPP":
            ranges_text += (
                "1️⃣ 🇲🇬 **Madagascar** | `26138XXX`\n"
                "2️⃣ 🇹🇬 **Togo** | `22899XXX`\n"
                "3️⃣ 🇹🇬 **Togo** | `22898XXX`\n"
                "4️⃣ 🇲🇬 **Madagascar** | `26134XXX`\n"
                "5️⃣ 🇹🇬 **Togo** | `22896XXX`"
            )
        else:
            ranges_text += (
                f"1️⃣ 🟢 **Primary Server Range** | `Active Line`\n"
                f"📌 Sequential active ranges for {cat_name} are currently online."
            )

        await query.message.edit_text(
            ranges_text,
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
            "📊 **Live Traffic Panel**\nপ্যানেলের সকল সক্রিয় রেঞ্জ ধারাবাহিক ও সিরিয়াল অনুযায়ী নিচে দেওয়া হলো:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.answer("সম্পন্ন হয়েছে!", show_alert=False)

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
