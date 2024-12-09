import streamlit as st
from telethon import TelegramClient, functions
from telethon.errors import PhoneNumberInvalidError, PhoneCodeInvalidError
import asyncio
import os
import nest_asyncio

# Allow nested loops for Streamlit compatibility
nest_asyncio.apply()

# Define session file path
session_path = "my_telegram_session"

# Cache Telegram client initialization
@st.cache_resource
def create_client(api_id, api_hash):
    """Create a new Telegram client and return it."""
    client = TelegramClient(session_path, api_id, api_hash)
    asyncio.set_event_loop(asyncio.new_event_loop())  # Ensure a fresh event loop
    asyncio.get_event_loop().run_until_complete(client.connect())
    return client

# Handle Step 1: Enter credentials
if "auth_step" not in st.session_state:
    st.session_state.auth_step = 1  # 1: Enter credentials, 2: Enter code, 3: Authenticated

if st.session_state.auth_step == 1:
    st.title("Telegram API Authentication - Step 1")
    st.write("Enter your Telegram API credentials.")

    api_id = st.text_input("API ID", key="api_id")
    api_hash = st.text_input("API Hash", key="api_hash")
    phone_number = st.text_input("Phone Number (e.g., +123456789)", key="phone_number")

    if st.button("Next"):
        if api_id and api_hash and phone_number:
            try:
                st.session_state.client = create_client(int(api_id), api_hash)
                asyncio.get_event_loop().run_until_complete(
                    st.session_state.client.send_code_request(phone_number)
                )
                st.session_state.auth_step = 2  # Move to Step 2
            except PhoneNumberInvalidError:
                st.error("Invalid phone number. Please try again.")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.error("Please fill out all fields.")

# Handle Step 2: Enter verification code
elif st.session_state.auth_step == 2:
    st.title("Telegram API Authentication - Step 2")
    st.write("A verification code has been sent to your Telegram app.")

    verification_code = st.text_input("Enter the verification code")

    if st.button("Authenticate"):
        try:
            asyncio.get_event_loop().run_until_complete(
                st.session_state.client.sign_in(st.session_state.phone_number, verification_code)
            )
            st.session_state.auth_step = 3  # Move to Step 3
        except PhoneCodeInvalidError:
            st.error("Invalid verification code. Please try again.")
        except Exception as e:
            st.error(f"Error: {e}")

# Handle Step 3: Authenticated
elif st.session_state.auth_step == 3:
    st.title("Telegram API Authentication - Success!")
    st.write("You are authenticated and can now make API calls.")

    channel_name = st.text_input("Enter Telegram channel username (e.g., 'unity_of_fields')")

    if st.button("Fetch Channel Info"):
        try:
            async def fetch_channel_info():
                result = await st.session_state.client(
                    functions.channels.GetFullChannelRequest(channel=channel_name)
                )
                st.write("Channel Info:", result.stringify())

            asyncio.get_event_loop().run_until_complete(fetch_channel_info())
        except Exception as e:
            st.error(f"Error fetching channel info: {e}")

# Debugging utilities
st.write("Current State:", st.session_state.auth_step)
