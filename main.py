import os
import asyncio
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, CopyTextButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINOSMS_API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"
BASE_API_URL = "https://minosms.com"
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_URL = "https://t.me/smm_otp_grup"
OTP_GROUP_CHAT_ID = -1004436883235

USER_STATES = {}
USER_RANGES = {}

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
    else: return "Cameroon", "CM", "🇨🇲"

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
            phone = data.get("full_number") or data.get("national_number") or data.get("phone") or data.get("number")
            if phone:
                return str(phone), str(clean_rid)
    except Exception as e:
        print(f"API Error: {e}")
    return None, None

async def get_minosms_real_number(target_range="23762"):
    return await asyncio.to_thread(_sync_get_minosms_real_number, target_range)

def _sync_fetch_live_traffic():
    # Minosms console.php API call with query parameter or proper headers
    headers = {"mauthapi": MINOSMS_API_KEY, "Accept": "application/json"}
    range_counts = {}
    total_hits = 0
    top_range_text = "N/A"
    
    try:
        # Trying both query param and headers for maximum compatibility
        res = requests.get(f"{BASE_API_URL}/console.php?api_key={MINOSMS_API_KEY}", headers=headers, timeout=5)
        if res.status_code != 200:
            res = requests.get(f"{BASE_API_URL}/console.php", headers=headers, timeout=5)
            
        if res.status_code == 200:
            res_json = res.json()
            hits = []
            if isinstance(res_json, list):
                hits = res_json
            elif isinstance(res_json, dict):
                hits = res_json.get("data", []) or res_json.get("hits", []) or res_json.get("ranges", []) or res_json.get("console", [])
                if isinstance(hits, dict):
                    hits = hits.get("hits", []) or hits.get("data", []) or []

            if isinstance(hits, list):
                total_hits = len(hits)
                for hit in hits:
                    if isinstance(hit, str):
                        clean_r = hit.strip()
                        sid = "FACEBOOK"
                    elif isinstance(hit, dict):
                        r = hit.get("range") or hit.get("rid") or hit.get("number") or hit.get("phone") or hit.get("prefix")
                        sid = hit.get("sid") or hit.get("service") or hit.get("app") or "FACEBOOK"
                        clean_r = str(r).strip() if r else ""
                    else:
                        continue

                    if clean_r:
                        clean_r = clean_r.replace("XXX", "").replace("X", "").strip()
                        key = f"{clean_r}XXX - {str(sid).upper()}"
                        if key in range_counts:
                            range_counts[key]["count"] += 1
                        else:
                            _, _, flag = get_country_info(clean_r)
                            range_counts[key] = {"flag": flag, "range": clean_r, "sid": str(sid).upper(), "count": 1}
    except Exception as e:
        print(f"Traffic Error: {e}")
    
    sorted_items = sorted(range_counts.items(), key=lambda x: x[1]["count"], reverse=True)
    if sorted_items:
        top_range_text = f"{sorted_items[0][1]['flag']} {sorted_items[0][1]['range']}XXX - {sorted_items[0][1]['sid']}"
    
    return sorted_items, total_hits, top_range_text

async def fetch_live_traffic_from_panel():
    return await asyncio.to_thread(_sync_fetch_live_traffic)

def _sync_check_minosms_otp(target_phone):
    headers = {"mauthapi": MINOSMS_API_KEY, "Accept": "application/json"}
    clean_target = ''.join(filter(str.isdigit, str(target_phone)))
    short_target = clean_target[-6:] if len(clean_target) >= 6 else clean_target
    
    try:
        res = requests.get(f"{BASE_API_URL}/check.php?api_key={MINOSMS_API_KEY}&number=+{clean_target}", headers=headers, timeout=3)
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
                        if match:
                            return match.group(0)
                        elif msg:
                            return msg
    except Exception as e:
        print(f"OTP Check Error: {e}")
    return None

async def check_minosms_otp(target_phone):
    return await asyncio.to_thread(_sync_check_minosms_otp, target_phone)

async def auto_forward_console_logs(application):
    await asyncio.sleep(5)
    seen_local_hits = set()
    while True:
        try:
            headers = {"mauthapi": MINOSMS_API_KEY, "Accept": "application/json"}
            def fetch_console_hits():
                try:
                    res = requests.get(f"{BASE_API_URL}/console.php?api_key={MINOSMS_API_KEY}", headers=headers, timeout=5)
                    if res.status_code == 200:
                        res_json = res.json()
                        if isinstance(res_json, list): return res_json
                        data = res_json.get("data", []) or res_json.get("hits", [])
                        if isinstance(data, list): return data
                        if isinstance(data, dict): return data.get("hits", [])
                except Exception as ex:
                    print(f"Auto Forward Fetch Error: {ex}")
                return []

            hits = await asyncio.to_thread(fetch_console_hits)
            for hit in hits:
                if not isinstance(hit, dict): continue
                r = hit.get("range", "") or hit.get("rid", "") or hit.get("number", "")
                sid = hit.get("sid", "FACEBOOK")
                msg = hit.get("message", "N/A")
                t_stamp = hit.get("time", "")
                
                unique_id = f"{r}_{t_stamp}_{msg}"
                if unique_id in seen_local_hits: continue
                seen_local_hits.add(unique_id)
                if len(seen_local_hits) > 500: seen_local_hits.clear()

                clean_num = str(r)
                masked_num = clean_num[:6] + "X" * (len(clean_num) - 6) if len(clean_num) > 6 else clean_num
                _, country_code, flag = get_country_info(str(r))
                
                log_text = (
                    f"<b>MINOSMS PANEL LOGS</b>\n"
                    f"📘 <b>{sid} OTP RECEIVE</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"{flag} <b>Country :</b> {country_code}\n"
                    f"🎯 <b>Range :</b> <code>{masked_num}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"✉ <b>Message :</b>\n"
                    f"<code>{msg}</code>"
                )
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("NUMBER BOT ↗", url=OTP_GROUP_URL)]])
                try:
                    await application.bot.send_message(chat_id=OTP_GROUP_CHAT_ID, text=log_text, reply_markup=markup, parse_mode="HTML")
                except Exception as send_err:
                    print(f"Telegram Send Error: {send_err}")
        except Exception as e:
            print(f"Auto Forward Error: {e}")
        await asyncio.sleep(5)

def create_number_markup(numbers_list):
    keyboard = []
    for num in numbers_list:
        _, _, flag = get_country_info(num)
        keyboard.append([InlineKeyboardButton(text=f"{flag} {num}", copy_text=CopyTextButton(text=num))])
    keyboard.append([
        InlineKeyboardButton("🔔 OTP GROUP ↗", url=OTP_GROUP_URL),
        InlineKeyboardButton("🔄 Change", callback_data="change_number")
    ])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_home")])
    return InlineKeyboardMarkup(keyboard)

async def poll_for_otp(chat_id, phone, context):
    for _ in range(300):
        await asyncio.sleep(1)
        try:
            status = await check_minosms_otp(phone)
            if status:
                otp_message = f"🚨 <b>NEW OTP RECEIVED!</b> 🚨\n\n📱 <b>Number:</b> <code>{phone}</code>\n🔑 <b>OTP Code:</b> <code>{status}</code>"
                await context.bot.send_message(chat_id=chat_id, text=otp_message, parse_mode="HTML")
                return
        except Exception as e:
            print(f"Polling Send Error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_STATES[user_id] = None
    reply_keyboard = [
        ["📞 Get API Number", "⚙ Set Range"],
        ["🟢 Live Traffic", "💳 Balance"],
        ["🛠 Support", "📣 OTP Group"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text("Welcome to SMM NUMBER PANEL!\n\nConnected with Mino Panel. Select an option below:", reply_markup=markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""

    if USER_STATES.get(user_id) == "WAITING_FOR_RANGE":
        clean_text = text.strip()
        if "x" in clean_text.lower() or clean_text.isdigit():
            USER_STATES[user_id] = None
            USER_RANGES[user_id] = clean_text
            await update.message.reply_text(f"🔴 Target range successfully set to:\n<b>{clean_text}</b>\n\nEkhon nicher '📞 Get API Number' button e click kore panel theke number nite paren.", parse_mode="HTML")
        else:
            await update.message.reply_text("🔴 Invalid range! Please enter a valid number prefix (e.g. 23762XXX).")
        return

    if "Get API Number" in text:
        USER_STATES[user_id] = None
        wait_msg = await update.message.reply_text("⏳ Fetching real number from Minosms panel, please wait...")
        user_range = USER_RANGES.get(user_id, "23762")
        numbers = []

        for _ in range(2):
            p, oid = await get_minosms_real_number(target_range=user_range)
            if p and p not in numbers:
                numbers.append(p)

        try: await wait_msg.delete()
        except Exception: pass

        if not numbers:
            await update.message.reply_text(f"❌ <b>No Real Number Available!</b>\n\nPanel has no stock for range <code>{user_range}</code>.", parse_mode="HTML")
            return

        country_name, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag} <b>{country_name}</b>"
        reply_markup = create_number_markup(numbers)
        await update.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
        
        for p in numbers:
            asyncio.create_task(poll_for_otp(update.effective_chat.id, p, context))

    elif "Set Range" in text:
        USER_STATES[user_id] = "WAITING_FOR_RANGE"
        await update.message.reply_text("🔴 Please send your target number range (e.g. 23762XXX):")

    elif "Live Traffic" in text:
        USER_STATES[user_id] = None
        sorted_items, total_hits, top_range = await fetch_live_traffic_from_panel()
        
        traffic_lines = [
            "📊 <b>Live Traffic</b>\n",
            f"📋 <b>Total OTP:</b> {total_hits}",
            "⏱ <b>Record:</b> Last 15 Minutes\n",
            f"👑 <b>Top Range:</b> {top_range}\n",
            "📭 <b>Range List</b>"
        ]
        
        if sorted_items:
            for _, info in sorted_items[:20]:
                traffic_lines.append(f"• {info['flag']} <code>{info['range']}XXX - {info['sid']} - {info['count']}</code>")
        else:
            traffic_lines.append("⚠️ No active ranges found right now.")
            
        await update.message.reply_text("\n".join(traffic_lines), parse_mode="HTML")

    elif "Balance" in text:
        USER_STATES[user_id] = None
        balance_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw (bKash/Binance)", callback_data="withdraw_bKash")],
            [InlineKeyboardButton("📱 Set bKash Number", callback_data="set_bkash"), InlineKeyboardButton("🔴 Set Binance ID", callback_data="set_binance")],
            [InlineKeyboardButton("💬 Support ↗", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ])
        balance_text = (
            "💳 <b>Your Balance:</b> $0.00122\n"
            "📁 <b>Payout Info:</b> Not Set\n\n"
            "📌 <i>Minimum withdraw is $1.00</i>"
        )
        await update.message.reply_text(balance_text, reply_markup=balance_markup, parse_mode="HTML")

    elif "OTP Group" in text:
        USER_STATES[user_id] = None
        group_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📣 Join OTP Group ↗", url=OTP_GROUP_URL)]])
        await update.message.reply_text("📣 Click the button below to join our official OTP Group:", reply_markup=group_markup)

    elif "Support" in text:
        USER_STATES[user_id] = None
        support_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📞 সাপোর্টে যোগাযোগ করুন ↗", url=f"https://t.me/{SUPPORT_USERNAME}")]])
        support_text = (
            "💬 <b>সাপোর্ট সেন্টার</b>\n\n"
            "যেকোনো সমস্যা বা প্রশ্ন থাকলে নিচের বাটনে ক্লিক করে সরাসরি আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন।\n\n"
            "⏰ দ্রুত সাড়া দেওয়া হবে ইনশাআল্লাহ।"
        )
        await update.message.reply_text(support_text, reply_markup=support_markup, parse_mode="HTML")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "change_number":
        user_id = query.from_user.id
        user_range = USER_RANGES.get(user_id, "23762")
        numbers = []
        for _ in range(2):
            p, oid = await get_minosms_real_number(target_range=user_range)
            if p and p not in numbers: numbers.append(p)
        if not numbers: return

        country_name, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag} <b>{country_name}</b>"
        reply_markup = create_number_markup(numbers)
        try: await query.edit_message_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception: pass

        for p in numbers:
            asyncio.create_task(poll_for_otp(query.message.chat_id, p, context))

    elif query.data == "back_home":
        try: await query.message.delete()
        except Exception: pass
        await start(update, context)
    elif query.data == "set_binance":
        await query.message.reply_text("Please send your Binance Pay ID:")
    elif query.data == "set_bkash":
        await query.message.reply_text("Please send your bKash Number:")
    elif query.data == "withdraw_bKash":
        await query.message.reply_text("❌ Minimum withdraw balance ($1.00) is required!")

async def post_init(application):
    asyncio.create_task(auto_forward_console_logs(application))

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).drop_pending_updates(True).build()
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

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    app.run_polling()
