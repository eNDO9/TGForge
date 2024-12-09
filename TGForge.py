import streamlit as st
from telethon import TelegramClient
from telethon.errors import (
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)
import asyncio
import os

nest_asyncio.apply()

# Define session file path
session_path = "my_telegram_session"

# Set up session state to track authentication progress
if "auth_step" not in st.session_state:
    st.session_state.auth_step = 1  # 1 = Enter credentials, 2 = Enter code, 3 = Authenticated
if "client" not in st.session_state:
    st.session_state.client = None

# Function to clean up session file
def delete_session_file():
    session_file = f"{session_path}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        st.write("Session file deleted.")

# Function to initialize the Telegram client
async def init_client(api_id, api_hash, phone_number):
    client = TelegramClient(session_path, api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone_number)
    return client

# Reuse or create a single event loop
def get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

if st.session_state.auth_step == 1:
    st.title("Telegram API Authentication - Step 1")
    st.write("Please enter your Telegram API credentials.")
    
    api_id = st.text_input("API ID")
    api_hash = st.text_input("API Hash")
    phone_number = st.text_input("Phone Number (e.g., +123456789)")
    
    if st.button("Next"):
        if api_id and api_hash and phone_number:
            try:
                loop = get_event_loop()  # Use the same event loop
                st.session_state.client = loop.run_until_complete(
                    init_client(int(api_id), api_hash, phone_number)
                )
                st.session_state.auth_step = 2
                st.experimental_rerun()
            except PhoneNumberInvalidError:
                st.error("Invalid phone number. Please try again.")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.error("Please fill out all fields.")

elif st.session_state.auth_step == 2:
    st.title("Telegram API Authentication - Step 2")
    st.write("A verification code has been sent to your Telegram app.")
    
    verification_code = st.text_input("Enter the verification code")
    
    if st.button("Authenticate"):
        try:
            loop = get_event_loop()
            loop.run_until_complete(
                st.session_state.client.sign_in(st.session_state.phone_number, verification_code)
            )
            st.session_state.auth_step = 3
            st.experimental_rerun()
        except PhoneCodeInvalidError:
            st.error("Invalid code. Please try again.")
        except Exception as e:
            st.error(f"Error: {e}")

# Handle Step 3: Authenticated
elif st.session_state.auth_step == 3:
    st.title("Telegram API Authentication - Success!")
    st.write("You are authenticated. You can now make API calls.")
    
    channel_name = st.text_input("Enter Telegram channel username (e.g., 'unity_of_fields')")
    
    if st.button("Fetch Channel Info"):
        try:
            async def get_channel_info():
                result = await st.session_state.client(functions.channels.GetFullChannelRequest(channel=channel_name))
                st.write("Channel Info:", result.stringify())
            
            asyncio.run(get_channel_info())
        except Exception as e:
            st.error(f"Error fetching channel info: {e}")

# Debugging utilities
st.write("Current State:", st.session_state.auth_step)
