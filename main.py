import os
import requests
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

# Tomar render er environment variable theke bot token nibe
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Screenshot anujayi API base url ebong support username
API_BASE_URL = "https://minosms.com[span_8](start_span)"[span_8](end_span)
SUPPORT_USERNAME = "@tmtamimmia[span_9](start_span)"[span_9](end_span)

# Apnar minosms.com er real api key ekhane bosiye din (Screenshot 1000004145.png onujayi)
MINO_API_KEY = "mino_live_a5db48f1d607f390b03bd1fccfc1d17[span_10](start_span)"[span_10](end_span)

# Conversation state range pawar jonno
ASKING_RANGE = 1

# Render a web service live rakhar jonno flask server
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot is running!"

def run():
    app_flask.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📱 Get Number", callback_data="get_number")],
        [InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")][span_11](start_span)[span_11](end_span)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"Assalamu Alaikum {user.first_name}!\n\n"
        "MINO SMS Number Bot-e apnake swagotom. Number nite nicher 'Get Number' button-e click korun."
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# Get Number button click korle range chaibe
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "get_number":
        await query.message.reply_text("Doya kore apnar kankkhito Range ID din (Jemon: `88017XXX`):", parse_mode="Markdown")[span_12](start_span)[span_12](end_span)
        return ASKING_RANGE

# User er dewa range accept kore minosms.com api call korbe
async def receive_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    range_id = update.message.text.strip()
    
    headers = {
        "mauthapi": MINO_API_KEY,[span_13](start_span)[span_13](end_span)[span_14](start_span)[span_14](end_span)
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "rid": range_id[span_15](start_span)[span_15](end_span)
    }
    
    wait_msg = await update.message.reply_text("⏳ Number khojha hocche, please wait...")
    
    try:
        # Screenshot 1000004144.png er getnumber.php endpoint onujayi request
        response = requests.post(f"{API_BASE_URL}/getnumber.php", headers=headers, json=payload, timeout=10)[span_16](start_span)[span_16](end_span)[span_17](start_span)[span_17](end_span)
        
        try:
            await wait_msg.delete()
        except Exception:
            pass

        if response.status_code == 200:
            res_data = response.json()
            await update.message.reply_text(f"✅ API Response:\n```json\n{res_data}\n```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ API Error! Status code: {response.status_code}")
            
    except Exception as e:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"❌ Number nite somossa hoyeche: {str(e)}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancel kora hoyeche.")
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is not set!")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^get_number$")],
        states={
            ASKING_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_range)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    keep_alive()
    application.run_polling()

if __name__ == '__main__':
    main()

