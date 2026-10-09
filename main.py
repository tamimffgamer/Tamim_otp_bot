async def auto_forward_console_logs(application):
    print("Dedicated Per-Number Check Loop Started Successfully!")
    while True:
        try:
            current_time = time.time()
            
            for user_id, u_info in list(ACTIVE_USER_NUMBERS.items()):
                u_phone = str(u_info.get("phone", "")).strip()
                fetch_time = u_info.get("fetch_time", 0)
                
                if (current_time - fetch_time) > 1200:
                    continue

                if not u_phone: continue

                res_data = await check_number_status(u_phone)
                if not res_data: continue

                sms_data = res_data.get("data") or res_data.get("sms") or res_data.get("message") or res_data
                
                msg_text = ""
                if isinstance(sms_data, dict):
                    actual_sms = sms_data.get("full_sms") or sms_data.get("message") or sms_data.get("text") or ""
                    explicit_otp = sms_data.get("otp_code") or ""
                    
                    if explicit_otp and str(explicit_otp).strip():
                        msg_text = f"OTP: {explicit_otp}"
                    elif actual_sms and str(actual_sms).strip():
                        msg_text = actual_sms
                    else:
                        continue
                elif isinstance(sms_data, str):
                    msg_text = sms_data

                if not msg_text:
                    msg_text = res_data.get("message") or res_data.get("text") or ""

                if not (s_s := str(msg_text).strip()): continue
                if s_s.lower() in ["success", "completed", "waiting", "failed", "ok", "active"]:
                    continue

                matches = re.findall(r'\b\d{4,8}\b', s_s)
                otp_code = None
                for m in matches:
                    if not m.startswith("202") and not m.startswith("201"):
                        otp_code = m
                        break
                
                if not otp_code: continue

                sent_set = u_info.setdefault("sent_otps", set())
                if otp_code not in sent_set:
                    sent_set.add(otp_code)
                    current_bal = USER_BALANCES.get(user_id, 0.0)
                    USER_BALANCES[user_id] = current_bal + 0.00122

                    country_name, _, flag = get_country_info(u_phone)
                    
                    # ব্যক্তিগত চ্যাটে পাঠানোর অংশ
                    personal_text = (
                        f"🟢 <b>SUCCESSFUL OTP RECEIVED</b>\n\n"
                        f"🌐 <b>Service :</b> SMS\n"
                        f"🌍 <b>Country :</b> {country_name} ({flag})\n"
                        f"🎯 <b>Number :</b> <code>{u_phone}</code>\n"
                        f"🔑 <b>OTP Code :</b> <code>{otp_code}</code>\n\n"
                        f"✉ <b>Full Message :</b>\n<code>{s_s}</code>\n\n"
                        f"💰 <b>Earned :</b> +$0.00122"
                    )
                    personal_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton(text=f"📋 Copy OTP: {otp_code}", copy_text=CopyTextButton(text=otp_code))],
                        [InlineKeyboardButton("🔄 Change Number", callback_data="change_number")]
                    ])
                    try:
                        await application.bot.send_message(
                            chat_id=u_info["chat_id"], 
                            text=personal_text, 
                            reply_markup=personal_markup,
                            parse_mode="HTML"
                        )
                        await success_otp(u_phone)
                    except Exception as per_ex:
                        print(f"Personal Send Error: {per_ex}")

                    # 📣 ওটিপি গ্রুপে পাঠানোর অংশ (লগ সহ)
                    print(f"Attempting to send OTP {otp_code} to group {OTP_GROUP_CHAT_ID}...")
                    group_text = (
                        f"🟢 <b>SMS OTP RECEIVED</b>\n\n"
                        f"🌍 <b>Country :</b> {country_name} ({flag})\n"
                        f"🎯 <b>Number :</b> <code>{u_phone}</code>\n"
                        f"🔑 <b>Code :</b> <code>{otp_code}</code>\n\n"
                        f"✉ <b>Message :</b>\n<code>{s_s}</code>"
                    )
                    group_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton(text=f"📋 Copy OTP: {otp_code}", copy_text=CopyTextButton(text=otp_code))],
                        [InlineKeyboardButton("NUMBER BOT ↗", url=f"https://t.me/{application.bot.username}")]
                    ])
                    try:
                        await application.bot.send_message(
                            chat_id=OTP_GROUP_CHAT_ID, 
                            text=group_text, 
                            reply_markup=group_markup, 
                            parse_mode="HTML"
                        )
                        print("Group OTP sent successfully!")
                    except Exception as g_ex:
                        print(f"❌ Group Send Error: {g_ex}")

        except Exception as e:
            print(f"Background Loop Error: {e}")
        
        await asyncio.sleep(2)
