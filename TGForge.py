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

# Session state for authentication progress
if "auth_step" not in st.session_state:
    st.session_state.auth_step = 1  # 1: Enter credentials, 2: Enter code, 3: Authenticated
if "client_initialized" not in st.session_state:
    st.session_state.client_initialized = False  # Tracks if the client is initialized

# Cleanup function for session file
def delete_session_file():
    session_file = f"{session_path}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        st.write("Old session file deleted.")

# Step 1: Enter API ID, API Hash, and Phone Number
if st.session_state.auth_step == 1:
    st.title("Telegram API Authentication - Step 1")
    st.write("Please enter your Telegram API credentials.")

    # Input fields for API credentials
    api_id = st.text_input("API ID", key="api_id")
    api_hash = st.text_input("API Hash", key="api_hash")
    phone_number = st.text_input("Phone Number (e.g., +123456789)", key="phone_number")
    
    if st.button("Next"):
        if api_id and api_hash and phone_number:
            try:
                # Create and connect the Telegram client
                async def init_client():
                    client = TelegramClient(session_path, int(api_id), api_hash)
                    await client.connect()
                    if not await client.is_user_authorized():
                        await client.send_code_request(phone_number)
                    return client
                
                st.session_state.client = asyncio.run(init_client())
                st.session_state.client_initialized = True
                st.session_state.auth_step = 2  # Move to Step 2
            except PhoneNumberInvalidError:
                st.error("Invalid phone number. Please try again.")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.error("Please fill out all fields.")

# Step 2: Enter Verification Code
elif st.session_state.auth_step == 2:
    st.title("Telegram API Authentication - Step 2")
    st.write("A verification code has been sent to your Telegram app.")
    
    verification_code = st.text_input("Enter the verification code")
    
    if st.button("Authenticate"):
        try:
            async def verify_code():
                await st.session_state.client.sign_in(st.session_state.phone_number, verification_code)
            
            asyncio.run(verify_code())
            st.session_state.auth_step = 3  # Move to Step 3
        except PhoneCodeInvalidError:
            st.error("Invalid verification code. Please try again.")
        except Exception as e:
            st.error(f"Error: {e}")

# Step 3: Authenticated
elif st.session_state.auth_step == 3:
    st.title("Telegram API Authentication - Success!")
    st.write("You are authenticated and can now make API calls.")
    
    # Example: Fetching channel info
    channel_name = st.text_input("Enter Telegram channel username (e.g., 'unity_of_fields')")

    if st.button("Fetch Channel Info"):
        try:
            async def fetch_channel_info():
                result = await st.session_state.client(
                    functions.channels.GetFullChannelRequest(channel=channel_name)
                )
                st.write("Channel Info:", result.stringify())
            
            asyncio.run(fetch_channel_info())
        except Exception as e:
            st.error(f"Error fetching channel info: {e}")

# Debugging tools
st.write("Current State:", st.session_state.auth_step)
