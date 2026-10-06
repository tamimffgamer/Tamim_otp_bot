import os
import asyncio
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, CopyTextButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

MINOSMS_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfc1d17"
BASE_API_URL = "https://minosms.com"
YOUR_TELEGRAM_USERNAME = "tamim_otp_bot"
OTP_GROUP_CHAT_ID = -5452590003

USER_STATES = {}
USER_RANGES = {}
SEEN_OTP_IDS = set()

def get_country_info(phone_number):
    clean_num = str(phone_number).replace("+", "").strip()
    if clean_num.startswith("237"): return "Cameroon", "CM", "🇨🇲"
    elif clean_num.startswith("225"): return "Ivory Coast", "CI", "🇨🇮"
    elif clean_num.startswith("228"): return "Togo", "TG", "🇹🇬"
    elif clean_num.startswith("229"): return "Benin", "BJ", "🇧🇯"
    elif clean_num.startswith("255"): return "Tanzania", "TZ", "🇹🇿"
    elif clean_num.startswith("266"): return "Lesotho", "LS", "🇱🇸"
    elif clean_num.startswith("380"): return "Ukraine", "UA", "🇺🇦"
    elif clean_num.startswith("224"): return "Guinea", "GN", "🇬🇳"
    elif clean_num.startswith("996"): return "Kyrgyzstan", "KG", "🇰🇬"
    elif clean_num.startswith("43"): return "Austria", "AT", "🇦🇹"
    else: return "Togo", "TG", "🇹🇬"

def _sync_get_minosms_real_number(target_range):
    headers = {
        "mauthapi": MINOSMS_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    clean_rid = str(target_range).upper().replace("XXX", "").replace("X", "").strip()
    payload = {"rid": clean_rid}
    try:
        res = requests.post(f"{BASE_API_URL}/getnumber.php", headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            res_data = res.json()
            data = res_data.get("data", {})
            phone = data.get("full_number") or data.get("national_number") or data.get("phone") or data.get("number") or res_data.get("number")
            order_id = res_data.get("id") or data.get("id") or res_data.get("rid") or clean_rid
            if phone:
                return str(phone), str(order_id)
    except Exception as e:
        print(f"API Error: {e}")
    return None, None

async def get_minosms_real_number(target_range="22896"):
    return await asyncio.to_thread(_sync_get_minosms_real_number, target_range)

def _sync_fetch_live_traffic():
    headers = {"mauthapi": MINOSMS_API_KEY, "Accept": "application/json"}
    service_data = {}
    total_hits = 0
    endpoints = ["/console.php", "/console", "/api/console", "/gettraffic"]
    
    for ep in endpoints:
        try:
            res = requests.get(f"{BASE_API_URL}{ep}", headers=headers, timeout=5)
            if res.status_code == 200:
                res_json = res.json()
                data = res_json.get("data", res_json)
                hits = []
                if isinstance(data, dict):
                    hits = data.get("hits", data.get("services", data.get("list", [])))
                elif isinstance(data, list):
                    hits = data
                
                if hits:
                    if isinstance(hits, dict):
                        for s_name, s_info in hits.items():
                            s_upper = str(s_name).upper()
                            if s_upper not in service_data:
                                service_data[s_upper] = []
                            ranges = s_info if isinstance(s_info, list) else s_info.get("ranges", [])
                            for r_item in ranges:
                                total_hits += 1
                                r_val = r_item.get("range") or r_item.get("rid") or str(r_item)
                                if r_val not in service_data[s_upper]:
                                    service_data[s_upper].append(str(r_val))
                    elif isinstance(hits, list):
                        for hit in hits:
                            if not isinstance(hit, dict): continue
                            total_hits += 1
                            r = hit.get("range") or hit.get("rid") or hit.get("number")
                            sid = hit.get("sid", hit.get("service", "FACEBOOK"))
                            if r:
                                s_upper = str(sid).upper()
                                if s_upper not in service_data:
                                    service_data[s_upper] = []
                                clean_r = str(r).strip()
                                if clean_r not in service_data[s_upper]:
                                    service_data[s_upper].append(clean_r)
                    if service_data:
                        break
        except Exception as e:
            continue
    return service_data, total_hits

async def fetch_live_traffic_from_panel():
    return await asyncio.to_thread(_sync_fetch_live_traffic)

def _sync_check_minosms_otp(target_phone, order_id):
    headers = {"mauthapi": MINOSMS_API_KEY, "Accept": "application/json"}
    clean_target = ''.join(filter(str.isdigit, str(target_phone)))
    short_target = clean_target[-6:] if len(clean_target) >= 6 else clean_target
    
    endpoints = ["/success-otp", "/console.php", "/history", "/api/history"]
    
    for ep in endpoints:
        try:
            res = requests.get(f"{BASE_API_URL}{ep}", headers=headers, timeout=4)
            if res.status_code == 200:
                res_json = res.json()
                data = res_json.get("data", res_json)
                otps = []
                if isinstance(data, dict):
                    otps = data.get("otps", data.get("hits", data.get("list", [])))
                elif isinstance(data, list):
                    otps = data
                
                if isinstance(otps, list):
                    for otp_item in otps:
                        if not isinstance(otp_item, dict): continue
                        num_raw = str(otp_item.get("number", otp_item.get("full_number", otp_item.get("range", ""))))
                        msg = str(otp_item.get("message", otp_item.get("msg", "")))
                        clean_num = ''.join(filter(str.isdigit, num_raw))
                        
                        if short_target in clean_num or (clean_target and clean_target in clean_num):
                            if msg and msg != "N/A" and msg != "None":
                                match = re.search(r'\b\d{4,8}\b', msg)
                                otp_code = match.group(0) if match else msg
                                return otp_code, msg
        except Exception as e:
            continue
    return None, None

async def check_minosms_otp(target_phone, order_id):
    return await asyncio.to_thread(_sync_check_minosms_otp, target_phone, order_id)

async def auto_forward_console_logs(application):
    await asyncio.sleep(5)
    while True:
        try:
            headers = {"mauthapi": MINOSMS_API_KEY, "Accept": "application/json"}
            def fetch_console_hits():
                try:
                    res = requests.get(f"{BASE_API_URL}/console.php", headers=headers, timeout=5)
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
                masked_num = clean_num[:6] + "X" * (len(clean_num) - 6) if len(clean_num) > 6 else clean_num
                _, country_code, flag = get_country_info(str(r))
                
                log_text = (
                    f"<b>𝑻𝑨𝑴𝒊𝑴 𝑶𝑻𝑷 𝑩𝑶𝑻</b>                    <b>Admin</b>\n"
                    f"OTP                     Admin\n"
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
                    [InlineKeyboardButton("NUMBER BOT ↗", url="https://t.me/tamim_otp_bot")]
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
        await asyncio.sleep(3)

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

async def poll_for_otp(chat_id, order_id, phone, context):
    for _ in range(300): 
        await asyncio.sleep(2) 
        try:
            otp_code, full_msg = await check_minosms_otp(phone, order_id)
            if otp_code:
                _, _, flag = get_country_info(phone)
                otp_message = (
                    f"🚨 <b>SUCCESS! OTP RECEIVED</b> 🚨\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"{flag} <b>Number:</b> <code>{phone}</code>\n"
                    f"🔑 <b>OTP Code:</b> <code>{otp_code}</code>\n"
                    f"✉ <b>Full Message:</b>\n<code>{full_msg}</code>"
                )
                
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Copy OTP", copy_text=CopyTextButton(text=otp_code))],
                    [InlineKeyboardButton("🔄 Get New Number", callback_data="change_number")]
                ])
                
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=otp_message, 
                    reply_markup=markup,
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
        ["📣 OTP Group"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text("Welcome to 𝑻𝑨𝑴𝒊𝑴 𝑶𝑻𝑷 𝑩𝑶𝑻 bot! 🤖\nPlease select an option from the menu below:", reply_markup=markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""

    if USER_STATES.get(user_id) == "WAITING_FOR_RANGE":
        clean_text = text.strip()
        if "x" in clean_text.lower() or clean_text.isdigit():
            USER_STATES[user_id] = None
            USER_RANGES[user_id] = clean_text
            await update.message.reply_text(f"🔴 Target range updated to: <b>{clean_text}</b>", parse_mode="HTML")
        else:
            await update.message.reply_text("🔴 Invalid range! Please enter a valid number prefix (e.g. 22896).")
        return

    if "Get API Number" in text:
        USER_STATES[user_id] = None
        wait_msg = await update.message.reply_text("⏳ Fetching real number from panel, please wait...")
        user_range = USER_RANGES.get(user_id, "22896")
        numbers = []
        orders = []

        for _ in range(2):
            p, oid = await get_minosms_real_number(target_range=user_range)
            if p and p not in numbers:
                numbers.append(p)
                if oid: orders.append((p, oid))

        try:
            await wait_msg.delete()
        except Exception:
            pass

        if not numbers:
            await update.message.reply_text(f"❌ <b>No Real Number Available!</b>\n\nPanel has no stock for range <code>{user_range}</code>.", parse_mode="HTML")
            return

        _, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag}\n⏳ Listening live for OTP..."
        
        reply_markup = create_number_markup(numbers)
        await update.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
        
        for p, oid in orders:
            asyncio.create_task(poll_for_otp(update.effective_chat.id, oid, p, context))

    elif "Set Range" in text:
        USER_STATES[user_id] = "WAITING_FOR_RANGE"
        await update.message.reply_text("🔴 Please send your target number range (e.g. 22896):")

    elif "Live Traffic" in text:
        USER_STATES[user_id] = None
        wait_traffic = await update.message.reply_text("⏳ Fetching live traffic from panel...")
        
        service_data, total_hits = await fetch_live_traffic_from_panel()
        
        try:
            await wait_traffic.delete()
        except Exception:
            pass
            
        traffic_lines = [
            "📊 <b>Live Traffic Summary</b>",
            f"📋 <b>Total Ranges/Hits:</b> {total_hits}",
            f"⏱ <b>Record:</b> Active Panel Services\n",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        
        if service_data:
            for service_name, ranges_list in service_data.items():
                ranges_count = len(ranges_list)
                traffic_lines.append(f"🔹 <b>{service_name}</b> <code>[{ranges_count} Ranges]</code>")
                sample_ranges = ", ".join([f"<code>{r}</code>" for r in ranges_list[:4]])
                if sample_ranges:
                    traffic_lines.append(f"   ↳ {sample_ranges}")
                traffic_lines.append("")
        else:
            traffic_lines.append("⚠️ No active traffic ranges found right now.")
            
        await update.message.reply_text("\n".join(traffic_lines), parse_mode="HTML")

    elif "Balance" in text:
        USER_STATES[user_id] = None
        balance_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Withdraw via Binance", callback_data="withdraw_binance")],
            [InlineKeyboardButton("🔴 Set Binance ID", callback_data="set_binance")],
            [InlineKeyboardButton("📣 OTP Group ↗", url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}")]
        ])
        await update.message.reply_text("Current Balance: $0.091\nBinance Pay ID: Not Set\n\nMinimum withdraw is $0.2", reply_markup=balance_markup)

    elif "OTP Group" in text:
        USER_STATES[user_id] = None
        group_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📣 Join OTP Group ↗", url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}")]
        ])
        await update.message.reply_text("📣 Click the button below to join our official OTP Group:", reply_markup=group_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "change_number":
        user_id = query.from_user.id
        user_range = USER_RANGES.get(user_id, "22896")
        numbers = []
        orders = []

        for _ in range(2):
            p, oid = await get_minosms_real_number(target_range=user_range)
            if p and p not in numbers:
                numbers.append(p)
                if oid: orders.append((p, oid))

        if not numbers: return

        _, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag}\n⏳ Listening live for OTP..."
        reply_markup = create_number_markup(numbers)
        try:
            await query.edit_message_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception: pass

        for p, oid in orders:
            asyncio.create_task(poll_for_otp(query.message.chat_id, oid, p, context))

    elif query.data == "back_home":
        try: await query.message.delete()
        except Exception: pass
        await start(update, context)
    elif query.data == "set_binance":
        await query.message.reply_text("Please send your Binance Pay ID:")

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
