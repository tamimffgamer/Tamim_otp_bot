import os
import asyncio
import requests
import time
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
    filters,
    ContextTypes,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = os.environ.get("MINO_API_KEY")

BASE_API_URL = "https://minosms.com"
YOUR_TELEGRAM_USERNAME = "smm_otp_grup"
SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_CHAT_ID = -1004436883235

USER_STATES = {}
USER_RANGES = {}
USER_BALANCES = {}
USER_WITHDRAW_INFO = {}
ACTIVE_USER_NUMBERS = {}
GLOBAL_SEEN_EVENTS = set()


def get_country_info(phone_number, api_country=""):
    clean = str(phone_number).replace("+", "").strip()

    country = api_country.lower()

    if "madagascar" in country:
        return "Madagascar", "MG", "🇲🇬"
    if "ivory" in country or "côte" in country:
        return "Ivory Coast", "CI", "🇨🇮"
    if "cameroon" in country:
        return "Cameroon", "CM", "🇨🇲"
    if "togo" in country:
        return "Togo", "TG", "🇹🇬"
    if "benin" in country:
        return "Benin", "BJ", "🇧🇯"
    if "tanzania" in country:
        return "Tanzania", "TZ", "🇹🇿"
    if "ukraine" in country:
        return "Ukraine", "UA", "🇺🇦"
    if "kyrgyzstan" in country:
        return "Kyrgyzstan", "KG", "🇰🇬"

    if clean.startswith("880"):
        return "Bangladesh", "BD", "🇧🇩"
    if clean.startswith("237"):
        return "Cameroon", "CM", "🇨🇲"
    if clean.startswith("225"):
        return "Ivory Coast", "CI", "🇨🇮"
    if clean.startswith("228"):
        return "Togo", "TG", "🇹🇬"
    if clean.startswith("261"):
        return "Madagascar", "MG", "🇲🇬"

    return "International", "INT", "🌍"


def api_headers():
    return {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def sync_get_number(target_range):
    if not MINO_API_KEY:
        print("MINO_API_KEY is missing")
        return None

    try:
        response = requests.post(
            f"{BASE_API_URL}/getnumber.php",
            headers=api_headers(),
            json={"rid": str(target_range).strip()},
            timeout=8,
        )

        if response.status_code != 200:
            print("Number API status:", response.status_code)
            return None

        data = response.json().get("data", {})

        phone = (
            data.get("full_number")
            or data.get("national_number")
            or data.get("phone")
            or data.get("number")
        )

        if not phone:
            return None

        return str(phone)

    except Exception as exc:
        print("Number API error:", exc)
        return None


async def get_real_number(target_range):
    return await asyncio.to_thread(sync_get_number, target_range)


def sync_live_traffic():
    result = {}
    total = 0

    if not MINO_API_KEY:
        return result, total

    try:
        response = requests.get(
            f"{BASE_API_URL}/console.php",
            headers=api_headers(),
            timeout=8,
        )

        if response.status_code != 200:
            return result, total

        data = response.json().get("data", [])

        if not isinstance(data, list):
            return result, total

        total = len(data)

        for item in data:
            if not isinstance(item, dict):
                continue

            range_value = (
                item.get("range")
                or item.get("number")
                or item.get("full_number")
            )

            if not range_value:
                continue

            service = str(
                item.get("service") or "SMS"
            ).upper().strip()

            country = item.get("country", "")

            name, code, flag = get_country_info(
                range_value,
                country,
            )

            result.setdefault(service, {})
            result[service].setdefault(
                code,
                {
                    "name": name,
                    "flag": flag,
                    "ranges": {},
                },
            )

            ranges = result[service][code]["ranges"]
            ranges[str(range_value)] = (
                ranges.get(str(range_value), 0) + 1
            )

    except Exception as exc:
        print("Traffic error:", exc)

    return result, total


async def live_traffic():
    return await asyncio.to_thread(sync_live_traffic)


def number_markup(phone):
    _, _, flag = get_country_info(phone)

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{flag} {phone}",
                copy_text=CopyTextButton(text=str(phone)),
            )
        ],
        [
            InlineKeyboardButton(
                "🔔 OTP GROUP",
                url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}",
            ),
            InlineKeyboardButton(
                "🔄 Change",
                callback_data="change_number",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back_home",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_STATES[user_id] = None

    keyboard = [
        ["📞 Get API Number", "⚙ Set Range"],
        ["🟢 Live Traffic", "💳 Balance"],
        ["💬 Support", "📣 OTP Group"],
    ]

    await update.message.reply_text(
        "Welcome to MINO SMS Number Bot 🤖\n\n"
        "Please select an option:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📞 Support",
                url=f"https://t.me/{SUPPORT_USERNAME}",
            )
        ]
    ])

    await update.message.reply_text(
        "💬 <b>Support Center</b>\n\n"
        "যেকোনো সমস্যার জন্য নিচের বাটনে যোগাযোগ করুন।",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    state = USER_STATES.get(user_id)

    if state == "WAITING_FOR_RANGE":
        if len(text) < 3:
            await update.message.reply_text(
                "❌ Invalid range."
            )
            return

        USER_RANGES[user_id] = text
        USER_STATES[user_id] = None

        await update.message.reply_text(
            f"✅ Range set to:\n<code>{text}</code>",
            parse_mode="HTML",
        )
        return

    if state == "WAITING_FOR_BKASH":
        USER_WITHDRAW_INFO[user_id] = f"bKash: {text}"
        USER_STATES[user_id] = None

        await update.message.reply_text(
            "✅ bKash information saved."
        )
        return

    if state == "WAITING_FOR_BINANCE":
        USER_WITHDRAW_INFO[user_id] = f"Binance: {text}"
        USER_STATES[user_id] = None

        await update.message.reply_text(
            "✅ Binance information saved."
        )
        return

    if text == "📞 Get API Number":
        target_range = USER_RANGES.get(
            user_id,
            "23762XXX",
        )

        wait = await update.message.reply_text(
            "⏳ Fetching number..."
        )

        phone = await get_real_number(target_range)

        try:
            await wait.delete()
        except Exception:
            pass

        if not phone:
            await update.message.reply_text(
                f"❌ No number available for "
                f"<code>{target_range}</code>.",
                parse_mode="HTML",
            )
            return

        ACTIVE_USER_NUMBERS[user_id] = {
            "phone": phone,
            "chat_id": update.effective_chat.id,
            "created_at": time.time(),
            "event_ids": set(),
        }

        name, _, flag = get_country_info(phone)

        await update.message.reply_text(
            f"✅ <b>Number Received</b>\n\n"
            f"🌍 Country: {flag} {name}\n"
            f"📱 Number: <code>{phone}</code>\n"
            f"⚙️ Range: <code>{target_range}</code>\n\n"
            f"ℹ️ Number is now active.",
            reply_markup=number_markup(phone),
            parse_mode="HTML",
        )

        return

    if text == "⚙ Set Range":
        USER_STATES[user_id] = "WAITING_FOR_RANGE"

        await update.message.reply_text(
            "⚙️ Send your target range.\n\n"
            "Example:\n"
            "<code>23762XXX</code>",
            parse_mode="HTML",
        )
        return

    if text == "🟢 Live Traffic":
        data, total = await live_traffic()

        if not data:
            await update.message.reply_text(
                "⚠️ No active traffic found."
            )
            return

        keyboard = []

        for service in sorted(data):
            count = sum(
                sum(country["ranges"].values())
                for country in data[service].values()
            )

            keyboard.append([
                InlineKeyboardButton(
                    f"👀 {service.title()} Range ({count})",
                    callback_data=f"traffic_service:{service}",
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="traffic_refresh",
            ),
            InlineKeyboardButton(
                "❌ Close",
                callback_data="traffic_close",
            ),
        ])

        await update.message.reply_text(
            f"📊 <b>Live Traffic</b>\n\n"
            f"📋 Total Events: <b>{total}</b>\n\n"
            f"Select service:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if text == "💳 Balance":
        balance = USER_BALANCES.get(user_id, 0.0)
        payout = USER_WITHDRAW_INFO.get(
            user_id,
            "Not Set",
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "💸 Withdraw",
                    callback_data="withdraw",
                )
            ],
            [
                InlineKeyboardButton(
                    "📱 Set bKash",
                    callback_data="set_bkash",
                ),
                InlineKeyboardButton(
                    "🔴 Set Binance",
                    callback_data="set_binance",
                ),
            ],
        ])

        await update.message.reply_text(
            f"💳 <b>Balance:</b> ${balance:.5f}\n"
            f"📂 <b>Payout:</b> {payout}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    if text == "💬 Support":
        await help_command(update, context)
        return

    if text == "📣 OTP Group":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📣 Join Group",
                    url=f"https://t.me/{YOUR_TELEGRAM_USERNAME}",
                )
            ]
        ])

        await update.message.reply_text(
            "📣 Official group:",
            reply_markup=keyboard,
        )


async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "back_home":
        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        await start(update, context)
        return

    if data == "change_number":
        await query.answer("Fetching new number...")

        target_range = USER_RANGES.get(
            user_id,
            "23762XXX",
        )

        phone = await get_real_number(target_range)

        if not phone:
            await query.answer(
                "No stock available.",
                show_alert=True,
            )
            return

        ACTIVE_USER_NUMBERS[user_id] = {
            "phone": phone,
            "chat_id": query.message.chat_id,
            "created_at": time.time(),
            "event_ids": set(),
        }

        name, _, flag = get_country_info(phone)

        await query.edit_message_text(
            f"✅ <b>New Number</b>\n\n"
            f"🌍 Country: {flag} {name}\n"
            f"📱 Number: <code>{phone}</code>\n"
            f"⚙️ Range: <code>{target_range}</code>",
            reply_markup=number_markup(phone),
            parse_mode="HTML",
        )
        return

    if data.startswith("traffic_service:"):
        await query.answer()

        service = data.split(":", 1)[1]
        traffic, _ = await live_traffic()

        if service not in traffic:
            await query.answer(
                "No data available.",
                show_alert=True,
            )
            return

        keyboard = []

        for code, info in sorted(
            traffic[service].items(),
            key=lambda x: sum(x[1]["ranges"].values()),
            reverse=True,
        ):
            count = sum(info["ranges"].values())

            keyboard.append([
                InlineKeyboardButton(
                    f"{info['flag']} {info['name']} "
                    f"({code}) - {count}",
                    callback_data=f"traffic_country:{service}:{code}",
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="traffic_main",
            )
        ])

        await query.edit_message_text(
            f"👑 <b>{service}</b>\n\n"
            f"Select country:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if data.startswith("traffic_country:"):
        await query.answer()

        _, service, code = data.split(":", 2)

        traffic, _ = await live_traffic()

        if (
            service not in traffic
            or code not in traffic[service]
        ):
            return

        info = traffic[service][code]

        keyboard = []

        for range_value, count in sorted(
            info["ranges"].items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            keyboard.append([
                InlineKeyboardButton(
                    f"🎛 {range_value} ({count})",
                    copy_text=CopyTextButton(
                        text=str(range_value)
                    ),
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔙 Back",
                callback_data=f"traffic_service:{service}",
            )
        ])

        await query.edit_message_text(
            f"👑 <b>Ranges</b>\n\n"
            f"🌍 {info['flag']} {info['name']}\n\n"
            f"Click to copy:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if data in ("traffic_main", "traffic_refresh"):
        await query.answer("🔄 Refreshed")

        traffic, total = await live_traffic()

        keyboard = []

        for service in sorted(traffic):
            count = sum(
                sum(country["ranges"].values())
                for country in traffic[service].values()
            )

            keyboard.append([
                InlineKeyboardButton(
                    f"👀 {service.title()} ({count})",
                    callback_data=f"traffic_service:{service}",
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="traffic_refresh",
            ),
            InlineKeyboardButton(
                "❌ Close",
                callback_data="traffic_close",
            ),
        ])

        await query.edit_message_text(
            f"📊 <b>Live Traffic</b>\n\n"
            f"📋 Total Events: <b>{total}</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if data == "traffic_close":
        await query.answer()

        try:
            await query.message.delete()
        except Exception:
            pass

        return

    if data == "set_bkash":
        USER_STATES[user_id] = "WAITING_FOR_BKASH"

        await query.answer()
        await query.message.reply_text(
            "📱 Send your bKash number:"
        )
        return

    if data == "set_binance":
        USER_STATES[user_id] = "WAITING_FOR_BINANCE"

        await query.answer()
        await query.message.reply_text(
            "🔴 Send your Binance ID:"
        )
        return

    if data == "withdraw":
        await query.answer()

        balance = USER_BALANCES.get(user_id, 0.0)

        if balance < 1.0:
            await query.message.reply_text(
                f"❌ Minimum withdrawal: $1.00\n"
                f"Current balance: ${balance:.5f}"
            )
            return

        await query.message.reply_text(
            "✅ Withdrawal request received."
        )
        return


def validate_environment():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    if not MINO_API_KEY:
        raise RuntimeError(
            "MINO_API_KEY environment variable is missing."
        )


if __name__ == "__main__":
    validate_environment()

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    app.add_handler(
        CallbackQueryHandler(callback_handler)
    )

    app.run_polling(
        drop_pending_updates=True
    )
