import os
import asyncio
import requests
import re
import time
import threading

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
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
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = os.environ.get("MINO_API_KEY")

BASE_API_URL = "https://minosms.com"

YOUR_TELEGRAM_USERNAME = "smm_otp_grup"
SUPPORT_USERNAME = "tmtamimmia"

OTP_GROUP_CHAT_ID = -1004436883235

DEFAULT_RANGE = "23762XXX"

# কত সেকেন্ডের মধ্যে নতুন SMS এলে active session হিসেবে ধরা হবে
SESSION_TIMEOUT = 20 * 60

# panel কত সেকেন্ড পরপর check করবে
POLL_INTERVAL = 2


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

if not MINO_API_KEY:
    raise RuntimeError("MINO_API_KEY environment variable is missing")


# =========================================================
# MEMORY
# =========================================================

USER_STATES = {}
USER_RANGES = {}
USER_BALANCES = {}
USER_WITHDRAW_INFO = {}

ACTIVE_USER_NUMBERS = {}

# একই SMS বারবার notification না দেওয়ার জন্য
GLOBAL_SEEN_MESSAGES = set()


# =========================================================
# COUNTRY
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

    return "International", "INT", "🌍"


# =========================================================
# NUMBER API
# =========================================================

def _sync_get_number(target_range):
    headers = {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {
        "rid": str(target_range).upper().strip()
    }

    try:
        response = requests.post(
            f"{BASE_API_URL}/getnumber.php",
            headers=headers,
            json=payload,
            timeout=8,
        )

        if response.status_code != 200:
            print("Get Number HTTP:", response.status_code)
            return None, None

        data = response.json()

        body = data.get("data", {})

        if not isinstance(body, dict):
            return None, None

        phone = (
            body.get("full_number")
            or body.get("national_number")
            or body.get("phone")
            or body.get("number")
        )

        order_id = (
            body.get("order_id")
            or body.get("orderId")
            or body.get("id")
            or body.get("order")
        )

        if phone:
            return str(phone), str(order_id or "")

    except Exception as e:
        print("Get Number Error:", e)

    return None, None


async def get_real_number(target_range):
    return await asyncio.to_thread(
        _sync_get_number,
        target_range
    )


# =========================================================
# PANEL CONSOLE
# =========================================================

def _sync_console():
    headers = {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            f"{BASE_API_URL}/console.php",
            headers=headers,
            timeout=8,
        )

        if response.status_code != 200:
            print("Console HTTP:", response.status_code)
            return []

        result = response.json()
        data = result.get("data", [])

        if isinstance(data, list):
            return data

    except Exception as e:
        print("Console Error:", e)

    return []


async def get_console():
    return await asyncio.to_thread(_sync_console)


# =========================================================
# NUMBER NORMALIZER
# =========================================================

def normalize_number(value):
    if not value:
        return ""

    return "".join(
        ch for ch in str(value)
        if ch.isdigit()
    )


# =========================================================
# FIND NUMBER IN PANEL RECORD
# =========================================================

def get_hit_number(hit):
    if not isinstance(hit, dict):
        return ""

    candidates = [
        hit.get("number"),
        hit.get("full_number"),
        hit.get("phone"),
        hit.get("phone_number"),
        hit.get("mobile"),
        hit.get("receiver"),
        hit.get("to"),
    ]

    for value in candidates:
        clean = normalize_number(value)

        if clean:
            return clean

    return ""


# =========================================================
# MESSAGE IDENTIFIER
# =========================================================

def get_message_id(hit, number, message):
    if not isinstance(hit, dict):
        return f"{number}|{message}"

    possible_ids = [
        hit.get("id"),
        hit.get("message_id"),
        hit.get("sms_id"),
        hit.get("log_id"),
        hit.get("uid"),
    ]

    for value in possible_ids:
        if value:
            return str(value)

    return f"{number}|{message}"


# =========================================================
# EXTRACT PANEL TIMESTAMP
# =========================================================

def get_hit_timestamp(hit):
    if not isinstance(hit, dict):
        return 0

    for key in [
        "timestamp",
        "time",
        "created_at",
        "created",
        "date",
        "datetime",
    ]:
        value = hit.get(key)

        if isinstance(value, (int, float)):
            return float(value)

    return 0


# =========================================================
# MATCH NUMBER SAFELY
# =========================================================

def numbers_match(a, b):
    a = normalize_number(a)
    b = normalize_number(b)

    if not a or not b:
        return False

    if a == b:
        return True

    # শেষ ৮ digit match
    if len(a) >= 8 and len(b) >= 8:
        if a[-8:] == b[-8:]:
            return True

    return False


# =========================================================
# LIVE TRAFFIC
# =========================================================

def _sync_live_traffic():
    hits = _sync_console()

    service_data = {}
    total = 0

    for hit in hits:
        if not isinstance(hit, dict):
            continue

        number = get_hit_number(hit)

        if not number:
            continue

        service = str(
            hit.get("service")
            or "SMS"
        ).upper().strip()

        country = str(
            hit.get("country")
            or ""
        ).strip()

        range_value = (
            hit.get("range")
            or hit.get("rid")
            or number[:8]
        )

        country_name, country_code, flag = get_country_info(
            number,
            country
        )

        service_data.setdefault(service, {})
        service_data[service].setdefault(
            country_code,
            {
                "name": country_name,
                "flag": flag,
                "ranges": {},
            }
        )

        ranges = service_data[service][country_code]["ranges"]

        range_value = str(range_value)

        ranges[range_value] = (
            ranges.get(range_value, 0) + 1
        )

        total += 1

    return service_data, total


async def fetch_live_traffic():
    return await asyncio.to_thread(
        _sync_live_traffic
    )


# =========================================================
# SAFE NEW-SMS NOTIFICATION
# =========================================================

async def notify_new_sms(application, user_id, info, hit):
    """
    নিরাপদ notification।
    SMS-এর আসল text বা OTP পাঠানো হয় না।
    """

    phone = info.get("phone", "")
    country = str(hit.get("country") or "")

    country_name, _, flag = get_country_info(
        phone,
        country
    )

    service = str(
        hit.get("service")
        or "SMS"
    ).upper()

    text = (
        "📩 <b>New SMS Received</b>\n\n"
        f"🌍 <b>Country:</b> {flag} {country_name}\n"
        f"📱 <b>Number:</b> <code>{phone}</code>\n"
        f"📡 <b>Service:</b> {service}\n"
        "🔐 <b>Verification code:</b> "
        "not displayed\n\n"
        "✅ This notification belongs to your active number session."
    )

    try:
        await application.bot.send_message(
            chat_id=info["chat_id"],
            text=text,
            parse_mode="HTML",
        )
    except Exception as e:
        print("Personal notification error:", e)


# =========================================================
# GROUP NOTIFICATION
# =========================================================

async def notify_group(application, hit):
    """
    Group-এ শুধু safe notification পাঠানো হয়।
    OTP/SMS body পাঠানো হয় না।
    """

    number = get_hit_number(hit)

    if not number:
        return

    service = str(
        hit.get("service")
        or "SMS"
    ).upper()

    country = str(
        hit.get("country")
        or ""
    )

    country_name, _, flag = get_country_info(
        number,
        country
    )

    text = (
        "🤖 <b>TAMIM OTP BOT</b>\n\n"
        "📩 <b>New SMS Received</b>\n\n"
        f"🌍 <b>Country:</b> {flag} {country_name}\n"
        f"📱 <b>Number:</b> <code>+{number}</code>\n"
        f"📡 <b>Service:</b> {service}\n"
        "🔐 <b>Verification code:</b> not displayed"
    )

    try:
        await application.bot.send_message(
            chat_id=OTP_GROUP_CHAT_ID,
            text=text,
            parse_mode="HTML",
        )

    except Exception as e:
        print(
            "Group Forward Error:",
            repr(e)
        )


# =========================================================
# BACKGROUND PANEL MONITOR
# =========================================================

async def monitor_panel(application):

    print("Panel monitor started.")

    while True:

        try:
            hits = await get_console()

            now = time.time()

            for hit in hits:

                if not isinstance(hit, dict):
                    continue

                number = get_hit_number(hit)

                if not number:
                    continue

                message = (
                    hit.get("message")
                    or hit.get("text")
                    or hit.get("sms")
                    or hit.get("content")
                    or ""
                )

                message = str(message).strip()

                if not message:
                    continue

                # Waiting/placeholder বাদ
                if "waiting" in message.lower():
                    continue

                # -------------------------------------------------
                # পুরোনো SMS global cache
                # -------------------------------------------------

                message_id = get_message_id(
                    hit,
                    number,
                    message
                )

                global_key = str(message_id)

                # -------------------------------------------------
                # ACTIVE USER SESSION MATCH
                # -------------------------------------------------

                for user_id, info in list(
                    ACTIVE_USER_NUMBERS.items()
                ):

                    session_start = info.get(
                        "session_start",
                        0
                    )

                    if now < session_start:
                        continue

                    if now - session_start > SESSION_TIMEOUT:
                        continue

                    user_phone = info.get(
                        "phone",
                        ""
                    )

                    if not numbers_match(
                        user_phone,
                        number
                    ):
                        continue

                    # একই message আবার পাঠানো যাবে না
                    sent_messages = info.setdefault(
                        "sent_messages",
                        set()
                    )

                    if global_key in sent_messages:
                        continue

                    # Session তৈরি হওয়ার আগের cached message বাদ
                    if global_key in info.get(
                        "old_messages",
                        set()
                    ):
                        continue

                    sent_messages.add(global_key)

                    await notify_new_sms(
                        application,
                        user_id,
                        info,
                        hit
                    )

                    # Balance চাইলে notification-এর জন্য
                    # এখানে amount পরিবর্তন করতে পারেন।
                    current_balance = USER_BALANCES.get(
                        user_id,
                        0.0
                    )

                    USER_BALANCES[user_id] = (
                        current_balance + 0.00122
                    )

                # -------------------------------------------------
                # GROUP
                # -------------------------------------------------

                if global_key not in GLOBAL_SEEN_MESSAGES:

                    GLOBAL_SEEN_MESSAGES.add(
                        global_key
                    )

                    if len(GLOBAL_SEEN_MESSAGES) > 5000:
                        GLOBAL_SEEN_MESSAGES.pop()

                    await notify_group(
                        application,
                        hit
                    )

        except Exception as e:
            print(
                "Panel Monitor Error:",
                repr(e)
            )

        await asyncio.sleep(
            POLL_INTERVAL
        )


# =========================================================
# NUMBER BUTTON
# =========================================================

def number_markup(phone):

    _, _, flag = get_country_info(phone)

    keyboard = [
        [
            InlineKeyboardButton(
                f"{flag} +{normalize_number(phone)}",
                callback_data="number_info"
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
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(update, context):

    user_id = update.effective_user.id

    USER_STATES[user_id] = None

    keyboard = [
        ["📞 Get API Number", "⚙ Set Range"],
        ["🟢 Live Traffic", "💳 Balance"],
        ["💬 Support", "📣 OTP Group"],
    ]

    markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 <b>Welcome to TAMIM OTP BOT</b>\n\n"
        "Please select an option:",
        reply_markup=markup,
        parse_mode="HTML"
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update, context):

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
        "সমস্যা হলে নিচের button ব্যবহার করুন।",
        reply_markup=markup,
        parse_mode="HTML"
    )


# =========================================================
# GET NUMBER
# =========================================================

async def send_number(update, user_id):

    wait = await update.message.reply_text(
        "⏳ Panel থেকে real number নেওয়া হচ্ছে..."
    )

    user_range = USER_RANGES.get(
        user_id,
        DEFAULT_RANGE
    )

    phone, order_id = await get_real_number(
        user_range
    )

    try:
        await wait.delete()
    except Exception:
        pass

    if not phone:

        await update.message.reply_text(
            f"❌ <b>No number available</b>\n\n"
            f"Range: <code>{user_range}</code>",
            parse_mode="HTML"
        )

        return

    # -------------------------------------------------
    # নতুন session
    # -------------------------------------------------

    old_hits = await get_console()

    old_messages = set()

    clean_phone = normalize_number(phone)

    for hit in old_hits:

        if not isinstance(hit, dict):
            continue

        hit_number = get_hit_number(hit)

        if not numbers_match(
            clean_phone,
            hit_number
        ):
            continue

        msg = (
            hit.get("message")
            or hit.get("text")
            or hit.get("sms")
            or hit.get("content")
            or ""
        )

        if msg:

            mid = get_message_id(
                hit,
                hit_number,
                str(msg)
            )

            old_messages.add(
                str(mid)
            )

    ACTIVE_USER_NUMBERS[user_id] = {
        "phone": phone,
        "order_id": order_id,
        "chat_id": update.effective_chat.id,

        # এই সময়ের পরের message-ই নতুন
        "session_start": time.time(),

        "old_messages": old_messages,
        "sent_messages": set(),
    }

    country_name, _, flag = get_country_info(phone)

    text = (
        "✅ <b>Number Received</b>\n\n"
        f"🌍 <b>Country:</b> {flag} {country_name}\n"
        f"📱 <b>Number:</b> <code>+{clean_phone}</code>\n"
        f"⚙️ <b>Range:</b> <code>{user_range}</code>\n\n"
        "ℹ️ <b>Number session is active.</b>\n"
        "নতুন SMS এলে এই chat-এ notification আসবে।"
    )

    await update.message.reply_text(
        text,
        reply_markup=number_markup(phone),
        parse_mode="HTML"
    )


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def handle_message(update, context):

    user_id = update.effective_user.id
    text = update.message.text or ""

    state = USER_STATES.get(user_id)

    # RANGE
    if state == "WAITING_FOR_RANGE":

        value = text.strip()

        if len(value) < 3:

            await update.message.reply_text(
                "❌ Invalid range."
            )

            return

        USER_RANGES[user_id] = value
        USER_STATES[user_id] = None

        await update.message.reply_text(
            f"✅ <b>Range updated:</b>\n"
            f"<code>{value}</code>",
            parse_mode="HTML"
        )

        return

    # BKASH
    if state == "WAITING_FOR_BKASH":

        value = text.strip()

        USER_WITHDRAW_INFO[user_id] = (
            f"bKash: {value}"
        )

        USER_STATES[user_id] = None

        await update.message.reply_text(
            "✅ bKash information saved."
        )

        return

    # BINANCE
    if state == "WAITING_FOR_BINANCE":

        value = text.strip()

        USER_WITHDRAW_INFO[user_id] = (
            f"Binance: {value}"
        )

        USER_STATES[user_id] = None

        await update.message.reply_text(
            "✅ Binance information saved."
        )

        return

    # GET NUMBER
    if "Get API Number" in text:

        USER_STATES[user_id] = None

        await send_number(
            update,
            user_id
        )

        return

    # SET RANGE
    if "Set Range" in text:

        USER_STATES[user_id] = (
            "WAITING_FOR_RANGE"
        )

        await update.message.reply_text(
            "⚙️ আপনার target range পাঠান।\n\n"
            "উদাহরণ:\n"
            "<code>23762XXX</code>",
            parse_mode="HTML"
        )

        return

    # LIVE TRAFFIC
    if "Live Traffic" in text:

        USER_STATES[user_id] = None

        service_data, total = (
            await fetch_live_traffic()
        )

        if not service_data:

            await update.message.reply_text(
                "⚠️ বর্তমানে কোনো traffic পাওয়া যায়নি।"
            )

            return

        keyboard = []

        for service in sorted(
            service_data.keys()
        ):

            count = sum(
                sum(c["ranges"].values())
                for c in service_data[service].values()
            )

            keyboard.append([
                InlineKeyboardButton(
                    f"👀 {service.title()} Range ({count})",
                    callback_data=f"tr_svc_{service}"
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

        await update.message.reply_text(
            f"📊 <b>Live Traffic</b>\n\n"
            f"📋 Total: <b>{total}</b>\n\n"
            "Service নির্বাচন করুন:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="HTML"
        )

        return

    # BALANCE
    if "Balance" in text:

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
            f"💳 <b>Balance:</b> "
            f"${balance:.5f}\n"
            f"📂 <b>Payout:</b> {payout}",
            reply_markup=markup,
            parse_mode="HTML"
        )

        return

    # SUPPORT
    if "Support" in text:

        await help_command(
            update,
            context
        )

        return

    # GROUP
    if "OTP Group" in text:

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📣 Join OTP Group",
                    url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}"
                )
            ]
        ])

        await update.message.reply_text(
            "📣 Official group:",
            reply_markup=markup
        )

        return


# =========================================================
# CALLBACK
# =========================================================

async def handle_callback(update, context):

    query = update.callback_query

    await query.answer()

    data = query.data
    user_id = query.from_user.id

    # BACK
    if data == "back_home":

        try:
            await query.message.delete()
        except Exception:
            pass

        # callback-এর ক্ষেত্রে start-এর বদলে
        # নতুন menu পাঠানো
        keyboard = [
            ["📞 Get API Number", "⚙ Set Range"],
            ["🟢 Live Traffic", "💳 Balance"],
            ["💬 Support", "📣 OTP Group"],
        ]

        await query.message.chat.send_message(
            "🏠 <b>Main Menu</b>",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )

        return

    # NUMBER INFO
    if data == "number_info":

        info = ACTIVE_USER_NUMBERS.get(
            user_id
        )

        if not info:

            await query.answer(
                "No active number.",
                show_alert=True
            )

            return

        await query.answer(
            "Number session is active."
        )

        return

    # CHANGE NUMBER
    if data == "change_number":

        await query.answer(
            "🔄 নতুন number নেওয়া হচ্ছে..."
        )

        user_range = USER_RANGES.get(
            user_id,
            DEFAULT_RANGE
        )

        phone, order_id = await get_real_number(
            user_range
        )

        if not phone:

            await query.answer(
                "❌ No number available.",
                show_alert=True
            )

            return

        # পুরোনো message snapshot
        hits = await get_console()

        old_messages = set()

        clean_phone = normalize_number(phone)

        for hit in hits:

            if not isinstance(hit, dict):
                continue

            hit_number = get_hit_number(hit)

            if not numbers_match(
                clean_phone,
                hit_number
            ):
                continue

            msg = (
                hit.get("message")
                or hit.get("text")
                or hit.get("sms")
                or hit.get("content")
                or ""
            )

            if msg:

                mid = get_message_id(
                    hit,
                    hit_number,
                    str(msg)
                )

                old_messages.add(
                    str(mid)
                )

        ACTIVE_USER_NUMBERS[user_id] = {
            "phone": phone,
            "order_id": order_id,
            "chat_id": query.message.chat_id,
            "session_start": time.time(),
            "old_messages": old_messages,
            "sent_messages": set(),
        }

        country_name, _, flag = (
            get_country_info(phone)
        )

        text = (
            "🔄 <b>New Number Received</b>\n\n"
            f"🌍 <b>Country:</b> {flag} {country_name}\n"
            f"📱 <b>Number:</b> "
            f"<code>+{clean_phone}</code>\n"
            f"⚙️ <b>Range:</b> "
            f"<code>{user_range}</code>\n\n"
            "ℹ️ New SMS notification is active."
        )

        try:

            await query.edit_message_text(
                text,
                reply_markup=number_markup(phone),
                parse_mode="HTML"
            )

        except Exception:

            await query.message.reply_text(
                text,
                reply_markup=number_markup(phone),
                parse_mode="HTML"
            )

        return

    # LIVE SERVICE
    if data.startswith("tr_svc_"):

        service = data.replace(
            "tr_svc_",
            "",
            1
        )

        service_data, _ = (
            await fetch_live_traffic()
        )

        if service not in service_data:

            await query.answer(
                "No data.",
                show_alert=True
            )

            return

        keyboard = []

        countries = service_data[service]

        for code, info in sorted(
            countries.items(),
            key=lambda item:
            sum(item[1]["ranges"].values()),
            reverse=True
        ):

            count = sum(
                info["ranges"].values()
            )

            keyboard.append([
                InlineKeyboardButton(
                    f"{info['flag']} "
                    f"{info['name']} "
                    f"({count})",
                    callback_data=(
                        f"tr_cnt_{service}_{code}"
                    )
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="tr_main"
            )
        ])

        await query.edit_message_text(
            f"👑 <b>{service}</b>\n\n"
            "Country নির্বাচন করুন:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="HTML"
        )

        return

    # LIVE COUNTRY
    if data.startswith("tr_cnt_"):

        parts = data.split("_", 3)

        if len(parts) < 4:
            return

        service = parts[2]
        country_code = parts[3]

        service_data, _ = (
            await fetch_live_traffic()
        )

        if (
            service not in service_data
            or country_code not in service_data[service]
        ):
            return

        info = service_data[
            service
        ][country_code]

        keyboard = []

        for range_value, count in sorted(
            info["ranges"].items(),
            key=lambda item: item[1],
            reverse=True
        ):

            keyboard.append([
                InlineKeyboardButton(
                    f"🎛 {range_value} ({count})",
                    callback_data="range_info"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔙 Back",
                callback_data=f"tr_svc_{service}"
            )
        ])

        await query.edit_message_text(
            f"👑 <b>Ranges</b>\n\n"
            f"🌐 Service: {service}\n"
            f"{info['flag']} "
            f"{info['name']}\n\n"
            "Range list:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="HTML"
        )

        return

    # LIVE MAIN / REFRESH
    if data in [
        "tr_main",
        "tr_refresh"
    ]:

        service_data, total = (
            await fetch_live_traffic()
        )

        keyboard = []

        for service in sorted(
            service_data.keys()
        ):

            count = sum(
                sum(c["ranges"].values())
                for c in service_data[service].values()
            )

            keyboard.append([
                InlineKeyboardButton(
                    f"👀 {service.title()} ({count})",
                    callback_data=f"tr_svc_{service}"
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

        await query.edit_message_text(
            f"📊 <b>Live Traffic</b>\n\n"
            f"📋 Total: <b>{total}</b>",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="HTML"
        )

        return

    # CLOSE
    if data == "tr_close":

        try:
            await query.message.delete()
        except Exception:
            pass

        return

    # BKASH
    if data == "set_bkash":

        USER_STATES[user_id] = (
            "WAITING_FOR_BKASH"
        )

        await query.message.reply_text(
            "📱 আপনার bKash number পাঠান:"
        )

        return

    # BINANCE
    if data == "set_binance":

        USER_STATES[user_id] = (
            "WAITING_FOR_BINANCE"
        )

        await query.message.reply_text(
            "🔴 আপনার Binance ID পাঠান:"
        )

        return

    # WITHDRAW
    if data == "withdraw_menu":

        balance = USER_BALANCES.get(
            user_id,
            0.0
        )

        if balance < 1.0:

            await query.message.reply_text(
                f"❌ Minimum withdraw: $1.00\n"
                f"Current: ${balance:.5f}"
            )

            return

        USER_BALANCES[user_id] = 0.0

        await query.message.reply_text(
            "✅ Withdraw request submitted."
        )

        return


# =========================================================
# POST INIT
# =========================================================

async def post_init(application):

    application.create_task(
        monitor_panel(application)
    )

    print("Bot started successfully.")


# =========================================================
# HEALTH SERVER
# =========================================================

from http.server import (
    HTTPServer,
    BaseHTTPRequestHandler
)


class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain"
        )
        self.end_headers()

        self.wfile.write(
            b"Tamim OTP Bot is running."
        )

    def do_HEAD(self):

        self.send_response(200)
        self.end_headers()


def run_health_server():

    port = int(
        os.environ.get(
            "PORT",
            "8080"
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(
        f"Health server running on port {port}"
    )

    server.serve_forever()


# =========================================================
# MAIN
# =========================================================

def main():

    threading.Thread(
        target=run_health_server,
        daemon=True
    ).start()

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            handle_callback
        )
    )

    print("Starting Telegram bot...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
