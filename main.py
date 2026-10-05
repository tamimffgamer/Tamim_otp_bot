import os
import asyncio
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    CopyTextButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Render/Redar/GitHub environment variable-এ নতুন MINO API key দিন
MINO_API_KEY = os.environ.get("MINO_API_KEY")

MINO_BASE_URL = "https://minosms.com"

# আপনার support
SUPPORT_USERNAME = "tmtamimmia"

# আপনার OTP group link
OTP_GROUP_USERNAME = "smm_otp_grup"

# =========================================================
# USER DATA
# =========================================================

USER_STATES = {}
USER_RANGES = {}


# =========================================================
# COUNTRY
# =========================================================

def get_country_info(phone_number):
    clean_num = str(phone_number).replace("+", "").strip()

    if clean_num.startswith("237"):
        return "Cameroon", "CM", "🇨🇲"

    elif clean_num.startswith("225"):
        return "Ivory Coast", "CI", "🇨🇮"

    elif clean_num.startswith("228"):
        return "Togo", "TG", "🇹🇬"

    elif clean_num.startswith("229"):
        return "Benin", "BJ", "🇧🇯"

    elif clean_num.startswith("255"):
        return "Tanzania", "TZ", "🇹🇿"

    elif clean_num.startswith("266"):
        return "Lesotho", "LS", "🇱🇸"

    elif clean_num.startswith("380"):
        return "Ukraine", "UA", "🇺🇦"

    elif clean_num.startswith("224"):
        return "Guinea", "GN", "🇬🇳"

    elif clean_num.startswith("996"):
        return "Kyrgyzstan", "KG", "🇰🇬"

    elif clean_num.startswith("43"):
        return "Austria", "AT", "🇦🇹"

    else:
        return "Unknown", "XX", "🌐"


# =========================================================
# MINO SMS - GET NUMBER
# =========================================================

def _sync_get_mino_number(target_range):

    if not MINO_API_KEY:
        print("MINO_API_KEY is missing")
        return None, None

    headers = {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # যেমন 88017XXX -> 88017
    clean_rid = (
        str(target_range)
        .upper()
        .replace("XXX", "")
        .replace("X", "")
        .strip()
    )

    payload = {
        "rid": clean_rid
    }

    try:

        response = requests.post(
            f"{MINO_BASE_URL}/getnumber.php",
            headers=headers,
            json=payload,
            timeout=10
        )

        print("MINO STATUS:", response.status_code)
        print("MINO RESPONSE:", response.text)

        if response.status_code != 200:
            return None, None

        data = response.json()

        # API response অনুযায়ী সম্ভাব্য number field
        number = (
            data.get("number")
            or data.get("phone")
            or data.get("full_number")
            or data.get("data", {}).get("number")
            or data.get("data", {}).get("phone")
            or data.get("data", {}).get("full_number")
        )

        # সম্ভাব্য order/id
        order_id = (
            data.get("id")
            or data.get("order_id")
            or data.get("booking_id")
            or data.get("data", {}).get("id")
            or data.get("data", {}).get("order_id")
        )

        if number:
            return str(number), str(order_id or "")

    except Exception as e:
        print("MINO API ERROR:", e)

    return None, None


async def get_mino_number(target_range):
    return await asyncio.to_thread(
        _sync_get_mino_number,
        target_range
    )


# =========================================================
# NUMBER BUTTONS
# =========================================================

def create_number_markup(numbers):

    keyboard = []

    for number in numbers:

        _, _, flag = get_country_info(number)

        keyboard.append([
            InlineKeyboardButton(
                text=f"{flag} {number}",
                copy_text=CopyTextButton(text=str(number))
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔔 OTP GROUP",
            url=f"https://t.me/{OTP_GROUP_USERNAME}"
        ),
        InlineKeyboardButton(
            "🔄 Change Number",
            callback_data="change_number"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "👨‍💻 Support",
            url=f"https://t.me/{SUPPORT_USERNAME}"
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="back_home"
        )
    ])

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["📞 Get API Number", "⚙ Set Range"],
        ["📣 OTP Group", "👨‍💻 Support"]
    ]

    markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 Welcome to Number Bot!\n\n"
        "Please select an option:",
        reply_markup=markup
    )


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # -----------------------------------------------------
    # SET RANGE
    # -----------------------------------------------------

    if USER_STATES.get(user_id) == "WAITING_FOR_RANGE":

        clean_text = text.upper().strip()

        if clean_text.replace("X", "").isdigit():

            USER_RANGES[user_id] = clean_text
            USER_STATES[user_id] = None

            await update.message.reply_text(
                f"✅ Target Range Updated\n\n"
                f"⚙️ Range: <code>{clean_text}</code>",
                parse_mode="HTML"
            )

        else:

            await update.message.reply_text(
                "❌ Invalid Range!\n\n"
                "Example:\n"
                "<code>22896</code>\n"
                "or\n"
                "<code>88017XXX</code>",
                parse_mode="HTML"
            )

        return

    # -----------------------------------------------------
    # GET NUMBER
    # -----------------------------------------------------

    if text == "📞 Get API Number":

        wait_msg = await update.message.reply_text(
            "⏳ Getting real number from MINO SMS..."
        )

        target_range = USER_RANGES.get(
            user_id,
            "22896"
        )

        numbers = []

        # 2টি number নেওয়ার চেষ্টা
        for _ in range(2):

            phone, order_id = await get_mino_number(
                target_range
            )

            if phone and phone not in numbers:
                numbers.append(phone)

        try:
            await wait_msg.delete()
        except Exception:
            pass

        if not numbers:

            await update.message.reply_text(
                "❌ No Number Available!\n\n"
                f"Panel has no available number for:\n"
                f"<code>{target_range}</code>",
                parse_mode="HTML"
            )

            return

        # Country
        country_name, country_code, flag = get_country_info(
            numbers[0]
        )

        # Header
        header = (
            f"🌐 <b>Country:</b> "
            f"{flag} {country_name}\n\n"
            f"⚙️ <b>Range:</b> "
            f"<code>{target_range}</code>"
        )

        markup = create_number_markup(numbers)

        await update.message.reply_text(
            header,
            reply_markup=markup,
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # SET RANGE
    # -----------------------------------------------------

    elif text == "⚙ Set Range":

        USER_STATES[user_id] = "WAITING_FOR_RANGE"

        await update.message.reply_text(
            "⚙️ <b>Set Target Range</b>\n\n"
            "আপনার Range পাঠান।\n\n"
            "Example:\n"
            "<code>22896</code>\n"
            "অথবা\n"
            "<code>88017XXX</code>",
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # OTP GROUP
    # -----------------------------------------------------

    elif text == "📣 OTP Group":

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📣 Join OTP Group ↗",
                    url=f"https://t.me/{OTP_GROUP_USERNAME}"
                )
            ]
        ])

        await update.message.reply_text(
            "📣 আমাদের OTP Group-এ যেতে নিচের button চাপুন:",
            reply_markup=markup
        )

        return

    # -----------------------------------------------------
    # SUPPORT
    # -----------------------------------------------------

    elif text == "👨‍💻 Support":

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "👨‍💻 Contact Support",
                    url=f"https://t.me/{SUPPORT_USERNAME}"
                )
            ]
        ])

        await update.message.reply_text(
            "👨‍💻 <b>Support</b>\n\n"
            "যেকোনো সমস্যায় আমাদের Support-এ যোগাযোগ করুন।",
            reply_markup=markup,
            parse_mode="HTML"
        )

        return


# =========================================================
# CALLBACK
# =========================================================

async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    # -----------------------------------------------------
    # CHANGE NUMBER
    # -----------------------------------------------------

    if query.data == "change_number":

        user_id = query.from_user.id

        target_range = USER_RANGES.get(
            user_id,
            "22896"
        )

        numbers = []

        for _ in range(2):

            phone, order_id = await get_mino_number(
                target_range
            )

            if phone and phone not in numbers:
                numbers.append(phone)

        if not numbers:

            await query.message.reply_text(
                "❌ এই Range-এ বর্তমানে কোনো number পাওয়া যায়নি।"
            )

            return

        country_name, country_code, flag = get_country_info(
            numbers[0]
        )

        header = (
            f"🌐 <b>Country:</b> "
            f"{flag} {country_name}\n\n"
            f"⚙️ <b>Range:</b> "
            f"<code>{target_range}</code>"
        )

        markup = create_number_markup(numbers)

        try:

            await query.edit_message_text(
                text=header,
                reply_markup=markup,
                parse_mode="HTML"
            )

        except Exception as e:

            print("Edit Error:", e)

        return

    # -----------------------------------------------------
    # BACK
    # -----------------------------------------------------

    elif query.data == "back_home":

        try:
            await query.message.delete()
        except Exception:
            pass

        # callback update-এ message থাকতে পারে
        if query.message:

            keyboard = [
                ["📞 Get API Number", "⚙ Set Range"],
                ["📣 OTP Group", "👨‍💻 Support"]
            ]

            markup = ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True
            )

            await query.message.reply_text(
                "🏠 <b>Main Menu</b>",
                reply_markup=markup,
                parse_mode="HTML"
            )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    if not MINO_API_KEY:
        raise RuntimeError(
            "MINO_API_KEY environment variable is missing."
        )

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    app.add_handler(
        CallbackQueryHandler(handle_callback)
    )

    print("🤖 Number Bot is running...")

    app.run_polling()
