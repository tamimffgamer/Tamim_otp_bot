import os
import asyncio
import requests
import re
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

def get_country_info(phone_number):
    clean_num = str(phone_number).replace("+", "").strip()
    if clean_num.startswith("880"): return "Bangladesh", "BD", "🇧🇩"
    elif clean_num.startswith("237"): return "Cameroon", "CM", "🇨🇲"
    elif clean_num.startswith("225"): return "Ivory Coast", "CI", "🇨🇮"
    elif clean_num.startswith("228"): return "Togo", "TG", "🇹🇬"
    elif clean_num.startswith("229"): return "Benin", "BJ", "🇧🇯"
    elif clean_num.startswith("255"): return "Tanzania", "TZ", "🇹🇿"
    elif clean_num.startswith("380"): return "Ukraine", "UA", "🇺🇦"
    elif clean_num.startswith("996"): return "Kyrgyzstan", "KG", "🇰🇬"
    else: return "Bangladesh", "BD", "🇧🇩"

def _sync_get_mino_real_number(target_range):
    headers = {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    clean_rid = str(target_range).upper().strip()
    payload = {"rid": clean_rid}
    try:
        res = requests.post(f"{BASE_API_URL}/getnumber.php", headers=headers, json=payload, timeout=2.0)
        if res.status_code == 200:
            res_data = res.json()
            data = res_data.get("data", {})
            phone = data.get("full_number") or data.get("national_number") or data.get("phone") or data.get("number")
            order_id = res_data.get("id") or data.get("id") or res_data.get("rid") or clean_rid
            if phone:
                return str(phone), str(order_id)
    except Exception as e:
        print(f"MINO API Error: {e}")
    return None, None

async def get_mino_real_number(target_range="88017XXX"):
    return await asyncio.to_thread(_sync_get_mino_real_number, target_range)

def _sync_fetch_live_traffic_detailed():
    headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
    service_data = {}
    total_hits = 0
    try:
        res = requests.get(f"{BASE_API_URL}/console.php", headers=headers, timeout=2.5)
        if res.status_code == 200:
            res_json = res.json()
            hits = (
                res_json.get("data", {}).get("hits", []) or 
                res_json.get("hits", []) or 
                res_json.get("data", []) or []
            )
            if isinstance(hits, list):
                total_hits = len(hits)
                for hit in hits:
                    if not isinstance(hit, dict): continue
                    r = hit.get("range") or hit.get("rid") or hit.get("number")
                    sid = str(hit.get("sid", "FACEBOOK")).upper().strip()
                    if r:
                        clean_r = str(r).strip()
                        c_name, c_code, c_flag = get_country_info(clean_r)
                        
                        if sid not in service_data:
                            service_data[sid] = {}
                        if c_code not in service_data[sid]:
                            service_data[sid][c_code] = {"name": c_name, "flag": c_flag, "ranges": {}}
                        
                        ranges_dict = service_data[sid][c_code]["ranges"]
                        if clean_r in ranges_dict:
                            ranges_dict[clean_r] += 1
                        else:
                            ranges_dict[clean_r] = 1
    except Exception as e:
        print(f"Detailed Traffic Error: {e}")
    return service_data, total_hits

async def fetch_live_traffic_detailed():
    return await asyncio.to_thread(_sync_fetch_live_traffic_detailed)

def _sync_check_mino_otp(target_phone):
    headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
    clean_target = ''.join(filter(str.isdigit, str(target_phone)))
    
    try:
        res = requests.get(f"{BASE_API_URL}/check.php?number={clean_target}", headers=headers, timeout=2.0)
        if res.status_code == 200:
            res_json = res.json()
            otps = res_json.get("data", {}).get("otps", []) or res_json.get("otps", []) or []
            if isinstance(otps, list):
                for otp_item in otps:
                    if not isinstance(otp_item, dict): continue
                    num_raw = str(otp_item.get("number", ""))
                    msg = str(otp_item.get("message", ""))
                    clean_num = ''.join(filter(str.isdigit, num_raw))
                    
                    if clean_target in clean_num or clean_num in clean_target:
                        match = re.search(r'\b\d{4,8}\b', msg)
                        if match:
                            return match.group(0)
                        elif msg:
                            return msg
    except Exception as e:
        print(f"OTP Check Error: {e}")
    return None

async def check_mino_otp(target_phone):
    return await asyncio.to_thread(_sync_check_mino_otp, target_phone)

async def auto_forward_console_logs(application):
    await asyncio.sleep(5)
    while True:
        try:
            headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
            def fetch_console_hits():
                try:
                    res = requests.get(f"{BASE_API_URL}/console.php", headers=headers, timeout=2)
                    if res.status_code == 200:
                        res_json = res.json()
                        return res_json.get("data", {}).get("hits", []) or []
                except Exception as ex:
                    print(f"Auto Forward Fetch Error: {ex}")
                return []

            hits = await asyncio.to_thread(fetch_console_hits)
            for hit in hits:
                if not isinstance(hit, dict): continue
                
                r = hit.get("range", "")
                sid = hit.get("sid", "FACEBOOK")
                msg = hit.get("message", "N/A")
                t_stamp = hit.get("time", "")
                
                unique_id = f"{r}_{t_stamp}_{msg}"
                if unique_id in SEEN_OTP_IDS:
                    continue
                
                SEEN_OTP_IDS.add(unique_id)
                if len(SEEN_OTP_IDS) > 500:
                    SEEN_OTP_IDS.clear()

                clean_num = str(r)
                if len(clean_num) > 6:
                    masked_num = clean_num[:6] + "X" * (len(clean_num) - 6)
                else:
                    masked_num = clean_num

                _, country_code, flag = get_country_info(str(r))
                
                log_text = (
                    f"<b>MINO SMS PANEL</b>                     <b>Admin</b>\n"
                    f"OTP                         Admin\n"
                    f"📘 <b>{sid} OTP RECEIVE</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"{flag} <b>Country :</b> {country_code}\n"
                    f"🎯 <b>Range :</b> <code>{masked_num}</code>\n"
                    f"🗣 <b>Language :</b> English\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"✉ <b>Message :</b>\n"
                    f"<code>{msg}</code>"
                )
                
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("NUMBER BOT ↗", url=f"https://t.me/{application.bot.username}")]
                ])
                
                try:
                    await application.bot.send_message(
                        chat_id=OTP_GROUP_CHAT_ID,
                        text=log_text,
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
                except Exception as send_err:
                    print(f"Telegram Send Error: {send_err}")
        except Exception as e:
            print(f"Auto Forward Error: {e}")
        
        await asyncio.sleep(2)

def create_number_markup(numbers_list):
    keyboard = []
    for num in numbers_list:
        _, _, flag = get_country_info(num)
        keyboard.append([InlineKeyboardButton(text=f"{flag} {num}", copy_text=CopyTextButton(text=num))])
    
    keyboard.append([
        InlineKeyboardButton("🔔 OTP GROUP", url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}"),
        InlineKeyboardButton("🔄 Change", callback_data="change_number")
    ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_home")])
    return InlineKeyboardMarkup(keyboard)

async def poll_for_otp(chat_id, user_id, phone, context):
    for _ in range(300): 
        await asyncio.sleep(1) 
        try:
            status = await check_mino_otp(phone)
            if status:
                current_bal = USER_BALANCES.get(user_id, 0.0)
                USER_BALANCES[user_id] = current_bal + 0.00122

                otp_message = f"🚨 <b>NEW OTP RECEIVED!</b> 🚨\n\n📱 <b>Number:</b> <code>{phone}</code>\n🔑 <b>OTP Code:</b> <code>{status}</code>\n💰 <b>Earned:</b> +$0.00122"
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=otp_message, 
                    parse_mode="HTML"
                )
                return
        except Exception as e:
            print(f"Polling Send Error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_STATES[user_id] = None
    reply_keyboard = [
        ["📞 Get API Number", "⚙ Set Range"],
        ["🟢 Live Traffic", "💳 Balance"],
        ["💬 Support", "📣 OTP Group"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text("Welcome to MINO SMS Number bot! 🤖\nPlease select an option from the menu below:", reply_markup=markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support_text = (
        "💬 <b>সাপোর্ট সেন্টার</b>\n\n"
        "যেকোনো সমস্যা বা প্রশ্ন থাকলে নিচের বাটনে ক্লিক করে সরাসরি আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন。\n\n"
        "⏰ দ্রুত সাড়া দেওয়া হবে ইনশাআল্লাহ。"
    )
    support_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 সাপোর্টে যোগাযোগ করুন", url=f"https://t.me/{SUPPORT_USERNAME}")]
    ])
    await update.message.reply_text(support_text, reply_markup=support_markup, parse_mode="HTML")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text("🔴 Invalid range! Please enter a valid number prefix (e.g. 88017XXX).")
        return
    elif state == "WAITING_FOR_BKASH":
        USER_STATES[user_id] = None
        USER_WITHDRAW_INFO[user_id] = f"bKash: {text.strip()}"
        await update.message.reply_text(f"✅ bKash number saved successfully: <code>{text.strip()}</code>", parse_mode="HTML")
        return
    elif state == "WAITING_FOR_BINANCE":
        USER_STATES[user_id] = None
        USER_WITHDRAW_INFO[user_id] = f"Binance ID: {text.strip()}"
        await update.message.reply_text(f"✅ Binance ID saved successfully: <code>{text.strip()}</code>", parse_mode="HTML")
        return

    if "Get API Number" in text:
        USER_STATES[user_id] = None
        wait_msg = await update.message.reply_text("⏳ Fetching real number from MINO panel, please wait...")
        user_range = USER_RANGES.get(user_id, "88017XXX")
        
        results = await asyncio.gather(
            get_mino_real_number(target_range=user_range),
            get_mino_real_number(target_range=user_range)
        )
        
        numbers = []
        for p, oid in results:
            if p and p not in numbers:
                numbers.append(p)

        try:
            await wait_msg.delete()
        except Exception:
            pass

        if not numbers:
            await update.message.reply_text(f"❌ <b>No Real Number Available!</b>\n\nPanel has no stock for range <code>{user_range}</code>.", parse_mode="HTML")
            return

        country_name, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag} {country_name}"
        
        reply_markup = create_number_markup(numbers)
        await update.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
        
        for p in numbers:
            asyncio.create_task(poll_for_otp(update.effective_chat.id, user_id, p, context))

    elif "Set Range" in text:
        USER_STATES[user_id] = "WAITING_FOR_RANGE"
        await update.message.reply_text("🔴 Please send your target number range (e.g. 88017XXX):")

    elif "Live Traffic" in text or "TRAFFIC" in text:
        USER_STATES[user_id] = None
        service_data, total_hits = await fetch_live_traffic_detailed()
        
        if not service_data:
            await update.message.reply_text("⚠️ No active traffic found right now.", parse_mode="HTML")
            return

        keyboard = []
        for sid in sorted(service_data.keys()):
            total_sid_otp = sum(sum(c_info["ranges"].values()) for c_info in service_data[sid].values())
            keyboard.append([InlineKeyboardButton(f"👀 Explore {sid.title()} Range ({total_sid_otp})", callback_data=f"tr_svc_{sid}")])
        
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="tr_refresh"), InlineKeyboardButton("❌ Close", callback_data="tr_close")])
        markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(f"📊 <b>Live Traffic Panel</b>\n📋 <b>Total OTP:</b> {total_hits}\nSelect a service below:", reply_markup=markup, parse_mode="HTML")

    elif "Balance" in text:
        USER_STATES[user_id] = None
        user_bal = USER_BALANCES.get(user_id, 0.0)
        saved_info = USER_WITHDRAW_INFO.get(user_id, "Not Set")
        
        balance_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw (bKash/Binance)", callback_data="withdraw_menu")],
            [InlineKeyboardButton("📱 Set bKash Number", callback_data="set_bkash"), InlineKeyboardButton("🔴 Set Binance ID", callback_data="set_binance")],
            [InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ])
        await update.message.reply_text(f"💳 <b>Your Balance:</b> ${user_bal:.5f}\n📂 <b>Payout Info:</b> {saved_info}\n\n📌 <i>Minimum withdraw is $1.00</i>", reply_markup=balance_markup, parse_mode="HTML")

    elif "Support" in text:
        USER_STATES[user_id] = None
        await help_command(update, context)

    elif "OTP Group" in text:
        USER_STATES[user_id] = None
        group_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📣 Join OTP Group ↗", url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}")]
        ])
        await update.message.reply_text("📣 Click the button below to join our official OTP Group:", reply_markup=group_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data == "change_number":
        await query.answer("🔄 Changing number...")
        user_range = USER_RANGES.get(user_id, "88017XXX")
        results = await asyncio.gather(
            get_mino_real_number(target_range=user_range),
            get_mino_real_number(target_range=user_range)
        )
        numbers = [p for p, _ in results if p]
        if not numbers: return
        country_name, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag} {country_name}"
        reply_markup = create_number_markup(numbers)
        try:
            await query.edit_message_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception: pass
        for p in numbers:
            asyncio.create_task(poll_for_otp(query.message.chat_id, user_id, p, context))

    elif data == "back_home":
        try: await query.message.delete()
        except Exception: pass
        await start(update, context)

    elif data.startswith("tr_svc_"):
        await query.answer()
        sid = data.replace("tr_svc_", "")
        service_data, _ = await fetch_live_traffic_detailed()
        if sid not in service_data:
            await query.answer("⚠️ No data available!", show_alert=True)
            return
        
        countries = service_data[sid]
        keyboard = []
        for c_code, c_info in sorted(countries.items(), key=lambda x: sum(x[1]["ranges"].values()), reverse=True):
            c_otp_count = sum(c_info["ranges"].values())
            keyboard.append([InlineKeyboardButton(f"{c_info['flag']} {c_info['name']} ({c_code}) - {c_otp_count} OTP", callback_data=f"tr_cnt_{sid}_{c_code}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="tr_main")])
        markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(f"👑 <b>Explore Service:</b> 🌐 {sid}\n\nSelect a country to view available ranges:", reply_markup=markup, parse_mode="HTML")
        except Exception: pass

    elif data.startswith("tr_cnt_"):
        await query.answer()
        parts = data.split("_")
        sid = parts[2]
        c_code = parts[3]
        
        service_data, _ = await fetch_live_traffic_detailed()
        if sid not in service_data or c_code not in service_data[sid]:
            await query.answer("⚠️ Data expired!", show_alert=True)
            return
        
        c_data = service_data[sid][c_code]
        ranges = c_data["ranges"]
        
        keyboard = []
        row = []
        sorted_ranges = sorted(ranges.items(), key=lambda x: x[1], reverse=True)
        for r_num, count in sorted_ranges:
            row.append(InlineKeyboardButton(f"🎛 {r_num} ({count})", copy_text=CopyTextButton(text=r_num)))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"tr_svc_{sid}")])
        markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(f"👑 <b>Ranges for</b> 🌐 {sid} - {c_data['flag']} <b>{c_code}</b>\n\nClick on any range to copy it.", reply_markup=markup, parse_mode="HTML")
        except Exception: pass

    elif data == "tr_main" or data == "tr_refresh":
        await query.answer("🔄 Refreshed!")
        service_data, total_hits = await fetch_live_traffic_detailed()
        keyboard = []
        for sid in sorted(service_data.keys()):
            total_sid_otp = sum(sum(c_info["ranges"].values()) for c_info in service_data[sid].values())
            keyboard.append([InlineKeyboardButton(f"👀 Explore {sid.title()} Range ({total_sid_otp})", callback_data=f"tr_svc_{sid}")])
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="tr_refresh"), InlineKeyboardButton("❌ Close", callback_data="tr_close")])
        markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(f"📊 <b>Live Traffic Panel</b>\n📋 <b>Total OTP:</b> {total_hits}\nSelect a service below:", reply_markup=markup, parse_mode="HTML")
        except Exception: pass

    elif data == "tr_close":
        try: await query.message.delete()
        except Exception: pass

    elif data == "set_bkash":
        USER_STATES[user_id] = "WAITING_FOR_BKASH"
        await query.message.reply_text("📲 Please send your bKash personal/agent number:")
        
    elif data == "set_binance":
        USER_STATES[user_id] = "WAITING_FOR_BINANCE"
        await query.message.reply_text("🔴 Please send your Binance Pay ID:")
        
    elif data == "withdraw_menu":
        user_bal = USER_BALANCES.get(user_id, 0.0)
        if user_bal < 1.0:
            await query.message.reply_text(f"❌ <b>Insufficient Balance!</b>\n\nYour balance is ${user_bal:.5f}. Minimum withdraw limit is <b>$1.00</b>.", parse_mode="HTML")
        else:
            saved_info = USER_WITHDRAW_INFO.get(user_id)
            if not saved_info:
                await query.message.reply_text("⚠️ Please set your bKash number or Binance ID first using the buttons in the Balance menu.")
            else:
                await query.message.reply_text(f"✅ <b>Withdraw Request Successful!</b>\n\nYour request for ${user_bal:.5f} to <b>{saved_info}</b> has been submitted to admin.")
                USER_BALANCES[user_id] = 0.0 

async def post_init(application):
    asyncio.create_task(auto_forward_console_logs(application))

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
        do_GET = lambda self, *a: (self.send_response(200), self.end_headers(), self.wfile.write(b"Bot is running!"))

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    app.run_polling()
