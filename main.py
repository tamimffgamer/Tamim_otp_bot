import requests
import time

# --- Configuration ---
BASE_URL = "https://minosms.com"                                    #
API_KEY = "mino_live_a5db48f1d607f390b0d3bd1fccfcd17"                #
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"                      # Apnar Bot Token ekhane din
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"                          # Apnar Telegram Chat ID ekhane din
RANGE_ID = "88017XXX"                                               # Je range er number nite chan (jemon 88017...)

def send_telegram_message(message):
    """Telegram bot-er maddhome message pathanor function"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"[!] Telegram error: {e}")

def get_virtual_number(range_id):
    """Mino SMS theke virtual number collect korar function"""
    url = f"{BASE_URL}/getnumber.php"                                   #
    headers = {"mauthapi": API_KEY}                                     #
    payload = {"rid": range_id}                                         #
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def wait_for_new_otp(phone_number, timeout_minutes=20):
    """20 minute porjonto check korbe ebong shudhu notun ba real OTP bot-e pathabe"""
    url = f"{BASE_URL}/check.php"                                       #
    params = {"api_key": API_KEY, "number": phone_number}               #
    
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    last_seen_message = None

    print(f"[*] Listening for new OTP on {phone_number} for up to {timeout_minutes} minutes...")

    while time.time() - start_time < timeout_seconds:
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # Panel er response theke message ba OTP extract kora
            current_message = data.get("sms") or data.get("message") or data.get("code") or data.get("otp")
            
            # Jodi notun message ashe ebong ager ta theke alada/purono na hoy
            if current_message and current_message != last_seen_message:
                last_seen_message = current_message
                alert_text = f"[+] Real OTP Received!\nNumber: {phone_number}\nOTP/Message: {current_message}"
                print(alert_text)
                
                # Telegram bot-e notification pathano
                send_telegram_message(alert_text)
                
                return current_message
                
        except Exception as e:
            print(f"[!] Error checking status: {e}")
            
        # Proti 5 second por por status check korbe
        time.sleep(5)
    
    timeout_msg = f"[-] Timeout: No new OTP received for {phone_number} within {timeout_minutes} minutes."
    print(timeout_msg)
    send_telegram_message(timeout_msg)
    return None

if __name__ == "__main__":
    print("[*] Requesting virtual number...")
    res = get_virtual_number(RANGE_ID)
    print("API Response:", res)
    
    # Response theke number extract kora
    phone_number = res.get("number") or res.get("phone")
    
    if phone_number:
        acquired_msg = f"[+] New Number Acquired: {phone_number}"
        print(acquired_msg)
        send_telegram_message(acquired_msg)
        
        # 20 minute porjonto active theke real OTP listen korbe
        wait_for_new_otp(phone_number, timeout_minutes=20)
    else:
        print("[-] Failed to get number. Check your range ID, balance, or API response format.")
