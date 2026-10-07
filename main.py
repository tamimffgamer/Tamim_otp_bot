async def auto_forward_console_logs(application):
    await asyncio.sleep(2)
    try:
        headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
        res = await asyncio.to_thread(requests.get, f"{BASE_API_URL}/console.php", headers=headers, timeout=5.0)
        if res.status_code == 200:
            res_json = res.json()
            hits = res_json.get("data", [])
            if isinstance(hits, list):
                for hit in hits:
                    if isinstance(hit, dict):
                        m = hit.get("message") or hit.get("text") or hit.get("sms") or hit.get("content") or ""
                        n = str(
                            hit.get("number") or hit.get("full_number") or hit.get("phone") or 
                            hit.get("phone_number") or hit.get("mobile") or hit.get("receiver") or 
                            hit.get("to") or hit.get("range", "")
                        )
                        SEEN_OTP_IDS.add(f"{n}_{m}")
    except Exception as e:
        print(f"Init Seen Error: {e}")

    while True:
        try:
            headers = {"mauthapi": MINO_API_KEY, "Accept": "application/json"}
            res = await asyncio.to_thread(requests.get, f"{BASE_API_URL}/console.php", headers=headers, timeout=5.0)
            if res.status_code == 200:
                res_json = res.json()
                hits = res_json.get("data", [])
                if isinstance(hits, list):
                    current_loop_time = time.time()
                    for hit in hits:
                        if not isinstance(hit, dict): continue

                        msg = hit.get("message") or hit.get("text") or hit.get("sms") or hit.get("content") or ""
                        num = str(
                            hit.get("number") or 
                            hit.get("full_number") or 
                            hit.get("phone") or 
                            hit.get("phone_number") or 
                            hit.get("mobile") or 
                            hit.get("receiver") or
                            hit.get("to") or
                            hit.get("range", "")
                        )
                        service = hit.get("service", "SMS")
                        country = hit.get("country", "Cameroon")

                        log_id = f"{num}_{msg}"
                        if log_id not in SEEN_OTP_IDS:
                            SEEN_OTP_IDS.add(log_id)
                            if len(SEEN_OTP_IDS) > 4000:
                                SEEN_OTP_IDS.pop()
                            
                            _, _, flag = get_country_info(num, country)
                            
                            # ১. প্যানেলের সকল কোড গ্রুপে ফরোয়ার্ড করা
                            group_text = (
                                f"🤖 <b>𝑻𝑨𝑴𝒊𝑴 𝑶𝑻𝑷 𝑩𝑶𝑻</b> 🤖\n\n"
                                f"📘 <b>{service} OTP RECEIVE</b>\n\n"
                                f"🌍 <b>Country :</b> {country} ({flag})\n"
                                f"🎯 <b>Number :</b> <code>{num}</code>\n"
                                f"🗣 <b>Language :</b> English\n\n"
                                f"✉ <b>Message :</b>\n<code>{msg}</code>"
                            )
                            group_markup = InlineKeyboardMarkup([
                                [InlineKeyboardButton("NUMBER BOT ↗", url=f"https://t.me/{application.bot.username}")]
                            ])
                            
                            try:
                                await application.bot.send_message(
                                    chat_id=OTP_GROUP_CHAT_ID, 
                                    text=group_text, 
                                    reply_markup=group_markup, 
                                    parse_mode="HTML"
                                )
                            except Exception as ex:
                                print(f"Group Forward Error: {ex}")

                            # ২. বট থেকে নেওয়া নাম্বারে ২০ মিনিটের মধ্যে কোድ আসলে ইনবক্সে পাঠানো (ফিক্সড ম্যাচিং লজিক)
                            clean_log_num = ''.join(filter(str.isdigit, num))
                            
                            for user_id, u_info in list(ACTIVE_USER_NUMBERS.items()):
                                req_time = u_info.get("req_time", 0)
                                
                                # ২০ মিনিট (১২০০ সেকেন্ড) সময়সীমা চেক
                                if current_loop_time < req_time or (current_loop_time - req_time) > 1200:
                                    continue

                                u_phone = str(u_info.get("phone", ""))
                                clean_u_phone = ''.join(filter(str.isdigit, u_phone))
                                
                                matched = False
                                if clean_u_phone and clean_log_num:
                                    # সঠিকভাবে নাম্বারের শেষ ৮ বা ৯ ডিজিট মিলিয়ে চেক করা যাতে প্লাস (+) বা কান্ট্রি কোড সমস্যা না করে
                                    if (clean_u_phone == clean_log_num or 
                                        clean_log_num.endswith(clean_u_phone) or 
                                        clean_u_phone.endswith(clean_log_num) or
                                        clean_log_num.find(clean_u_phone) != -1 or
                                        clean_u_phone.find(clean_log_num) != -1 or
                                        (len(clean_u_phone) >= 7 and clean_u_phone[-7:] == clean_log_num[-7:])):
                                        matched = True

                                if matched:
                                    match_otp = re.search(r'\b\d{4,8}\b', msg)
                                    otp_code = match_otp.group(0) if match_otp else msg
                                    
                                    sent_set = u_info.setdefault("sent_otps", set())
                                    if otp_code not in sent_set:
                                        sent_set.add(otp_code)
                                        current_bal = USER_BALANCES.get(user_id, 0.0)
                                        USER_BALANCES[user_id] = current_bal + 0.00122
                                        
                                        personal_text = (
                                            f"🤖 <b>𝑻𝑨𝑴𝒊𝑴 𝑶𝑻𝑷 𝑩𝑶𝑻</b> 🤖\n\n"
                                            f"🚨 <b>YOUR NUMBER OTP RECEIVE</b>\n\n"
                                            f"📘 <b>Service :</b> {service}\n"
                                            f"🌍 <b>Country :</b> {country} ({flag})\n"
                                            f"🎯 <b>Number :</b> <code>{u_phone}</code>\n"
                                            f"🔑 <b>OTP Code :</b> <code>{otp_code}</code>\n\n"
                                            f"✉ <b>Full Message :</b>\n<code>{msg}</code>\n\n"
                                            f"💰 <b>Earned:</b> +$0.00122"
                                        )
                                        try:
                                            await application.bot.send_message(
                                                chat_id=u_info["chat_id"], 
                                                text=personal_text, 
                                                parse_mode="HTML"
                                            )
                                        except Exception as per_ex:
                                            print(f"Personal Send Error: {per_ex}")
        except Exception as e:
            print(f"Background Loop Error: {e}")
        await asyncio.sleep(2)
