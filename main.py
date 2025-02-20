import streamlit as st
import asyncio
import pandas as pd
import io
from telegram_client import create_client, delete_session_file
from fetch_channel import get_channel_info
from telethon.errors import PhoneNumberInvalidError, PhoneCodeInvalidError, SessionPasswordNeededError

# --- Streamlit UI ---
st.title("TGForge")

# Ensure session state variables are initialized
if "auth_step" not in st.session_state:
    st.session_state.auth_step = 1
    st.session_state.authenticated = False
    st.session_state.client = None
    
if st.session_state.auth_step == 1:
    st.subheader("Step 1: Enter Telegram API Credentials")
    
    api_id = st.text_input("API ID", value=st.session_state.get("api_id", ""))
    api_hash = st.text_input("API Hash", value=st.session_state.get("api_hash", ""))
    phone_number = st.text_input("Phone Number (e.g., +123456789)")

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("Next"):
            if api_id and api_hash and phone_number:
                try:
                    st.session_state.api_id = api_id
                    st.session_state.api_hash = api_hash
                    st.session_state.phone_number = phone_number

                    if st.session_state.client is None:
                        st.session_state.client = create_client(int(api_id), api_hash)

                    async def connect_and_send_code():
                        await st.session_state.client.connect()
                        if not await st.session_state.client.is_user_authorized():
                            await st.session_state.client.send_code_request(phone_number)

                    st.session_state.event_loop.run_until_complete(connect_and_send_code())
                    st.session_state.auth_step = 2  

                except PhoneNumberInvalidError:
                    st.error("Invalid phone number. Please check and try again.")
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        if st.button("Reset Session"):
            delete_session_file()

# --- Step 2: Enter Verification Code ---
elif st.session_state.auth_step == 2:
    st.subheader("Step 2: Enter Verification Code")
    verification_code = st.text_input("Enter the verification code")

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("Authenticate"):
            try:
                async def sign_in():
                    await st.session_state.client.sign_in(st.session_state.phone_number, verification_code)

<<<<<<< HEAD
                st.session_state.event_loop.run_until_complete(sign_in())
                st.session_state.auth_step = 3  
                st.session_state.authenticated = True
                st.success("Authentication successful!")
=======
    channel_input = st.text_area("Enter Telegram channel usernames (comma-separated):", "")
>>>>>>> 5d46fef247b946ddce550d5f4ce261605dd452b1

            except PhoneCodeInvalidError:
                st.error("Invalid verification code. Please try again.")
            except SessionPasswordNeededError:
                st.error("Two-step verification is enabled. This script does not handle passwords.")
            except Exception as e:
                st.error(f"Error: {e}")

<<<<<<< HEAD
    with col2:
        if st.button("Reset Session"):
            delete_session_file()
=======
        try:
            channel_data = st.session_state.event_loop.run_until_complete(fetch_info())
            st.session_state.channel_data = channel_data
        except Exception as e:
            st.error(f"Error while fetching channel data: {e}")

    if "channel_data" in st.session_state and st.session_state.channel_data:
        df = pd.DataFrame(st.session_state.channel_data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)

        st.download_button(
            label="📥 Download Excel File",
            data=output,
            file_name="channel_info.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
>>>>>>> 5d46fef247b946ddce550d5f4ce261605dd452b1
