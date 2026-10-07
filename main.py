import os
import asyncio
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, CopyTextButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN_2") or os.environ.get("BOT_TOKEN")

PANEL_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"
BASE_API_URL = "https://minosms.com"
YOUR_TELEGRAM_USERNAME = "smm_otp_grup"
SUPPORT_USERNAME = "smmsaport"
OTP_GROUP_CHAT_ID = -1004436883235

USER_STATES = {}
USER_RANGES = {}
USER_BALANCES = {}  
USER_WITHDRAW_INFO = {} 
SEEN_OTP_IDS = set()

def get_country_info(phone_number):
    clean_num = str(phone_number).replace("+", "").strip()
    if clean_num.startswith("224"): return "Guinea", "GN", "🇬🇳"
    elif clean_num.startswith("237"): return "Cameroon", "CM", "🇨🇲"
    elif clean_num.startswith("261"): return "Madagascar", "MG", "🇲🇬"
    elif clean_num.startswith("255"): return "Tanzania", "TZ", "🇹🇿"
    elif clean_num.startswith("228"): return "Togo", "TG", "🇹🇬"
    elif clean_num.startswith("374"): return "Armenia", "AM", "🇦🇲"
    elif clean_num.startswith("992"): return "Tajikistan", "TJ", "🇹🇯"
    elif clean_num.startswith("1809") or clean_num.startswith("1829"): return "Dominican Republic", "DO", "🇩🇴"
    elif clean_num.startswith("49"): return "Germany", "DE", "🇩🇪"
    else: return "Togo", "TG", "🇹🇬"

def _sync_get_panel_ranges():
    headers = {"mauthapi": PANEL_API_KEY, "Accept": "application/json"}
    try:
        res = requests.get(f"{BASE_API_URL}/console.php?api_key={PANEL_API_KEY}", headers=headers, timeout=3)
        if res.status_code != 200:
            res = requests.get(f"{BASE_API_URL}/console", headers=headers, timeout=3)
        if res.status_code == 200:
            res_json = res.json()
            hits = res_json if isinstance(res_json, list) else (res_json.get("data", {}).get("hits", []) or res_json.get("data", []) or [])
            services = {}
            for hit in hits:
                if not isinstance(hit, dict): continue
                sid = str(hit.get("sid", "FACEBOOK")).upper()
                r = str(hit.get("range") or hit.get("rid") or hit.get("number", "")).strip()
                if r:
                    if sid not in services: services[sid] = set()
                    services[sid].add(r)
            return {k: list(v) for k, v in services.items()}
    except Exception as e:
        print(f"Fetch Ranges Error: {e}")
    return {}

async def get_panel_ranges():
    return await asyncio.to_thread(_sync_get_panel_ranges)

def _sync_get_panel_real_number(target_range):
    headers = {"mauthapi": PANEL_API_KEY, "Accept": "application/json", "Content-Type": "application/json"}
    clean_rid = str(target_range).upper().replace("XXX", "").replace("X", "").strip()
    payload = {"rid": clean_rid}
    try:
        res = requests.post(f"{BASE_API_URL}/getnumber.php", headers=headers, json=payload, timeout=2)
        if res.status_code != 200:
            res = requests.post(f"{BASE_API_URL}/getnum", headers=headers, json=payload, timeout=2)
            
        if res.status_code == 200:
            res_data = res.json()
            data = res_data.get("data", {})
            phone = data.get("full_number") or data.get("national_number") or data.get("phone") or data.get("number")
            order_id = res_data.get("id") or data.get("id") or res_data.get("rid") or clean_rid
            if phone:
                return str(phone), str(order_id)
    except Exception as e:
        print(f"API Error: {e}")
    return None, None

async def get_panel_real_number(target_range="23762"):
    return await asyncio.to_thread(_sync_get_panel_real_number, target_range)

def _sync_check_panel_otp(target_phone, order_id):
    headers = {"mauthapi": PANEL_API_KEY, "Accept": "application/json"}
    clean_target = ''.join(filter(str.isdigit, str(target_phone)))
    short_target = clean_target[-6:] if len(clean_target) >= 6 else clean_target
    
    try:
        res = requests.get(f"{BASE_API_URL}/check.php?api_key={PANEL_API_KEY}&number=+{clean_target}", headers=headers, timeout=2)
        if res.status_code != 200:
            res = requests.get(f"{BASE_API_URL}/success-otp", headers=headers, timeout=2)

        if res.status_code == 200:
            res_json = res.json()
            otps = res_json.get("data", {}).get("otps", []) or res_json.get("data", []) or []
            if isinstance(otps, list):
                for otp_item in otps:
                    if not isinstance(otp_item, dict): continue
                    num_raw = str(otp_item.get("number", ""))
                    msg = str(otp_item.get("message", ""))
                    clean_num = ''.join(filter(str.isdigit, num_raw))
                    if short_target in clean_num or (clean_target and clean_target in clean_num):
                        match = re.search(r'\b\d{4,8}\b', msg)
                        if match: return match.group(0)
                        elif msg: return msg
    except Exception as e:
        print(f"OTP Check Error: {e}")
    return None

async def check_panel_otp(target_phone, order_id):
    return await asyncio.to_thread(_sync_check_panel_otp, target_phone, order_id)

async def auto_forward_console_logs(application):
    await asyncio.sleep(5)
    while True:
        try:
            headers = {"mauthapi": PANEL_API_KEY, "Accept": "application/json"}
            def fetch_console_hits():
                try:
                    res = requests.get(f"{BASE_API_URL}/console.php?api_key={PANEL_API_KEY}", headers=headers, timeout=2)
                    if res.status_code != 200:
                        res = requests.get(f"{BASE_API_URL}/console", headers=headers, timeout=2)
                    if res.status_code == 200:
                        res_json = res.json()
                        if isinstance(res_json, list): return res_json
                        return res_json.get("data", {}).get("hits", []) or res_json.get("data", []) or []
                except Exception: pass
                return []

            hits = await asyncio.to_thread(fetch_console_hits)
            for hit in hits:
                if not isinstance(hit, dict): continue
                r = hit.get("range", "") or hit.get("rid", "") or hit.get("number", "")
                sid = hit.get("sid", "FACEBOOK")
                msg = hit.get("message", "N/A")
                t_stamp = hit.get("time", "")
                
                unique_id = f"{r}_{t_stamp}_{msg}"
                if unique_id in SEEN_OTP_IDS: continue
                SEEN_OTP_IDS.add(unique_id)
                if len(SEEN_OTP_IDS) > 500: SEEN_OTP_IDS.clear()

                clean_num = str(r)
                masked_num = clean_num[:6] + "X" * (len(clean_num) - 6) if len(clean_num) > 6 else clean_num
                _, country_code, flag = get_country_info(str(r))
                
                log_text = (
                    f"<b>PANEL LOGS</b>\n"
                    f"📘 <b>{sid} OTP RECEIVE</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"{flag} <b>Country :</b> {country_code}\n"
                    f"🎯 <b>Range :</b> <code>{masked_num}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"✉ <b>Message :</b>\n"
                    f"<code>{msg}</code>"
                )
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("NUMBER BOT ↗", url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}")]])
                try:
                    await application.bot.send_message(chat_id=OTP_GROUP_CHAT_ID, text=log_text, reply_markup=markup, parse_mode="HTML")
                except Exception: pass
        except Exception: pass
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

async def poll_for_otp(chat_id, user_id, order_id, phone, context):
    for _ in range(300): 
        await asyncio.sleep(1) 
        try:
            status = await check_panel_otp(phone, order_id)
            if status:
                current_bal = USER_BALANCES.get(user_id, 0.0)
                USER_BALANCES[user_id] = current_bal + 0.00122
                otp_message = f"🚨 <b>NEW OTP RECEIVED!</b> 🚨\n\n📱 <b>Number:</b> <code>{phone}</code>\n🔑 <b>OTP Code:</b> <code>{status}</code>\n💰 <b>Earned:</b> +$0.00122"
                await context.bot.send_message(chat_id=chat_id, text=otp_message, parse_mode="HTML")
                return
        except Exception: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_STATES[user_id] = None
    reply_keyboard = [
        ["📞 Get API Number", "📂 Panel Ranges"],
        ["⚙ Set Range", "🟢 Live Traffic"],
        ["💳 Balance", "💬 Support"],
        ["📣 OTP Group"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text("Welcome to Panel Bot! 🤖\nPlease select an option from the menu below:", reply_markup=markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""
    state = USER_STATES.get(user_id)

    if state == "WAITING_FOR_RANGE":
        clean_text = text.strip()
        if "x" in clean_text.lower() or clean_text.isdigit():
            USER_STATES[user_id] = None
            USER_RANGES[user_id] = clean_text
            await update.message.reply_text(f"🔴 Target range updated to: <b>{clean_text}</b>", parse_mode="HTML")
        else:
            await update.message.reply_text("🔴 Invalid range! Please enter a valid number prefix (e.g. 23762).")
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
        wait_msg = await update.message.reply_text("⏳ Fetching real number from panel, please wait...")
        user_range = USER_RANGES.get(user_id, "23762")
        
        results = await asyncio.gather(
            get_panel_real_number(target_range=user_range),
            get_panel_real_number(target_range=user_range)
        )
        
        numbers, orders = [], []
        for p, oid in results:
            if p and p not in numbers:
                numbers.append(p)
                if oid: orders.append((p, oid))

        try: await wait_msg.delete()
        except Exception: pass

        if not numbers:
            await update.message.reply_text(f"❌ <b>No Real Number Available!</b>\n\nPanel has no stock for range <code>{user_range}</code>.", parse_mode="HTML")
            return

        _, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag}"
        reply_markup = create_number_markup(numbers)
        await update.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
        
        for p, oid in orders:
            asyncio.create_task(poll_for_otp(update.effective_chat.id, user_id, oid, p, context))

    elif "Panel Ranges" in text:
        USER_STATES[user_id] = None
        wait_msg = await update.message.reply_text("⏳ Fetching live ranges from panel...")
        services = await get_panel_ranges()
        try: await wait_msg.delete()
        except Exception: pass

        if not services:
            await update.message.reply_text("⚠️ No active ranges found in panel right now.")
            return

        keyboard = []
        for sid, ranges in services.items():
            keyboard.append([InlineKeyboardButton(f"📂 {sid} ({len(ranges)} Ranges)", callback_data=f"service_{sid}")])
        
        await update.message.reply_text("📂 <b>Available Panel Services & Ranges:</b>\nClick any service below to view its ranges:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif "Set Range" in text:
        USER_STATES[user_id] = "WAITING_FOR_RANGE"
        await update.message.reply_text("🔴 Please send your target number range (e.g. 23762):")

    elif "Live Traffic" in text:
        USER_STATES[user_id] = None
        headers = {"mauthapi": PANEL_API_KEY, "Accept": "application/json"}
        try:
            res = requests.get(f"{BASE_API_URL}/console.php?api_key={PANEL_API_KEY}", headers=headers, timeout=2)
            if res.status_code != 200: res = requests.get(f"{BASE_API_URL}/console", headers=headers, timeout=2)
            hits = res.json() if res.status_code == 200 else []
            if isinstance(hits, dict): hits = hits.get("data", {}).get("hits", []) or hits.get("data", []) or []
            total_hits = len(hits) if isinstance(hits, list) else 0
            await update.message.reply_text(f"📊 <b>Live Traffic Summary</b>\n\n📋 <b>Total OTP Received:</b> {total_hits}", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("⚠️ Could not fetch live traffic right now.")

    elif "Balance" in text:
        USER_STATES[user_id] = None
        user_bal = USER_BALANCES.get(user_id, 0.0)
        saved_info = USER_WITHDRAW_INFO.get(user_id, "Not Set")
        balance_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw_menu")],
            [InlineKeyboardButton("📱 Set bKash", callback_data="set_bkash"), InlineKeyboardButton("🔴 Set Binance", callback_data="set_binance")],
            [InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ])
        await update.message.reply_text(f"💳 <b>Your Balance:</b> ${user_bal:.5f}\n📂 <b>Payout Info:</b> {saved_info}\n\n📌 <i>Minimum withdraw is $1.00</i>", reply_markup=balance_markup, parse_mode="HTML")

    elif "Support" in text:
        await update.message.reply_text(f"💬 jogajog korun: https://t.me/{SUPPORT_USERNAME}")

    elif "OTP Group" in text:
        await update.message.reply_text(f"📣 joyen korun: https://t.me/{YOUR_TELEGRAM_USERNAME}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("service_"):
        sid = data.replace("service_", "")
        services = await get_panel_ranges()
        ranges = services.get(sid, [])
        
        keyboard = []
        for r in ranges[:10]:
            country_name, _, flag = get_country_info(r)
            keyboard.append([InlineKeyboardButton(f"{flag} {country_name} | {r}XXX", callback_data=f"selrange_{r}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Services", callback_data="back_services")])
        
        try:
            await query.edit_message_text(f"📌 <b>Service: {sid}</b>\nSelect a range to set as target:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except Exception: pass

    elif data.startswith("selrange_"):
        selected_r = data.replace("selrange_", "")
        USER_RANGES[user_id] = selected_r
        try:
            await query.edit_message_text(f"✅ Target range successfully set to: <code>{selected_r}</code>\n\nNow click 'Get API Number' from menu to grab numbers!", parse_mode="HTML")
        except Exception: pass

    elif data == "back_services":
        services = await get_panel_ranges()
        keyboard = [[InlineKeyboardButton(f"📂 {sid} ({len(ranges)} Ranges)", callback_data=f"service_{sid}")] for sid, ranges in services.items()]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_home")])
        try:
            await query.edit_message_text("📂 <b>Available Panel Services & Ranges:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        except Exception: pass

    elif data == "change_number":
        user_range = USER_RANGES.get(user_id, "23762")
        results = await asyncio.gather(get_panel_real_number(target_range=user_range), get_panel_real_number(target_range=user_range))
        numbers, orders = [], []
        for p, oid in results:
            if p and p not in numbers:
                numbers.append(p)
                if oid: orders.append((p, oid))
        if not numbers: return
        _, _, flag = get_country_info(numbers[0])
        try:
            await query.edit_message_text(f"✅ <b>Number:</b> {flag}", reply_markup=create_number_markup(numbers), parse_mode="HTML")
        except Exception: pass
        for p, oid in orders:
            asyncio.create_task(poll_for_otp(query.message.chat_id, user_id, oid, p, context))

    elif data == "back_home":
        try: await query.message.delete()
        except Exception: pass
        await start(update, context)
        
    elif data == "set_bkash":
        USER_STATES[user_id] = "WAITING_FOR_BKASH"
        await query.message.reply_text("📲 Please send your bKash number:")
        
    elif data == "set_binance":
        USER_STATES[user_id] = "WAITING_FOR_BINANCE"
        await query.message.reply_text("🔴 Please send your Binance Pay ID:")
        
    elif data == "withdraw_menu":
        user_bal = USER_BALANCES.get(user_id, 0.0)
        if user_bal < 1.0:
            await query.message.reply_text(f"❌ Balance ${user_bal:.5f} is less than minimum withdraw ($1.00).")
        else:
            saved_info = USER_WITHDRAW_INFO.get(user_id)
            if not saved_info:
                await query.message.reply_text("⚠️ Please set your bKash or Binance ID first.")
            else:
                await query.message.reply_text(f"✅ Withdraw request submitted for ${user_bal:.5f} to <b>{saved_info}</b>", parse_mode="HTML")
                USER_BALANCES[user_id] = 0.0

async def post_init(application):
    asyncio.create_task(auto_forward_console_logs(application))

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading
    class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running!")
        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    app.run_polling()
