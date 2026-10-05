import os
import time
import threading
import requests
import telebot

from flask import Flask

# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
MINO_API_KEY = os.getenv("MINO_API_KEY")

# আপনার অনুমোদিত aggregate traffic/statistics API
# এখানে OTP/SMS content থাকবে না।
TRAFFIC_API_URL = os.getenv("TRAFFIC_API_URL", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

if not MINO_API_KEY:
    raise RuntimeError("MINO_API_KEY environment variable is missing.")


# =========================================================
# TELEGRAM BOT
# =========================================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


# =========================================================
# FLASK KEEP-ALIVE
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running."


@app.route("/health")
def health():
    return "OK"


def run_flask():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


# =========================================================
# RANGE CONFIGURATION
# =========================================================
#
# এখানে আপনার অনুমোদিত range ID বসাবেন।
#
# উদাহরণ:
# 88017XXX
# 22507XXX
# 22896XXX
# 23765XXX
#
# এগুলো শুধু range identifier।
# কোনো ফোন নম্বর বা OTP এখানে রাখা হবে না।
# =========================================================

RANGES = [
    {
        "id": "88017XXX",
        "country": "Bangladesh",
        "flag": "🇧🇩"
    },
    {
        "id": "22507XXX",
        "country": "Ivory Coast",
        "flag": "🇨🇮"
    },
    {
        "id": "22896XXX",
        "country": "Togo",
        "flag": "🇹🇬"
    },
    {
        "id": "23765XXX",
        "country": "Cameroon",
        "flag": "🇨🇲"
    }
]


# =========================================================
# CACHE
# =========================================================

TRAFFIC_CACHE = {}
CACHE_TIME = 0
CACHE_SECONDS = 10

CACHE_LOCK = threading.Lock()


# =========================================================
# GET AGGREGATE TRAFFIC
# =========================================================

def get_traffic_data():
    """
    TRAFFIC_API_URL থেকে aggregate traffic data নেয়।

    প্রত্যাশিত JSON format:

    {
        "ranges": [
            {
                "range": "22896XXX",
                "traffic": 71
            },
            {
                "range": "88017XXX",
                "traffic": 128
            }
        ]
    }

    এখানে phone number, OTP বা SMS content ব্যবহার করা হয় না।
    """

    global TRAFFIC_CACHE
    global CACHE_TIME

    now = time.time()

    with CACHE_LOCK:
        if now - CACHE_TIME < CACHE_SECONDS and TRAFFIC_CACHE:
            return TRAFFIC_CACHE.copy()

    # API দেওয়া না থাকলে zero data
    if not TRAFFIC_API_URL:
        data = {}

        for item in RANGES:
            data[item["id"]] = 0

        with CACHE_LOCK:
            TRAFFIC_CACHE = data
            CACHE_TIME = now

        return data

    try:
        response = requests.get(
            TRAFFIC_API_URL,
            timeout=10
        )

        response.raise_for_status()

        payload = response.json()

        result = {}

        for item in payload.get("ranges", []):
            range_id = str(item.get("range", "")).strip()

            try:
                traffic = int(item.get("traffic", 0))
            except (TypeError, ValueError):
                traffic = 0

            if range_id:
                result[range_id] = max(traffic, 0)

        # Configured ranges যেগুলো API-তে নেই
        # সেগুলো 0 থাকবে
        for item in RANGES:
            result.setdefault(item["id"], 0)

        with CACHE_LOCK:
            TRAFFIC_CACHE = result
            CACHE_TIME = now

        return result

    except Exception as e:
        print("Traffic API error:", e)

        # আগের cache থাকলে সেটা ব্যবহার
        with CACHE_LOCK:
            if TRAFFIC_CACHE:
                return TRAFFIC_CACHE.copy()

        return {
            item["id"]: 0
            for item in RANGES
        }


# =========================================================
# SORT RANGES
# =========================================================

def get_sorted_ranges():
    traffic = get_traffic_data()

    data = []

    for item in RANGES:
        range_id = item["id"]

        data.append({
            "id": range_id,
            "country": item["country"],
            "flag": item["flag"],
            "traffic": traffic.get(range_id, 0)
        })

    data.sort(
        key=lambda x: x["traffic"],
        reverse=True
    )

    return data


# =========================================================
# LIVE TRAFFIC MESSAGE
# =========================================================

def build_live_traffic_message():
    ranges = get_sorted_ranges()

    lines = [
        "📊 <b>LIVE TRAFFIC</b>",
        "",
        "Panel-এর aggregate traffic অনুযায়ী ranking:",
        ""
    ]

    medals = {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }

    for position, item in enumerate(ranges, start=1):

        medal = medals.get(position, f"{position}️⃣")

        lines.append(
            f"{medal} <b>{position}st</b> — "
            f"{item['flag']} {item['country']}"
        )

        lines.append(
            f"   ⚙️ Range: <code>{item['id']}</code>"
        )

        lines.append(
            f"   📈 Traffic: <b>{item['traffic']}</b>"
        )

        lines.append("")

    lines.append(
        "🔄 <i>Refresh চাপলে সর্বশেষ aggregate data দেখা যাবে।</i>"
    )

    return "\n".join(lines)


# =========================================================
# MAIN MENU
# =========================================================

def main_keyboard():

    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)

    live_button = telebot.types.InlineKeyboardButton(
        "📊 Live Traffic",
        callback_data="live_traffic"
    )

    refresh_button = telebot.types.InlineKeyboardButton(
        "🔄 Refresh",
        callback_data="refresh_traffic"
    )

    keyboard.add(
        live_button,
        refresh_button
    )

    return keyboard


# =========================================================
# /START
# =========================================================

@bot.message_handler(commands=["start"])
def start_command(message):

    text = (
        "👋 <b>Welcome</b>\n\n"
        "আপনি নিচের button ব্যবহার করে "
        "panel-এর aggregate range traffic দেখতে পারবেন।\n\n"
        "📊 <b>Live Traffic</b> চাপুন।"
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# /TRAFFIC
# =========================================================

@bot.message_handler(commands=["traffic"])
def traffic_command(message):

    text = build_live_traffic_message()

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# CALLBACK BUTTONS
# =========================================================

@bot.callback_query_handler(
    func=lambda call: call.data in [
        "live_traffic",
        "refresh_traffic"
    ]
)
def traffic_callback(call):

    try:

        # Telegram loading indicator বন্ধ
        bot.answer_callback_query(call.id)

        text = build_live_traffic_message()

        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=main_keyboard()
        )

    except Exception as e:

        print("Callback error:", e)

        try:
            bot.answer_callback_query(
                call.id,
                "Data refresh করা যায়নি। আবার চেষ্টা করুন।",
                show_alert=True
            )
        except Exception:
            pass


# =========================================================
# ERROR-SAFE POLLING
# =========================================================

def run_bot():

    while True:

        try:

            print("Telegram bot started.")

            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30
            )

        except Exception as e:

            print("Bot polling error:", e)

            time.sleep(5)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    run_bot()
