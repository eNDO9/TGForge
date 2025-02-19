import streamlit as st
from telethon import TelegramClient, functions
from telethon.errors import PhoneNumberInvalidError, PhoneCodeInvalidError, SessionPasswordNeededError
import asyncio
import os
import nest_asyncio

# Allow nested async loops in Streamlit
nest_asyncio.apply()

# Define session file path
SESSION_PATH = "my_telegram_session"

# Function to delete session file and log out user
def delete_session_file():
    session_file = f"{SESSION_PATH}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
    st.session_state.authenticated = False
    st.session_state.client = None
    st.session_state.auth_step = 1  # Reset authentication step
    st.success("Logged out successfully. Refresh the page to start over.")

# Function to create a Telegram client
def create_client(api_id, api_hash):
    return TelegramClient(SESSION_PATH, api_id, api_hash)

# Ensure a single event loop exists
if "event_loop" not in st.session_state:
    st.session_state.event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.event_loop)

# Initialize session state variables
if "auth_step" not in st.session_state:
    st.session_state.auth_step = 1
    st.session_state.authenticated = False
    st.session_state.client = None

st.title("Telegram API Authentication")

# Step 1: Check if the user is already authenticated
if st.session_state.auth_step == 1:
    try:
        if st.session_state.client is None:
            if "api_id" in st.session_state and "api_hash" in st.session_state:
                st.session_state.client = create_client(st.session_state.api_id, st.session_state.api_hash)

        async def connect_and_check_auth():
            if st.session_state.client:
                await st.session_state.client.connect()
                return await st.session_state.client.is_user_authorized()
            return False

        # Run inside single event loop
        is_authorized = st.session_state.event_loop.run_until_complete(connect_and_check_auth())

        if is_authorized:
            st.session_state.authenticated = True
            st.session_state.auth_step = 3  # Skip to authenticated step
            st.success("You are already authenticated!")

    except Exception as e:
        st.warning(f"Session check failed: {e}")

# Step 2: If not authenticated, ask for credentials
if not st.session_state.authenticated and st.session_state.auth_step == 1:
    st.subheader("Step 1: Enter Telegram API Credentials")
    
    api_id = st.text_input("API ID", value=st.session_state.get("api_id", ""))
    api_hash = st.text_input("API Hash", value=st.session_state.get("api_hash", ""))
    phone_number = st.text_input("Phone Number (e.g., +123456789)")
    
    if st.button("Next"):
        if api_id and api_hash and phone_number:
            try:
                st.session_state.api_id = api_id
                st.session_state.api_hash = api_hash
                st.session_state.phone_number = phone_number

                # Ensure client is created
                if st.session_state.client is None:
                    st.session_state.client = create_client(int(api_id), api_hash)

                async def connect_and_send_code():
                    await st.session_state.client.connect()
                    if not await st.session_state.client.is_user_authorized():
                        await st.session_state.client.send_code_request(phone_number)
                
                # Run inside single event loop
                st.session_state.event_loop.run_until_complete(connect_and_send_code())

                st.session_state.auth_step = 2  # Move to next step
                
            except PhoneNumberInvalidError:
                st.error("Invalid phone number. Please check and try again.")
            except Exception as e:
                st.error(f"Error: {e}")

# Step 3: Enter the verification code
elif st.session_state.auth_step == 2:
    st.subheader("Step 2: Enter Verification Code")
    st.write("A verification code has been sent to your Telegram app.")

    verification_code = st.text_input("Enter the verification code")
    
    if st.button("Authenticate"):
        try:
            async def sign_in():
                await st.session_state.client.sign_in(st.session_state.phone_number, verification_code)

            st.session_state.event_loop.run_until_complete(sign_in())

            st.session_state.auth_step = 3  # Move to success step
            st.session_state.authenticated = True
            st.success("Authentication successful!")
        
        except PhoneCodeInvalidError:
            st.error("Invalid verification code. Please try again.")
        except SessionPasswordNeededError:
            st.error("Two-step verification is enabled. This script does not handle passwords.")
        except Exception as e:
            st.error(f"Error: {e}")

# Step 4: Authentication success
elif st.session_state.auth_step == 3 and st.session_state.authenticated:
    st.subheader("Authenticated!")
    st.write("You are now logged in and can make Telegram API calls.")

    channel_name = st.text_input("Enter Telegram channel username (e.g., 'unity_of_fields')")

    if st.button("Fetch Channel Info"):
        try:
            async def fetch_channel_info():
                result = await st.session_state.client(functions.channels.GetFullChannelRequest(channel=channel_name))
                st.write("Channel Info:", result.stringify())

            st.session_state.event_loop.run_until_complete(fetch_channel_info())

        except Exception as e:
            st.error(f"Error fetching channel info: {e}")

    # Logout button
    if st.button("Logout"):
        delete_session_file()
