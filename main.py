import os
import asyncio
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, CopyTextButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Mino SMS API details
API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"
BASE_API_URL = "https://minosms.com"

YOUR_TELEGRAM_USERNAME = "smm_otp_grup"
OTP_GROUP_CHAT_ID = -1004436883235

USER_STATES = {}
USER_RANGES = {}
SEEN_OTP_IDS = set()

def get_country_info(phone_number):
    clean_num = str(phone_number).replace("+", "").strip()
    if clean_num.startswith("880"): return "Bangladesh", "BD", "🇧🇩"
    elif clean_num.startswith("237"): return "Cameroon", "CM", "🇨🇲"
    elif clean_num.startswith("225"): return "Ivory Coast", "CI", "🇨🇮"
    elif clean_num.startswith("228"): return "Togo", "TG", "🇹🇬"
    elif clean_num.startswith("229"): return "Benin", "BJ", "🇧🇯"
    elif clean_num.startswith("255"): return "Tanzania", "TZ", "🇹🇿"
    elif clean_num.startswith("266"): return "Lesotho", "LS", "🇱🇸"
    elif clean_num.startswith("380"): return "Ukraine", "UA", "🇺🇦"
    elif clean_num.startswith("996"): return "Kyrgyzstan", "KG", "🇰🇬"
    elif clean_num.startswith("43"): return "Austria", "AT", "🇦🇹"
    else: return "Bangladesh", "BD", "🇧🇩"

def _sync_get_real_number(target_range):
    headers = {
        "mauthapi": API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    clean_rid = str(target_range).upper().strip()
    payload = {"rid": clean_rid}
    try:
        res = requests.post(f"{BASE_API_URL}/getnumber.php", headers=headers, json=payload, timeout=5)
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

async def get_real_number(target_range="88017XXX"):
    return await asyncio.to_thread(_sync_get_real_number, target_range)

def _sync_fetch_live_traffic():
    headers = {"mauthapi": API_KEY, "Accept": "application/json"}
    range_counts = {}
    total_hits = 0
    try:
        res = requests.get(f"{BASE_API_URL}/console.php", headers=headers, timeout=5)
        if res.status_code == 200:
            res_json = res.json()
            hits = res_json.get("data", {}).get("hits", []) or res_json.get("data", []) or res_json.get("hits", [])
            if isinstance(hits, list):
                total_hits = len(hits)
                for hit in hits:
                    if not isinstance(hit, dict): continue
                    r = hit.get("range") or hit.get("rid")
                    sid = hit.get("sid", "FACEBOOK")
                    if r:
                        clean_r = str(r).strip()
                        if clean_r in range_counts:
                            range_counts[clean_r]["count"] += 1
                        else:
                            range_counts[clean_r] = {"sid": str(sid).upper(), "count": 1}
    except Exception as e:
        print(f"Traffic Error: {e}")
    sorted_ranges = sorted(range_counts.items(), key=lambda x: x[1]["count"], reverse=True)
    return sorted_ranges, total_hits

async def fetch_live_traffic_from_panel():
    return await asyncio.to_thread(_sync_fetch_live_traffic)

def _sync_check_otp(target_phone, order_id):
    headers = {"mauthapi": API_KEY, "Accept": "application/json"}
    clean_target = ''.join(filter(str.isdigit, str(target_phone)))
    short_target = clean_target[-6:] if len(clean_target) >= 6 else clean_target
    
    try:
        res = requests.get(f"{BASE_API_URL}/check.php?api_key={API_KEY}&number=+{clean_target}", headers=headers, timeout=3)
        if res.status_code == 200:
            res_json = res.json()
            otps = res_json.get("data", {}).get("otps", []) or res_json.get("otps", []) or []
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

async def check_otp(target_phone, order_id):
    return await asyncio.to_thread(_sync_check_otp, target_phone, order_id)

async def auto_forward_console_logs(application):
    await asyncio.sleep(5)
    while True:
        try:
            headers = {"mauthapi": API_KEY, "Accept": "application/json"}
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
                msg = hit.get("message", "N/A").replace("<", "&lt;").replace(">", "&gt;")
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

                country_name, country_code, flag = get_country_info(str(r))
                
                log_text = (
                    f"<b>SMM NUMBER PANEL</b>                   <b>Admin</b>\n"
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
                    [InlineKeyboardButton("NUMBER BOT ↗", url="https://t.me/Smmnumberbot")]
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
        await asyncio.sleep(1) 
        try:
            status = await check_otp(phone, order_id)
            if status:
                otp_message = f"🚨 <b>NEW OTP RECEIVED!</b> 🚨\n\n📱 <b>Number:</b> <code>{phone}</code>\n🔑 <b>OTP Code:</b> <code>{status}</code>"
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
        ["📣 OTP Group"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text("Welcome to FB MASTER NUMBER bot! 🤖\nPlease select an option from the menu below:", reply_markup=markup)

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
            await update.message.reply_text("🔴 Invalid range! Please enter a valid number prefix (e.g. 88017XXX).")
        return

    if "Get API Number" in text:
        USER_STATES[user_id] = None
        wait_msg = await update.message.reply_text("⏳ Fetching real number from panel, please wait...")
        user_range = USER_RANGES.get(user_id, "88017XXX")
        numbers = []
        orders = []

        for _ in range(2):
            p, oid = await get_real_number(target_range=user_range)
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

        country_name, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag} {country_name}"
        
        reply_markup = create_number_markup(numbers)
        await update.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
        
        for p, oid in orders:
            asyncio.create_task(poll_for_otp(update.effective_chat.id, oid, p, context))

    elif "Set Range" in text:
        USER_STATES[user_id] = "WAITING_FOR_RANGE"
        await update.message.reply_text("🔴 Please send your target number range (e.g. 88017XXX):")

    elif "Live Traffic" in text:
        USER_STATES[user_id] = None
        sorted_ranges, total_hits = await fetch_live_traffic_from_panel()
        traffic_lines = ["📊 <b>Live Traffic</b>\n", f"📋 <b>Total OTP:</b> {total_hits}", f"⏱ <b>Record:</b> Last 15 Minutes\n"]
        if sorted_ranges:
            top_r, top_info = sorted_ranges[0]
            _, _, top_flag = get_country_info(top_r)
            traffic_lines.append(f"👑 <b>Top Range:</b> {top_flag} <code>{top_r}</code> - {top_info['sid']}")
            traffic_lines.append("\n📥 <b>Range List</b>")
            for r, info in sorted_ranges:
                _, _, flag = get_country_info(r)
                traffic_lines.append(f"• {flag} <code>{r}</code> - {info['sid']} - {info['count']}")
        else:
            traffic_lines.append("⚠️ No active ranges found right now.")
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
        user_range = USER_RANGES.get(user_id, "88017XXX")
        numbers = []
        orders = []

        for _ in range(2):
            p, oid = await get_real_number(target_range=user_range)
            if p and p not in numbers:
                numbers.append(p)
                if oid: orders.append((p, oid))

        if not numbers: return

        country_name, _, flag = get_country_info(numbers[0])
        header_text = f"✅ <b>Number:</b> {flag} {country_name}"
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
