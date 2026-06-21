import os

main_path = "backend/app/main.py"
with open(main_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Verify exact line contents to ensure surgical accuracy
start_idx = -1
end_idx = -1

for idx, line in enumerate(lines):
    if "# Offline Fallback if no LLM response could be fetched or generated" in line and idx > 1400:
        start_idx = idx
    if 'yield f"data: {json.dumps({\'type\': \'action\', \'action\': action, \'disclaimer\': disclaimer, \'reply\': reply})}\\n\\n"' in line and idx > 1500:
        end_idx = idx

print(f"Detected Start Index: {start_idx} ('{lines[start_idx].strip() if start_idx != -1 else 'NONE'}')")
print(f"Detected End Index: {end_idx} ('{lines[end_idx].strip() if end_idx != -1 else 'NONE'}')")

if start_idx != -1 and end_idx != -1:
    replacement = """            # Offline Fallback if no LLM response could be fetched or generated
            if not message:
                msg_lower = input_data.message.lower()
                is_schedule_query = any(k in msg_lower for k in ["show", "read", "view", "what", "my", "list", "check", "శెడ్యూల్", "అపాయింట్మెంట్", "షెడ్యూల్", "अपॉइंटमेंट", "शेड्यूल"]) and any(k in msg_lower for k in ["appointment", "appointments", "consultation", "consultations", "schedule", "visit", "visits", "meeting", "meetings", "record", "records"])
                is_booking_intent = any(k in msg_lower for k in ["book", "schedule", "appointment", "अपॉइंटमेंट", "అపాయింట్మెంట్"])
                
                if is_schedule_query:
                    intent = "view_schedule"
                    action_type = "OPEN_DASHBOARD"
                    if current_user.role == "patient":
                        message = "Opening your dashboard to view upcoming appointments."
                    elif current_user.role == "doctor":
                        message = "Opening your doctor workspace to view consultations."
                    else:
                        message = "Opening admin portal."
                elif is_booking_intent:
                    intent = "book_appointment"
                    action_type = "OPEN_DOCTORS"
                    message = "Opening doctors directory for you to browse and book appointments."
                elif "record" in msg_lower or "prescription" in msg_lower or "file" in msg_lower or "report" in msg_lower:
                    intent = "view_records"
                    action_type = "OPEN_RECORDS"
                    message = "Opening your medical records workspace."
                elif "setting" in msg_lower or "profile" in msg_lower:
                    intent = "view_settings"
                    action_type = "OPEN_SETTINGS"
                    message = "Opening your profile settings page."
                elif "chat" in msg_lower or "message" in msg_lower:
                    intent = "view_chat"
                    action_type = "OPEN_CHAT"
                    message = "Opening your private chats workspace."
                elif "sos" in msg_lower or "emergency" in msg_lower:
                    intent = "trigger_sos"
                    action_type = "TRIGGER_SOS"
                    message = "Triggering emergency SOS broadcast."
                elif "logout" in msg_lower or "sign out" in msg_lower:
                    intent = "logout"
                    action_type = "LOGOUT"
                    message = "Logging you out from the system."
                else:
                    intent = "common_help"
                    message = "Hello! I am TARS. How can I help you today?"

            # Map the action types from TARS layout to what the frontend expects
            action_payload = None
            if action_type:
                mapped_type = action_type
                if action_type == 'OPEN_DOCTORS':
                    mapped_type = 'find_doctors'
                    # Map speciality parameter to specialization
                    spec = action_params.get("speciality", "general").lower()
                    action_params = {"specialization": spec}
                elif action_type in ['OPEN_PRESCRIPTIONS', 'OPEN_RECORDS']:
                    mapped_type = 'view_records'
                elif action_type in ['OPEN_DASHBOARD', 'OPEN_WORKSPACE', 'OPEN_ADMIN_PORTAL']:
                    mapped_type = 'view_dashboard'
                elif action_type == 'OPEN_SETTINGS':
                    mapped_type = 'view_settings'
                elif action_type == 'OPEN_CHAT':
                    mapped_type = 'view_chat'
                elif action_type == 'TRIGGER_SOS':
                    mapped_type = 'trigger_sos'
                elif action_type == 'LOGOUT':
                    mapped_type = 'logout'
                
                action_payload = {
                    "type": mapped_type,
                    "parameters": action_params
                }

            # Enforce Role-Based Access Control (RBAC)
            user_role = current_user.role
            role_permissions = SYSTEM_CAPABILITIES.get("roles", {}).get(user_role, {}).get("permissions", [])
            
            if action_payload:
                act_name = action_payload["type"]
                if act_name not in ["logout", "trigger_sos"] and act_name not in role_permissions:
                    # Access Denied!
                    action_payload = None
                    if user_role == "doctor":
                        message = "Access Denied: As a doctor, you do not have permission to execute this action."
                    elif user_role == "admin":
                        message = "Access Denied: As an admin, you do not have permission to execute this action."
                    else:
                        message = "Access Denied: Under your role, you do not have permission to execute this action."

            # Database side-effects (e.g. creating prescription internally if requested by doctor)
            if action_payload and action_payload["type"] == "create_prescription" and user_role == "doctor":
                try:
                    params = action_payload.get("parameters", {})
                    p_name = params.get("patient_name")
                    diagnosis = params.get("diagnosis")
                    medicines = params.get("medicines", [])
                    instructions = params.get("instructions", "")
                    
                    from sqlalchemy import or_, and_
                    p_profile = db.query(models.PatientProfile).filter(
                        models.PatientProfile.name.ilike(f"%{p_name}%")
                    ).first()
                    
                    if p_profile:
                        recipient_id = p_profile.user_id
                        conv_db = db.query(models.PrivateConversation).filter(
                            or_(
                                and_(models.PrivateConversation.user1_id == current_user.id, models.PrivateConversation.user2_id == recipient_id),
                                and_(models.PrivateConversation.user1_id == recipient_id, models.PrivateConversation.user2_id == current_user.id)
                            )
                        ).first()
                        if not conv_db:
                            conv_db = models.PrivateConversation(
                                user1_id=current_user.id,
                                user2_id=recipient_id
                            )
                            db.add(conv_db)
                            db.commit()
                            db.refresh(conv_db)
                        
                        from app.routes.chats import create_prescription_internal
                        create_prescription_internal(
                            db=db,
                            conversation_id=conv_db.id,
                            current_user=current_user,
                            patient_name=p_profile.name,
                            diagnosis=diagnosis,
                            medicines=medicines,
                            instructions=instructions
                        )
                        message = f"Prescription issued successfully for {p_profile.name}."
                except Exception as ex:
                    print(f"Failed to issue prescription in backend: {ex}")

            # Stream message chunk-by-chunk to preserve typing effect
            chunk_size = 4
            for i in range(0, len(message), chunk_size):
                chunk = message[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\\n\\n"
                await asyncio.sleep(0.01)

            # Save final response to the Message log in database
            assistant_msg = models.Message(
                conversation_id=conv.id,
                role="assistant",
                content=f"{message}\\n\\n[Disclaimer: {disclaimer}]"
            )
            db.add(assistant_msg)
            db.commit()

            # Yield action payload and final message mapping to complete the call
            yield f"data: {json.dumps({'type': 'action', 'action': action_payload, 'disclaimer': disclaimer, 'reply': message})}\\n\\n"
"""
    # Replace lines
    new_lines = lines[:start_idx] + [replacement] + lines[end_idx+1:]
    with open(main_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Replacement performed successfully!")
else:
    print("Could not find start and/or end index!")
