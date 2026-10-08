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
    if api_country:
        c_lower = api_country.lower()
        if "madagascar" in c_lower: return "Madagascar", "MG", "🇲🇬"
        elif "ivory" in c_lower or "côte" in c_lower: return "Ivory Coast", "CI", "🇨🇮"
        elif "cameroon" in c_lower: return "Cameroon", "CM", "🇨🇲"
        elif "togo" in c_lower: return "Togo", "TG", "🇹🇬"
        elif "benin" in c_lower: return "Benin", "BJ", "🇧🇯"
        elif "tanzania" in c_lower: return "Tanzania", "TZ", "🇹🇿"
        elif "ukraine" in c_lower: return "Ukraine", "UA", "🇺🇦"
        elif "kyrgyzstan" in c_lower: return "Kyrgyzstan", "KG", "🇰🇬"
    
    if clean_num.startswith("880"): return "Bangladesh", "BD", "🇧🇩"
    elif clean_num.startswith("237"): return "Cameroon", "CM", "🇨🇲"
    elif clean_num.startswith("225"): return "Ivory Coast", "CI", "🇨🇮"
    elif clean_num.startswith("228"): return "Togo", "TG", "🇹🇬"
    elif clean_num.startswith("261"): return "Madagascar", "MG", "🇲🇬"
    else: return "International", "INT", "🌍"

def _sync_get_mino_real_number(target_range):
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
    return await asyncio.to_thread(_sync_get_mino_real_number, target_range)

def _sync_success_otp(phone_number):
    headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
    clean_num = str(phone_number).strip()
    try:
        requests.get(f"{BASE_API_URL}/success_otp.php?api_key={MINO_API_KEY}&number={clean_num}", headers=headers, timeout=5.0)
    except:
        pass

async def success_otp(phone_number):
    await asyncio.to_thread(_sync_success_otp, phone_number)

def _sync_fetch_live_traffic_detailed():
    headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
    service_data = {}
    total_hits = 0
    try:
        res = requests.get(f"{BASE_API_URL}/console.php", headers=headers, timeout=10.0)
        if res.status_code == 200:
            res_json = res.json()
            hits = res_json.get("data", [])
            if isinstance(hits, list):
                total_hits = len(hits)
                for hit in hits:
                    if not isinstance(hit, dict): continue
                    r = hit.get("range") or hit.get("number") or hit.get("full_number", "") or hit.get("phone", "")
                    sid = str(hit.get("service", "FACEBOOK")).upper().strip()
                    api_country = hit.get("country", "")
                    
                    if r:
                        clean_r = str(r).strip()
                        c_name, c_code, c_flag = get_country_info(clean_r, api_country)
                        
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

async def auto_forward_console_logs(application):
    print("Background Console Stream Listener Started Successfully!")
    while True:
        try:
            headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
            
            res = await asyncio.to_thread(requests.get, f"{BASE_API_URL}/console.php", headers=headers, timeout=6.0)
            if res.status_code == 200:
                res_json = res.json()
                hits = res_json.get("data", [])
                if isinstance(hits, list):
                    current_time = time.time()
                    for hit in hits:
                        if not isinstance(hit, dict): continue
                        msg = hit.get("message") or hit.get("text") or hit.get("sms") or hit.get("content") or hit.get("msg") or ""
                        num = str(hit.get("number") or hit.get("full_number") or hit.get("phone") or hit.get("range", "")).strip()
                        service = hit.get("service", "SMS")
                        country = hit.get("country", "International")

                        if not msg: continue
                        if str(msg).lower().strip() in ["success", "completed", "waiting", "failed"]:
                            continue

                        g_id = f"g_{num}_{msg}_{time.time()}"
                        if g_id in SEEN_OTP_IDS: continue
                        SEEN_OTP_IDS.add(g_id)
                        if len(SEEN_OTP_IDS) > 500:
                            SEEN_OTP_IDS.clear()

                        match_otp_g = re.search(r'\b\d{4,8}\b', str(msg))
                        if not match_otp_g: continue
                        otp_code_g = match_otp_g.group(0)

                        _, _, flag = get_country_info(num, country)
                        
                        # শুধুমাত্র ডিজিটগুলো ফিল্টার করে নেওয়া
                        clean_console_num = re.sub(r'\D', '', num)
                        
                        for user_id, u_info in list(ACTIVE_USER_NUMBERS.items()):
                            u_phone_raw = str(u_info.get("phone", ""))
                            u_clean = re.sub(r'\D', '', u_phone_raw)
                            fetch_time = u_info.get("fetch_time", 0)
                            
                            if (current_time - fetch_time) > 1200:
                                continue

                            if u_clean and clean_console_num:
                                # শেষ ৯টি ডিজিট বের করা
                                u_suffix = u_clean[-9:] if len(u_clean) >= 9 else u_clean
                                c_suffix = clean_console_num[-9:] if len(clean_console_num) >= 9 else clean_console_num
                                
                                # শেষের ৯ ডিজিট হুবহু মিলে গেলে কোড ফরোয়ার্ড হবে
                                if u_suffix and c_suffix and (u_suffix == c_suffix):
                                    sent_set = u_info.setdefault("sent_otps", set())
                                    if otp_code_g not in sent_set:
                                        sent_set.add(otp_code_g)
                                        current_bal = USER_BALANCES.get(user_id, 0.0)
                                        USER_BALANCES[user_id] = current_bal + 0.00122

                                        personal_text = (
                                            f"🟢 <b>SUCCESSFUL OTP RECEIVED</b>\n\n"
                                            f"🌐 <b>Service :</b> {service}\n"
                                            f"🌍 <b>Country :</b> {country} ({flag})\n"
                                            f"🎯 <b>Number :</b> <code>{num}</code>\n"
                                            f"🔑 <b>OTP Code :</b> <code>{otp_code_g}</code>\n\n"
                                            f"✉ <b>Full Message :</b>\n<code>{msg}</code>\n\n"
                                            f"💰 <b>Earned :</b> +$0.00122"
                                        )
                                        personal_markup = InlineKeyboardMarkup([
                                            [InlineKeyboardButton(text=f"📋 Copy OTP: {otp_code_g}", copy_text=CopyTextButton(text=otp_code_g))],
                                            [InlineKeyboardButton("🔄 Change Number", callback_data="change_number")]
                                        ])
                                        try:
                                            await application.bot.send_message(
                                                chat_id=u_info["chat_id"], 
                                                text=personal_text, 
                                                reply_markup=personal_markup,
                                                parse_mode="HTML"
                                            )
                                            await success_otp(num)
                                        except Exception as per_ex:
                                            print(f"Personal Send Error: {per_ex}")

                        group_text = (
                            f"🟢 <b>{service} OTP RECEIVED</b>\n\n"
                            f"🌍 <b>Country :</b> {country} ({flag})\n"
                            f"🎯 <b>Number :</b> <code>{num}</code>\n"
                            f"🔑 <b>Code :</b> <code>{otp_code_g}</code>\n\n"
                            f"✉ <b>Message :</b>\n<code>{msg}</code>"
                        )
                        group_markup = InlineKeyboardMarkup([
                            [InlineKeyboardButton(text=f"📋 Copy OTP: {otp_code_g}", copy_text=CopyTextButton(text=otp_code_g))],
                            [InlineKeyboardButton("NUMBER BOT ↗", url=f"https://t.me/{application.bot.username}")]
                        ])
                        try:
                            await application.bot.send_message(
                                chat_id=OTP_GROUP_CHAT_ID, 
                                text=group_text, 
                                reply_markup=group_markup, 
                                parse_mode="HTML"
                            )
                        except: pass
            else:
                print(f"Console API Status Code: {res.status_code}")

        except Exception as e:
            print(f"Background Loop Error: {e}")
        await asyncio.sleep(1)

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
            header_text = f"✅ <b>Number:</b> {flag} {country_name}\n\nEkhon ei number-ti te OTP pathale sathe sathe apnake real code ekhane pathiye dewa hobe! (Valid for 20 mins)"
            reply_markup = create_single_number_markup(phone)
            await update.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")

        elif "Set Range" in text:
            USER_STATES[user_id] = "WAITING_FOR_RANGE"
            await update.message.reply_text("🔴 Please send your target number range (e.g. 23762XXX):")

        elif "Live Traffic" in text or "TRAFFIC" in text:
            USER_STATES[user_id] = None
            service_data, total_hits = await fetch_live_traffic_detailed()
            
            if not service_data:
                await update.message.reply_text("⚠ No active traffic found right now.", parse_mode="HTML")
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
            header_text = f"✅ <b>New Number:</b> {flag} {country_name}"
            reply_markup = create_single_number_markup(phone)
            try:
                await query.edit_message_text(header_text, reply_markup=reply_markup, parse_mode="HTML")
            except:
                await query.message.reply_text(header_text, reply_markup=reply_markup, parse_mode="HTML")

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
            try: await query.edit_message_text(f"👑 <b>Explore Service:</b> 🌐 {sid}\n\nSelect a country:", reply_markup=markup, parse_mode="HTML")
            except: pass

        elif data.startswith("tr_cnt_"):
            await query.answer()
            parts = data.split("_")
            sid = parts[2]
            c_code = parts[3]
            service_data, _ = await fetch_live_traffic_detailed()
            if sid not in service_data or c_code not in service_data[sid]: return
            
            c_data = service_data[sid][c_code]
            ranges = c_data["ranges"]
            
            keyboard = []
            row = []
            for r_num, count in sorted(ranges.items(), key=lambda x: x[1], reverse=True):
                row.append(InlineKeyboardButton(f"🎛 {r_num} ({count})", copy_text=CopyTextButton(text=r_num)))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row: keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"tr_svc_{sid}")])
            markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.edit_message_text(f"👑 <b>Ranges for</b> 🌐 {sid} - {c_data['flag']} <b>{c_code}</b>\n\nClick range to copy:", reply_markup=markup, parse_mode="HTML")
            except: pass

        elif data == "tr_main" or data == "tr_refresh":
            await query.answer("🔄 Refreshed!")
            service_data, total_hits = await fetch_live_traffic_detailed()
            keyboard = []
            for sid in sorted(service_data.keys()):
                total_sid_otp = sum(sum(c_info["ranges"].values()) for c_info in service_data[sid].values())
                keyboard.append([InlineKeyboardButton(f"👀 Explore {sid.title()} Range ({total_sid_otp})", callback_data=f"tr_svc_{sid}")])
            keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="tr_refresh"), InlineKeyboardButton("❌ Close", callback_data="tr_close")])
            markup = InlineKeyboardMarkup(keyboard)
            try: await query.edit_message_text(f"📊 <b>Live Traffic Panel</b>\n📋 <b>Total OTP:</b> {total_hits}\nSelect a service:", reply_markup=markup, parse_mode="HTML")
            except: pass

        elif data == "tr_close":
            try: await query.message.delete()
            except: pass

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

async def on_startup(application):
    asyncio.create_task(auto_forward_console_logs(application))

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
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

    app.run_polling()
