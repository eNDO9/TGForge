import streamlit as st
import asyncio
import pandas as pd
import io
from telegram_client import TelegramSession
from fetch_channel import get_channel_info

# --- Streamlit UI ---
st.title("Telegram API Authentication")

# Ensure session state variables are initialized
if "auth_step" not in st.session_state:
    st.session_state.auth_step = 1
    st.session_state.authenticated = False
    st.session_state.client = None
    st.session_state.event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.event_loop)

if st.session_state.auth_step == 1:
    st.subheader("Step 1: Enter Telegram API Credentials")
    
    api_id = st.text_input("API ID")
    api_hash = st.text_input("API Hash")
    phone_number = st.text_input("Phone Number (e.g., +123456789)")

    if st.button("Next"):
        if api_id and api_hash and phone_number:
            try:
                st.session_state.client = TelegramSession(int(api_id), api_hash)
                asyncio.run(st.session_state.client.connect())
                asyncio.run(st.session_state.client.send_code(phone_number))
                st.session_state.auth_step = 2  
            except Exception as e:
                st.error(f"Error: {e}")

elif st.session_state.auth_step == 2:
    st.subheader("Step 2: Enter Verification Code")
    verification_code = st.text_input("Enter the verification code")

    if st.button("Authenticate"):
        try:
            asyncio.run(st.session_state.client.sign_in(st.session_state.phone_number, verification_code))
            st.session_state.auth_step = 3  
            st.session_state.authenticated = True
            st.success("Authentication successful!")
        except Exception as e:
            st.error(f"Error: {e}")

elif st.session_state.auth_step == 3 and st.session_state.authenticated:
    st.subheader("Fetch Telegram Channel Info")

    channel_input = st.text_area("Enter Telegram channel usernames (comma-separated):", "")

    if st.button("Fetch Channel Info"):
        async def fetch_info():
            channel_list = [channel.strip() for channel in channel_input.split(",") if channel.strip()]
            results = []
            for channel in channel_list:
                channel_info = await get_channel_info(st.session_state.client.client, channel)
                results.append(channel_info)
            return results

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
