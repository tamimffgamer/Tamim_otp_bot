import os
import asyncio
import requests
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, CopyTextButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

MINO_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfc1d17"
BASE_API_URL = "https://minosms.com"
YOUR_TELEGRAM_USERNAME = "smm_otp_grup"
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_CHAT_ID = -1004436883235

USER_STATES = {}
USER_RANGES = {}
USER_BALANCES = {}  
USER_WITHDRAW_INFO = {} 
SEEN_OTP_IDS = set()
ACTIVE_USER_NUMBERS = {} 

def get_country_info(phone_number, api_country=""):
    clean_num = str(phone_number).replace("+", "").strip()
    if clean_num.startswith("880"): return "Bangladesh", "BD", "🇧🇩"
    elif clean_num.startswith("237"): return "Cameroon", "CM", "🇨🇲"
    elif clean_num.startswith("225"): return "Ivory Coast", "CI", "🇨🇮"
    elif clean_num.startswith("228"): return "Togo", "TG", "🇹🇬"
    elif clean_num.startswith("261"): return "Madagascar", "MG", "🇲🇬"
    else: return "International", "INT", "🌍"

def get_mino_real_number_sync(target_range):
    headers = {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    clean_rid = str(target_range).upper().strip()
    payload = {"rid": clean_rid}
    try:
        res = requests.post(f"{BASE_API_URL}/getnumber.php", headers=headers, json=payload, timeout=10.0)
        if res.status_code == 200:
            res_data = res.json()
            data = res_data.get("data", {})
            phone = data.get("full_number") or data.get("national_number") or data.get("phone") or data.get("number")
            if phone:
                return str(phone), str(clean_rid)
    except Exception as e:
        print(f"MINO API Error: {e}")
    return None, None

async def get_mino_real_number(target_range="23762XXX"):
    return await asyncio.to_thread(get_mino_real_number_sync, target_range)

def success_otp_sync(phone_number):
    headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
    clean_num = str(phone_number).strip()
    try:
        requests.get(f"{BASE_API_URL}/success_otp.php?api_key={MINO_API_KEY}&number={clean_num}", headers=headers, timeout=5.0)
    except:
        pass

async def success_otp(phone_number):
    await asyncio.to_thread(success_otp_sync, phone_number)

def check_number_status_sync(phone_number):
    headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
    clean_num = str(phone_number).strip().replace("+", "")
    try:
        url = f"{BASE_API_URL}/check.php?api_key={MINO_API_KEY}&number={clean_num}"
        res = requests.get(url, headers=headers, timeout=6.0)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Check API Error: {e}")
    return None

async def check_number_status(phone_number):
    return await asyncio.to_thread(check_number_status_sync, phone_number)

async def auto_forward_console_logs(application):
    print("Dedicated Per-Number Check Loop Started Successfully!")
    while True:
        try:
            current_time = time.time()
            
            for user_id, u_info in list(ACTIVE_USER_NUMBERS.items()):
                u_phone = str(u_info.get("phone", "")).strip()
                fetch_time = u_info.get("fetch_time", 0)
                
                if (current_time - fetch_time) > 1200:
                    continue

                if not u_phone: continue

                res_data = await check_number_status(u_phone)
                if not res_data: continue

                sms_data = res_data.get("data") or res_data.get("sms") or res_data.get("message") or res_data
                
                msg_text = ""
                if isinstance(sms_data, dict):
                    actual_sms = sms_data.get("full_sms") or sms_data.get("message") or sms_data.get("text") or ""
                    explicit_otp = sms_data.get("otp_code") or ""
                    
                    if explicit_otp and str(explicit_otp).strip():
                        msg_text = f"OTP: {explicit_otp}"
                    elif actual_sms and str(actual_sms).strip():
                        msg_text = actual_sms
                    else:
                        continue
                elif isinstance(sms_data, str):
                    msg_text = sms_data

                if not msg_text:
                    msg_text = res_data.get("message") or res_data.get("text") or ""

                s_s = str(msg_text).strip()
                if not s_s: continue
                if s_s.lower() in ["success", "completed", "waiting", "failed", "ok", "active"]:
                    continue

                matches = re.findall(r'\b\d{4,8}\b', s_s)
                otp_code = None
                for m in matches:
                    if not m.startswith("202") and not m.startswith("201"):
                        otp_code = m
                        break
                
                if not otp_code: continue

                sent_set = u_info.setdefault("sent_otps", set())
                if otp_code not in sent_set:
                    sent_set.add(otp_code)
                    current_bal = USER_BALANCES.get(user_id, 0.0)
                    USER_BALANCES[user_id] = current_bal + 0.00122

                    country_name, _, flag = get_country_info(u_phone)
                    
                    personal_text = (
                        f"🟢 <b>SUCCESSFUL OTP RECEIVED</b>\n\n"
                        f"🌐 <b>Service :</b> SMS\n"
                        f"🌍 <b>Country :</b> {country_name} ({flag})\n"
                        f"🎯 <b>Number :</b> <code>{u_phone}</code>\n"
                        f"🔑 <b>OTP Code :</b> <code>{otp_code}</code>\n\n"
                        f"✉ <b>Full Message :</b>\n<code>{s_s}</code>\n\n"
                        f"💰 <b>Earned :</b> +$0.00122"
                    )
                    personal_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton(text=f"📋 Copy OTP: {otp_code}", copy_text=CopyTextButton(text=otp_code))],
                        [InlineKeyboardButton("🔄 Change Number", callback_data="change_number")]
                    ])
                    try:
                        await application.bot.send_message(
                            chat_id=u_info["chat_id"], 
                            text=personal_text, 
                            reply_markup=personal_markup,
                            parse_mode="HTML"
                        )
                        await success_otp(u_phone)
                    except Exception as per_ex:
                        print(f"Personal Send Error: {per_ex}")

                    print(f"DEBUG: Trying to send OTP to Group ID: {OTP_GROUP_CHAT_ID}")
                    group_text = (
                        f"🟢 <b>SMS OTP RECEIVED</b>\n\n"
                        f"🌍 <b>Country :</b> {country_name} ({flag})\n"
                        f"🎯 <b>Number :</b> <code>{u_phone}</code>\n"
                        f"🔑 <b>Code :</b> <code>{otp_code}</code>\n\n"
                        f"✉ <b>Message :</b>\n<code>{s_s}</code>"
                    )
                    group_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton(text=f"📋 Copy OTP: {otp_code}", copy_text=CopyTextButton(text=otp_code))],
                        [InlineKeyboardButton("NUMBER BOT ↗", url=f"https://t.me/{application.bot.username}")]
                    ])
                    try:
                        await application.bot.send_message(
                            chat_id=OTP_GROUP_CHAT_ID, 
                            text=group_text, 
                            reply_markup=group_markup, 
                            parse_mode="HTML"
                        )
                        print("DEBUG: Group OTP sent successfully!")
                    except Exception as g_ex:
                        print(f"❌ DEBUG Group Send Error: {g_ex}")

        except Exception as e:
            print(f"Background Loop Error: {e}")
        
        await asyncio.sleep(2)

def create_single_number_markup(phone_num):
    _, _, flag = get_country_info(phone_num)
    keyboard = [
        [InlineKeyboardButton(text=f"{flag} {phone_num}", copy_text=CopyTextButton(text=phone_num))],
        [
            InlineKeyboardButton("🔔 OTP GROUP", url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}"),
            InlineKeyboardButton("🔄 Change", callback_data="change_number")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        USER_STATES[user_id] = None
        reply_keyboard = [
            ["📞 Get API Number", "⚙ Set Range"],
            ["🟢 Live Traffic", "💳 Balance"],
            ["💬 Support", "📣 OTP Group"]
        ]
        markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        await update.message.reply_text("Welcome to MINO SMS Number bot! 🤖\nPlease select an option from the menu below:", reply_markup=markup)
    except Exception as e:
        print(f"Start Error: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        support_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 সাপোর্টে যোগাযোগ করুন", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ])
        await update.message.reply_text("💬 <b>সাপোর্ট সেন্টার</b>\n\nযেকোনো সমস্যা থাকলে নিচের বাটনে যোগাযোগ করুন:", reply_markup=support_markup, parse_mode="HTML")
    except Exception as e:
        print(f"Help Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text or ""
        state = USER_STATES.get(user_id)

        if state == "WAITING_FOR_RANGE":
            clean_text = text.strip()
            if len(clean_text) >= 3:
                USER_STATES[user_id] = None
                USER_RANGES[user_id] = clean_text
                await update.message.reply_text(f"🔴 Target range updated to: <b>{clean_text}</b>", parse_mode="HTML")
            else:
                await update.message.reply_text("🔴 Invalid range! Please enter a valid number prefix.")
            return
        elif state == "WAITING_FOR_BKASH":
            USER_STATES[user_id] = None
            USER_WITHDRAW_INFO[user_id] = f"bKash: {text.strip()}"
            await update.message.reply_text(f"✅ bKash number saved: <code>{text.strip()}</code>", parse_mode="HTML")
            return
        elif state == "WAITING_FOR_BINANCE":
            USER_STATES[user_id] = None
            USER_WITHDRAW_INFO[user_id] = f"Binance ID: {text.strip()}"
            await update.message.reply_text(f"✅ Binance ID saved: <code>{text.strip()}</code>", parse_mode="HTML")
            return

        if "Get API Number" in text:
            USER_STATES[user_id] = None
            wait_msg = await update.message.reply_text("⏳ Fetching real number from MINO panel...")
            user_range = USER_RANGES.get(user_id, "23762XXX")
            
            phone, _ = await get_mino_real_number(target_range=user_range)
            try: await wait_msg.delete()
            except: pass

            if not phone:
                await update.message.reply_text(f"❌ No stock available for range <code>{user_range}</code>.", parse_mode="HTML")
                return

            ACTIVE_USER_NUMBERS[user_id] = {
                "phone": phone,
                "chat_id": update.effective_chat.id,
                "sent_otps": set(),
                "fetch_time": time.time()
            }

            country_name, _, flag = get_country_info(phone)
            header_text = f"✅ <b>Number:</b> {flag} {country_name}\n\nএই নাম্বারে কোড পাঠান। এটি পরবর্তী **২০ মিনিট** পর্যন্ত সক্রিয় থাকবে এবং এই সময়ের মধ্যে আসা সঠিক কোডটিই কেবল এখানে পাঠানো হবে!"
            reply_markup = create_single_number_markup(phone)
            await update.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")

        elif "Set Range" in text:
            USER_STATES[user_id] = "WAITING_FOR_RANGE"
            await update.message.reply_text("🔴 Please send your target number range (e.g. 23762XXX):")

        elif "Live Traffic" in text or "TRAFFIC" in text:
            USER_STATES[user_id] = None
            await update.message.reply_text("📊 Live traffic panel is active.", parse_mode="HTML")

        elif "Balance" in text:
            USER_STATES[user_id] = None
            user_bal = USER_BALANCES.get(user_id, 0.0)
            saved_info = USER_WITHDRAW_INFO.get(user_id, "Not Set")
            balance_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw_menu")],
                [InlineKeyboardButton("📱 Set bKash", callback_data="set_bkash"), InlineKeyboardButton("🔴 Set Binance", callback_data="set_binance")]
            ])
            await update.message.reply_text(f"💳 <b>Balance:</b> ${user_bal:.5f}\n📂 <b>Payout Info:</b> {saved_info}", reply_markup=balance_markup, parse_mode="HTML")

        elif "Support" in text: await help_command(update, context)
        elif "OTP Group" in text:
            group_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📣 Join OTP Group", url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}")]])
            await update.message.reply_text("📣 Join official OTP group:", reply_markup=group_markup)
    except Exception as e:
        print(f"Message Handler Error: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        data = query.data
        user_id = query.from_user.id

        if data == "back_home":
            try: await query.message.delete()
            except: pass
            await start(update, context)

        elif data == "change_number":
            await query.answer("🔄 Fetching new number...")
            user_range = USER_RANGES.get(user_id, "23762XXX")
            phone, _ = await get_mino_real_number(target_range=user_range)
            
            if not phone:
                await query.answer(f"❌ No stock available for range {user_range}.", show_alert=True)
                return

            ACTIVE_USER_NUMBERS[user_id] = {
                "phone": phone,
                "chat_id": query.message.chat_id,
                "sent_otps": set(),
                "fetch_time": time.time()
            }

            country_name, _, flag = get_country_info(phone)
            header_text = f"✅ <b>New Number:</b> {flag} {country_name}\n\nনতুন নাম্বারের ২০ মিনিটের সময়সীমা শুরু হয়েছে!"
            reply_markup = create_single_number_markup(phone)
            try:
                await query.edit_message_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
            except:
                await query.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")

        elif data == "set_bkash":
            USER_STATES[user_id] = "WAITING_FOR_BKASH"
            await query.message.reply_text("📲 Please send your bKash number:")
        elif data == "set_binance":
            USER_STATES[user_id] = "WAITING_FOR_BINANCE"
            await query.message.reply_text("🔴 Please send your Binance ID:")
        elif data == "withdraw_menu":
            user_bal = USER_BALANCES.get(user_id, 0.0)
            if user_bal < 1.0:
                await query.message.reply_text(f"❌ Minimum withdraw is $1.00. Current: ${user_bal:.5f}")
            else:
                await query.message.reply_text("✅ Withdraw request submitted successfully.")
                USER_BALANCES[user_id] = 0.0
    except Exception as e:
        print(f"Callback Error: {e}")

async def post_init(application):
    application.create_task(auto_forward_console_logs(application))

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
        do_HEAD = lambda s: s.do_GET()
        def do_GET(self, *a):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running!")

    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    app.run_polling(drop_pending_updates=True)
