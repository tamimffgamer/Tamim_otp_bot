import os
import asyncio
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    CopyTextButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = os.environ.get("MINO_API_KEY")

BASE_API_URL = "https://minosms.com"

YOUR_TELEGRAM_USERNAME = "smm_otp_grup"
SUPPORT_USERNAME = "tmtamimmia"

# Your Telegram group
OTP_GROUP_CHAT_ID = -1004436883235

DEFAULT_RANGE = "23762XXX"


# =========================================================
# BASIC CHECK
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in Render Environment Variables.")

if not MINO_API_KEY:
    raise RuntimeError("MINO_API_KEY is missing in Render Environment Variables.")


# =========================================================
# USER DATA
# =========================================================

USER_STATES = {}
USER_RANGES = {}
USER_BALANCES = {}
USER_WITHDRAW_INFO = {}

# user_id -> active number information
ACTIVE_USER_NUMBERS = {}


# =========================================================
# COUNTRY INFORMATION
# =========================================================

def get_country_info(phone_number, api_country=""):
    clean_num = str(phone_number).replace("+", "").strip()

    if api_country:
        c = str(api_country).lower()

        if "madagascar" in c:
            return "Madagascar", "MG", "🇲🇬"

        if "ivory" in c or "côte" in c or "cote" in c:
            return "Ivory Coast", "CI", "🇨🇮"

        if "cameroon" in c:
            return "Cameroon", "CM", "🇨🇲"

        if "togo" in c:
            return "Togo", "TG", "🇹🇬"

        if "benin" in c:
            return "Benin", "BJ", "🇧🇯"

        if "tanzania" in c:
            return "Tanzania", "TZ", "🇹🇿"

        if "ukraine" in c:
            return "Ukraine", "UA", "🇺🇦"

        if "kyrgyzstan" in c:
            return "Kyrgyzstan", "KG", "🇰🇬"

    if clean_num.startswith("880"):
        return "Bangladesh", "BD", "🇧🇩"

    if clean_num.startswith("237"):
        return "Cameroon", "CM", "🇨🇲"

    if clean_num.startswith("225"):
        return "Ivory Coast", "CI", "🇨🇮"

    if clean_num.startswith("228"):
        return "Togo", "TG", "🇹🇬"

    if clean_num.startswith("261"):
        return "Madagascar", "MG", "🇲🇬"

    if clean_num.startswith("229"):
        return "Benin", "BJ", "🇧🇯"

    if clean_num.startswith("255"):
        return "Tanzania", "TZ", "🇹🇿"

    if clean_num.startswith("380"):
        return "Ukraine", "UA", "🇺🇦"

    if clean_num.startswith("996"):
        return "Kyrgyzstan", "KG", "🇰🇬"

    return "International", "INT", "🌍"


# =========================================================
# MINO API - GET NUMBER
# =========================================================

def _sync_get_mino_real_number(target_range):

    headers = {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    clean_rid = str(target_range).upper().strip()

    payload = {
        "rid": clean_rid
    }

    try:
        response = requests.post(
            f"{BASE_API_URL}/getnumber.php",
            headers=headers,
            json=payload,
            timeout=10,
        )

        print("GET NUMBER STATUS:", response.status_code)
        print("GET NUMBER RESPONSE:", response.text[:1000])

        if response.status_code != 200:
            return None, None

        try:
            data_json = response.json()
        except Exception:
            return None, None

        data = data_json.get("data", {})

        if not isinstance(data, dict):
            data = {}

        phone = (
            data.get("full_number")
            or data.get("national_number")
            or data.get("phone")
            or data.get("number")
        )

        if phone:
            return str(phone), clean_rid

    except Exception as e:
        print("MINO GET NUMBER ERROR:", e)

    return None, None


async def get_mino_real_number(target_range):
    return await asyncio.to_thread(
        _sync_get_mino_real_number,
        target_range
    )


# =========================================================
# LIVE TRAFFIC
# =========================================================

def _sync_fetch_live_traffic():

    headers = {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            f"{BASE_API_URL}/console.php",
            headers=headers,
            timeout=10,
        )

        print("CONSOLE STATUS:", response.status_code)

        if response.status_code != 200:
            return [], 0

        try:
            data = response.json()
        except Exception:
            return [], 0

        hits = data.get("data", [])

        if not isinstance(hits, list):
            return [], 0

        return hits, len(hits)

    except Exception as e:
        print("LIVE TRAFFIC ERROR:", e)

    return [], 0


async def fetch_live_traffic():
    return await asyncio.to_thread(_sync_fetch_live_traffic)


# =========================================================
# BUILD TRAFFIC DATA
# =========================================================

def build_traffic_data(hits):

    service_data = {}

    for hit in hits:

        if not isinstance(hit, dict):
            continue

        service = str(
            hit.get("service")
            or "SMS"
        ).upper().strip()

        country = str(
            hit.get("country")
            or ""
        ).strip()

        number_or_range = (
            hit.get("range")
            or hit.get("number")
            or hit.get("full_number")
            or hit.get("phone")
            or ""
        )

        if not number_or_range:
            continue

        value = str(number_or_range).strip()

        country_name, country_code, flag = get_country_info(
            value,
            country
        )

        if service not in service_data:
            service_data[service] = {}

        if country_code not in service_data[service]:
            service_data[service][country_code] = {
                "name": country_name,
                "flag": flag,
                "ranges": {}
            }

        ranges = service_data[service][country_code]["ranges"]

        ranges[value] = ranges.get(value, 0) + 1

    return service_data


# =========================================================
# NUMBER BUTTON
# =========================================================

def create_number_markup(phone_number):

    _, _, flag = get_country_info(phone_number)

    keyboard = [

        [
            InlineKeyboardButton(
                text=f"{flag} {phone_number}",
                copy_text=CopyTextButton(text=str(phone_number))
            )
        ],

        [
            InlineKeyboardButton(
                "🔔 OTP GROUP",
                url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}"
            ),

            InlineKeyboardButton(
                "🔄 Change",
                callback_data="change_number"
            )
        ],

        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back_home"
            )
        ]

    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    USER_STATES[user_id] = None

    keyboard = [

        ["📞 Get API Number", "⚙ Set Range"],

        ["🟢 Live Traffic", "💳 Balance"],

        ["💬 Support", "📣 OTP Group"]

    ]

    markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 <b>Welcome to MINO SMS Number Bot!</b>\n\n"
        "নিচের মেনু থেকে একটি অপশন নির্বাচন করুন।",
        reply_markup=markup,
        parse_mode="HTML"
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📞 Support",
                url=f"https://t.me/{SUPPORT_USERNAME}"
            )
        ]
    ])

    await update.message.reply_text(
        "💬 <b>Support Center</b>\n\n"
        "সমস্যা হলে নিচের বাটনে যোগাযোগ করুন।",
        reply_markup=markup,
        parse_mode="HTML"
    )


# =========================================================
# GET NUMBER
# =========================================================

async def handle_get_number(update, user_id):

    wait_message = await update.message.reply_text(
        "⏳ <b>MINO panel থেকে number নেওয়া হচ্ছে...</b>",
        parse_mode="HTML"
    )

    user_range = USER_RANGES.get(
        user_id,
        DEFAULT_RANGE
    )

    phone, used_range = await get_mino_real_number(
        user_range
    )

    try:
        await wait_message.delete()
    except Exception:
        pass

    if not phone:

        await update.message.reply_text(
            f"❌ <b>এই range-এ কোনো number পাওয়া যায়নি।</b>\n\n"
            f"Range: <code>{user_range}</code>",
            parse_mode="HTML"
        )

        return

    ACTIVE_USER_NUMBERS[user_id] = {
        "phone": phone,
        "range": used_range,
        "chat_id": update.effective_chat.id,
    }

    country_name, country_code, flag = get_country_info(phone)

    markup = create_number_markup(phone)

    text = (
        "✅ <b>Number Successfully Allocated</b>\n\n"
        f"🌍 <b>Country:</b> {flag} {country_name}\n"
        f"🔢 <b>Number:</b> <code>{phone}</code>\n"
        f"⚙️ <b>Range:</b> <code>{used_range}</code>\n\n"
        "🔄 নতুন number নিতে <b>Change</b> চাপুন।"
    )

    await update.message.reply_text(
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        user_id = update.effective_user.id
        text = (update.message.text or "").strip()

        state = USER_STATES.get(user_id)

        # ---------------------------------------------
        # RANGE INPUT
        # ---------------------------------------------

        if state == "WAITING_FOR_RANGE":

            if len(text) < 3:

                await update.message.reply_text(
                    "❌ Invalid range.\n"
                    "উদাহরণ: <code>23762XXX</code>",
                    parse_mode="HTML"
                )

                return

            USER_RANGES[user_id] = text.upper()
            USER_STATES[user_id] = None

            await update.message.reply_text(
                f"✅ <b>Range Updated</b>\n\n"
                f"New Range: <code>{text.upper()}</code>",
                parse_mode="HTML"
            )

            return

        # ---------------------------------------------
        # BKASH
        # ---------------------------------------------

        if state == "WAITING_FOR_BKASH":

            USER_WITHDRAW_INFO[user_id] = (
                f"bKash: {text}"
            )

            USER_STATES[user_id] = None

            await update.message.reply_text(
                f"✅ bKash information saved:\n"
                f"<code>{text}</code>",
                parse_mode="HTML"
            )

            return

        # ---------------------------------------------
        # BINANCE
        # ---------------------------------------------

        if state == "WAITING_FOR_BINANCE":

            USER_WITHDRAW_INFO[user_id] = (
                f"Binance ID: {text}"
            )

            USER_STATES[user_id] = None

            await update.message.reply_text(
                f"✅ Binance information saved:\n"
                f"<code>{text}</code>",
                parse_mode="HTML"
            )

            return

        # ---------------------------------------------
        # GET NUMBER
        # ---------------------------------------------

        if text == "📞 Get API Number":

            USER_STATES[user_id] = None

            await handle_get_number(
                update,
                user_id
            )

            return

        # ---------------------------------------------
        # SET RANGE
        # ---------------------------------------------

        if text == "⚙ Set Range":

            USER_STATES[user_id] = "WAITING_FOR_RANGE"

            current_range = USER_RANGES.get(
                user_id,
                DEFAULT_RANGE
            )

            await update.message.reply_text(
                "⚙️ <b>Set Number Range</b>\n\n"
                f"বর্তমান range: <code>{current_range}</code>\n\n"
                "নতুন range পাঠান।\n"
                "উদাহরণ: <code>23762XXX</code>",
                parse_mode="HTML"
            )

            return

        # ---------------------------------------------
        # LIVE TRAFFIC
        # ---------------------------------------------

        if text == "🟢 Live Traffic":

            USER_STATES[user_id] = None

            hits, total = await fetch_live_traffic()

            if not hits:

                await update.message.reply_text(
                    "⚠️ বর্তমানে কোনো traffic পাওয়া যায়নি।"
                )

                return

            service_data = build_traffic_data(hits)

            if not service_data:

                await update.message.reply_text(
                    "⚠️ Traffic data পাওয়া গেছে, "
                    "কিন্তু display করার মতো range নেই।"
                )

                return

            keyboard = []

            for service in sorted(service_data):

                total_service = 0

                for country_data in service_data[service].values():

                    total_service += sum(
                        country_data["ranges"].values()
                    )

                keyboard.append([
                    InlineKeyboardButton(
                        f"👀 {service.title()} ({total_service})",
                        callback_data=f"tr_svc_{service[:30]}"
                    )
                ])

            keyboard.append([
                InlineKeyboardButton(
                    "🔄 Refresh",
                    callback_data="tr_refresh"
                ),
                InlineKeyboardButton(
                    "❌ Close",
                    callback_data="tr_close"
                )
            ])

            markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"📊 <b>Live Traffic</b>\n\n"
                f"📋 Total records: <b>{total}</b>\n\n"
                "একটি service নির্বাচন করুন:",
                reply_markup=markup,
                parse_mode="HTML"
            )

            return

        # ---------------------------------------------
        # BALANCE
        # ---------------------------------------------

        if text == "💳 Balance":

            USER_STATES[user_id] = None

            balance = USER_BALANCES.get(
                user_id,
                0.0
            )

            payout = USER_WITHDRAW_INFO.get(
                user_id,
                "Not Set"
            )

            markup = InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "💸 Withdraw",
                        callback_data="withdraw_menu"
                    )
                ],

                [
                    InlineKeyboardButton(
                        "📱 Set bKash",
                        callback_data="set_bkash"
                    ),

                    InlineKeyboardButton(
                        "🔴 Set Binance",
                        callback_data="set_binance"
                    )
                ]

            ])

            await update.message.reply_text(
                f"💳 <b>Your Balance</b>\n\n"
                f"💰 Balance: <code>${balance:.5f}</code>\n"
                f"📂 Payout: <code>{payout}</code>",
                reply_markup=markup,
                parse_mode="HTML"
            )

            return

        # ---------------------------------------------
        # SUPPORT
        # ---------------------------------------------

        if text == "💬 Support":

            await help_command(
                update,
                context
            )

            return

        # ---------------------------------------------
        # OTP GROUP
        # ---------------------------------------------

        if text == "📣 OTP Group":

            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📣 Join Group",
                        url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}"
                    )
                ]
            ])

            await update.message.reply_text(
                "📣 Group link:",
                reply_markup=markup
            )

            return

    except Exception as e:

        print(
            "MESSAGE HANDLER ERROR:",
            repr(e)
        )

        try:
            await update.message.reply_text(
                "❌ একটি technical error হয়েছে। "
                "কিছুক্ষণ পরে আবার চেষ্টা করুন।"
            )
        except Exception:
            pass


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id
    data = query.data

    try:

        # ---------------------------------------------
        # BACK HOME
        # ---------------------------------------------

        if data == "back_home":

            try:
                await query.message.delete()
            except Exception:
                pass

            keyboard = [
                ["📞 Get API Number", "⚙ Set Range"],
                ["🟢 Live Traffic",
