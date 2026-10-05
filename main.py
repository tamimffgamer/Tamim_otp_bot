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

def _sync_test_connection():
    headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
    try:
        # Anek somoy panel-er console ba stats endpoint alada thake
        res = requests.get(f"{BASE_API_URL}/console.php", headers=headers, timeout=5)
        return res.status_code, res.text[:300]
    except Exception as e:
        return 500, str(e)

async def test_api_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_code, response_text = await asyncio.to_thread(_sync_test_connection)
    await update.message.reply_text(
        f"🔌 <b>API Connection Test:</b>\n\n"
        f"Status Code: <code>{status_code}</code>\n"
        f"Response Preview:\n<code>{response_text}</code>",
        parse_mode="HTML"
    )

def _sync_fetch_live_traffic_detailed():
    headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
    service_data = {}
    total_hits = 0
    try:
        res = requests.get(f"{BASE_API_URL}/console.php", headers=headers, timeout=3.0)
        if res.status_code == 200:
            res_json = res.json()
            # Ekhane amra shob possible keys check korchi jate data miss na hoy
            hits = (
                res_json.get("data", {}).get("hits", []) or 
                res_json.get("hits", []) or 
                res_json.get("data", []) or 
                res_json.get("ranges", []) or []
            )
            if isinstance(hits, list):
                total_hits = len(hits)
                for hit in hits:
                    if not isinstance(hit, dict): continue
                    r = hit.get("range") or hit.get("rid") or hit.get("number")
                    sid = str(hit.get("sid", hit.get("service", "FACEBOOK"))).upper().strip()
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""

    if "Live Traffic" in text or "TRAFFIC" in text:
        USER_STATES[user_id] = None
        service_data, total_hits = await fetch_live_traffic_detailed()
        
        if not service_data:
            await update.message.reply_text(
                "⚠️ <b>Panel Connection Warning:</b>\n"
                "Live traffic/ranges paoya jacche na. Apnar panel-er API key ba endpoint check করুন।\n\n"
                "API test korte `/testapi` command-ti use korun.", 
                parse_mode="HTML"
            )
            return

        keyboard = []
        for sid in sorted(service_data.keys()):
            total_sid_otp = sum(sum(c_info["ranges"].values()) for c_info in service_data[sid].values())
            keyboard.append([InlineKeyboardButton(f"👀 Explore {sid.title()} Range ({total_sid_otp})", callback_data=f"tr_svc_{sid}")])
        
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="tr_refresh"), InlineKeyboardButton("❌ Close", callback_data="tr_close")])
        markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(f"📊 <b>Live Traffic Panel</b>\n📋 <b>Total OTP:</b> {total_hits}\nSelect a service below:", reply_markup=markup, parse_mode="HTML")
    
    elif "Get API Number" in text:
        await update.message.reply_text("📞 API Number fetching feature ready.")
    elif "Balance" in text:
        await update.message.reply_text("💳 Balance menu.")
    elif "Support" in text:
        await update.message.reply_text("💬 Support menu.")
    elif "OTP Group" in text:
        await update.message.reply_text("📣 OTP Group link.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('testapi', test_api_connection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
        do_GET = lambda self, *a: (self.send_response(200), self.end_headers(), self.wfile.write(b"Bot is running!"))

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    app.run_polling()
