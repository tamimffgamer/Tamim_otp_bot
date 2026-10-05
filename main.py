import os
import asyncio
import requests

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
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MINO_API_KEY = os.environ.get("MINO_API_KEY")

MINO_BASE_URL = "https://minosms.com"

SUPPORT_USERNAME = "tmtamimmia"
OTP_GROUP_USERNAME = "smm_otp_grup"


# =========================================================
# USER DATA
# =========================================================

USER_STATES = {}
USER_RANGES = {}


# =========================================================
# COUNTRY INFORMATION
# =========================================================

def get_country_info(phone_number):

    number = str(phone_number).replace("+", "").strip()

    countries = [
        ("237", "Cameroon", "CM", "🇨🇲"),
        ("225", "Ivory Coast", "CI", "🇨🇮"),
        ("228", "Togo", "TG", "🇹🇬"),
        ("229", "Benin", "BJ", "🇧🇯"),
        ("255", "Tanzania", "TZ", "🇹🇿"),
        ("266", "Lesotho", "LS", "🇱🇸"),
        ("380", "Ukraine", "UA", "🇺🇦"),
        ("224", "Guinea", "GN", "🇬🇳"),
        ("996", "Kyrgyzstan", "KG", "🇰🇬"),
        ("43", "Austria", "AT", "🇦🇹"),
        ("880", "Bangladesh", "BD", "🇧🇩"),
    ]

    for prefix, name, code, flag in countries:

        if number.startswith(prefix):
            return name, code, flag

    return "Unknown", "XX", "🌐"


# =========================================================
# MINO SMS API
# =========================================================

def sync_get_number(target_range):

    if not MINO_API_KEY:

        print("ERROR: MINO_API_KEY is missing")

        return None, None

    if not target_range:

        return None, None

    # -----------------------------------------------------
    # MINO documentation:
    #
    # Header:
    # mauthapi: YOUR_API_KEY
    #
    # Payload:
    # {"rid": "88017XXX"}
    # -----------------------------------------------------

    headers = {
        "mauthapi": MINO_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    rid = str(target_range).strip().upper()

    payload = {
        "rid": rid
    }

    try:

        response = requests.post(
            f"{MINO_BASE_URL}/getnumber.php",
            headers=headers,
            json=payload,
            timeout=15,
        )

        print("MINO HTTP:", response.status_code)
        print("MINO RESPONSE:", response.text)

        if response.status_code != 200:

            return None, None

        try:
            data = response.json()

        except ValueError:

            print("MINO returned non-JSON response")

            return None, None

        # -------------------------------------------------
        # Different possible response structures
        # -------------------------------------------------

        root = data if isinstance(data, dict) else {}

        nested = root.get("data")

        if not isinstance(nested, dict):
            nested = {}

        number = (
            root.get("number")
            or root.get("phone")
            or root.get("full_number")
            or root.get("national_number")

            or nested.get("number")
            or nested.get("phone")
            or nested.get("full_number")
            or nested.get("national_number")
        )

        order_id = (
            root.get("id")
            or root.get("order_id")
            or root.get("booking_id")

            or nested.get("id")
            or nested.get("order_id")
            or nested.get("booking_id")
        )

        if number:

            return str(number), str(order_id or "")

        print("Number field was not found in MINO response")

    except requests.RequestException as error:

        print("MINO REQUEST ERROR:", error)

    except Exception as error:

        print("MINO ERROR:", error)

    return None, None


async def get_number(target_range):

    return await asyncio.to_thread(
        sync_get_number,
        target_range
    )


# =========================================================
# NUMBER BUTTONS
# =========================================================

def create_number_markup(numbers, target_range):

    keyboard = []

    for number in numbers:

        _, _, flag = get_country_info(number)

        keyboard.append([
            InlineKeyboardButton(
                text=f"{flag} {number}",
                copy_text=CopyTextButton(
                    text=str(number)
                )
            )
        ])

    # Change Number
    keyboard.append([
        InlineKeyboardButton(
            "🔄 Change Number",
            callback_data="change_number"
        )
    ])

    # OTP Group
    keyboard.append([
        InlineKeyboardButton(
            "📣 OTP Group",
            url=f"https://t.me/{OTP_GROUP_USERNAME}"
        )
    ])

    # Support
    keyboard.append([
        InlineKeyboardButton(
            "👨‍💻 Support",
            url=f"https://t.me/{SUPPORT_USERNAME}"
        )
    ])

    # Back
    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="back_home"
        )
    ])

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# HOME MENU
# =========================================================

def home_keyboard():

    keyboard = [
        [
            "📞 Get API Number",
            "⚙ Set Range"
        ],
        [
            "📣 OTP Group",
            "👨‍💻 Support"
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 <b>Welcome to Number Bot!</b>\n\n"
        "নিচের Menu থেকে একটি option নির্বাচন করুন।",
        reply_markup=home_keyboard(),
        parse_mode="HTML",
    )


# =========================================================
# GET NUMBER
# =========================================================

async def handle_get_number(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    target_range = USER_RANGES.get(
        user_id,
        "22896"
    )

    wait_message = await update.message.reply_text(
        "⏳ <b>Getting number...</b>\n\n"
        f"⚙️ Range: <code>{target_range}</code>",
        parse_mode="HTML",
    )

    numbers = []

    # দুইবার চেষ্টা করবে
    for _ in range(2):

        phone, order_id = await get_number(
            target_range
        )

        if phone and phone not in numbers:

            numbers.append(phone)

    try:

        await wait_message.delete()

    except Exception:

        pass

    # -----------------------------------------------------
    # No number
    # -----------------------------------------------------

    if not numbers:

        await update.message.reply_text(
            "❌ <b>No Number Available</b>\n\n"
            f"⚙️ Range: <code>{target_range}</code>\n\n"
            "এই Range-এ বর্তমানে number পাওয়া যায়নি।",
            parse_mode="HTML",
        )

        return

    # -----------------------------------------------------
    # Country
    # -----------------------------------------------------

    country_name, country_code, flag = get_country_info(
        numbers[0]
    )

    # -----------------------------------------------------
    # Header
    # -----------------------------------------------------

    text = (
        f"🌐 <b>Country:</b> "
        f"{flag} {country_name}\n\n"

        f"⚙️ <b>Range:</b> "
        f"<code>{target_range}</code>\n\n"

        f"📱 <b>Available Number:</b> "
        f"{len(numbers)}"
    )

    markup = create_number_markup(
        numbers,
        target_range
    )

    await update.message.reply_text(
        text,
        reply_markup=markup,
        parse_mode="HTML",
    )


# =========================================================
# SET RANGE
# =========================================================

async def handle_set_range(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    USER_STATES[user_id] = "WAITING_FOR_RANGE"

    await update.message.reply_text(
        "⚙️ <b>Set Target Range</b>\n\n"
        "আপনার Range পাঠান।\n\n"
        "উদাহরণ:\n"
        "<code>22896</code>\n"
        "অথবা\n"
        "<code>88017XXX</code>",
        parse_mode="HTML",
    )


# =========================================================
# SAVE RANGE
# =========================================================

async def handle_range_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    text = update.message.text.strip().upper()

    # X বাদ দিলে বাকি অংশ numeric হতে হবে
    test_value = text.replace("X", "")

    if not test_value.isdigit():

        await update.message.reply_text(
            "❌ <b>Invalid Range!</b>\n\n"
            "সঠিক উদাহরণ:\n"
            "<code>22896</code>\n"
            "অথবা\n"
            "<code>88017XXX</code>",
            parse_mode="HTML",
        )

        return

    USER_RANGES[user_id] = text
    USER_STATES[user_id] = None

    await update.message.reply_text(
        "✅ <b>Range Updated</b>\n\n"
        f"⚙️ Range: <code>{text}</code>\n\n"
        "এখন 📞 Get API Number চাপুন।",
        parse_mode="HTML",
    )


# =========================================================
# OTP GROUP
# =========================================================

async def handle_group(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📣 Join OTP Group ↗",
                url=f"https://t.me/{OTP_GROUP_USERNAME}"
            )
        ]
    ])

    await update.message.reply_text(
        "📣 <b>OTP Group</b>\n\n"
        "Group-এ যেতে নিচের button চাপুন।",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# =========================================================
# SUPPORT
# =========================================================

async def handle_support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👨‍💻 Contact Support",
                url=f"https://t.me/{SUPPORT_USERNAME}"
            )
        ]
    ])

    await update.message.reply_text(
        "👨‍💻 <b>Support</b>\n\n"
        f"Support: @{SUPPORT_USERNAME}",
        reply_markup=keyboard,
        parse_mode="HTML",
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
    # Range input
    # -----------------------------------------------------

    if USER_STATES.get(user_id) == "WAITING_FOR_RANGE":

        await handle_range_input(
            update,
            context
        )

        return

    # -----------------------------------------------------
    # Menu buttons
    # -----------------------------------------------------

    if text == "📞 Get API Number":

        await handle_get_number(
            update,
            context
        )

    elif text == "⚙ Set Range":

        await handle_set_range(
            update,
            context
        )

    elif text == "📣 OTP Group":

        await handle_group(
            update,
            context
        )

    elif text == "👨‍💻 Support":

        await handle_support(
            update,
            context
        )


# =========================================================
# CALLBACK HANDLER
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

        wait_message = await query.message.reply_text(
            "⏳ Getting a new number..."
        )

        numbers = []

        for _ in range(2):

            phone, order_id = await get_number(
                target_range
            )

            if phone and phone not in numbers:

                numbers.append(phone)

        try:

            await wait_message.delete()

        except Exception:

            pass

        if not numbers:

            await query.message.reply_text(
                "❌ এই Range-এ নতুন number পাওয়া যায়নি।"
            )

            return

        country_name, country_code, flag = get_country_info(
            numbers[0]
        )

        text = (
            f"🌐 <b>Country:</b> "
            f"{flag} {country_name}\n\n"

            f"⚙️ <b>Range:</b> "
            f"<code>{target_range}</code>"
        )

        markup = create_number_markup(
            numbers,
            target_range
        )

        try:

            await query.edit_message_text(
                text=text,
                reply_markup=markup,
                parse_mode="HTML",
            )

        except Exception as error:

            print("EDIT MESSAGE ERROR:", error)

    # -----------------------------------------------------
    # BACK HOME
    # -----------------------------------------------------

    elif query.data == "back_home":

        try:

            await query.message.delete()

        except Exception:

            pass

        await query.message.reply_text(
            "🏠 <b>Main Menu</b>",
            reply_markup=home_keyboard(),
            parse_mode="HTML",
        )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "BOT ERROR:",
        context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # Check BOT TOKEN
    # -----------------------------------------------------

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    # -----------------------------------------------------
    # Check MINO API KEY
    # -----------------------------------------------------

    if not MINO_API_KEY:

        raise RuntimeError(
            "MINO_API_KEY environment variable is missing."
        )

    # -----------------------------------------------------
    # Create bot
    # -----------------------------------------------------

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # Handlers
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            handle_callback
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        "================================="
    )

    print(
        "🤖 MINO NUMBER BOT STARTED"
    )

    print(
        "================================="
    )

    # -----------------------------------------------------
    # Run
    # -----------------------------------------------------

    app.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# START PROGRAM
# =========================================================

if __name__ == "__main__":
    main()
