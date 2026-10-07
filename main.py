import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

BASE_URL = "https://minosms.com"
API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = "-1004436883235"
RANGE_ID = "88017XXX"  # Apnar target range ID ekhane diben

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[!] Telegram error: {e}")

def get_virtual_number(range_id):
    url = f"{BASE_URL}/getnumber.php"
    headers = {"mauthapi": API_KEY}
    payload = {"rid": range_id}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def wait_for_new_otp(phone_number, timeout_minutes=20):
    url = f"{BASE_URL}/check.php"
    params = {"api_key": API_KEY, "number": phone_number}
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    last_seen_message = None

    while time.time() - start_time < timeout_seconds:
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            current_message = data.get("sms") or data.get("message") or data.get("code") or data.get("otp")
            
            if current_message and current_message != last_seen_message:
                last_seen_message = current_message
                alert_text = f"[+] Real OTP Received!\nNumber: {phone_number}\nOTP/Message: {current_message}"
                send_telegram_message(alert_text)
                return current_message
        except Exception as e:
            print(f"[!] Error: {e}")
        time.sleep(5)
    
    send_telegram_message(f"[-] Timeout: No new OTP received for {phone_number}.")

def background_worker():
    """Background-e number nebe ebong OTP check korbe"""
    time.sleep(5) # Server start howar jonno khetro toiri
    res = get_virtual_number(RANGE_ID)
    phone_number = res.get("number") or res.get("phone")
    
    if phone_number:
        send_telegram_message(f"[+] New Number Acquired: {phone_number}")
        wait_for_new_otp(phone_number, timeout_minutes=20)
    else:
        send_telegram_message("[-] Failed to get number from API.")

@app.route('/')
def home():
    return "Bot is running live!"

if __name__ == "__main__":
    # Background thread-e bot-er kaj cholbe, ar main thread-e Flask server port bind korbe
    t = threading.Thread(target=background_worker)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
