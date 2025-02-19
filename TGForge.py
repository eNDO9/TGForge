import streamlit as st
from telethon import TelegramClient, functions
from telethon.errors import PhoneNumberInvalidError, PhoneCodeInvalidError, SessionPasswordNeededError
import asyncio
import os
import nest_asyncio

# Allow nested async loops for Streamlit
nest_asyncio.apply()

# Define session file path
SESSION_PATH = "my_telegram_session"

# Function to delete session file and logout user
def delete_session_file():
    session_file = f"{SESSION_PATH}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        st.session_state.authenticated = False
        st.session_state.client = None
        st.session_state.auth_step = 1  # Reset authentication step
        st.success("Logged out successfully. Refresh the page to start over.")

# Function to create and return a Telegram client
def create_client(api_id, api_hash):
    return TelegramClient(SESSION_PATH, api_id, api_hash)

# Initialize session state variables
if "auth_step" not in st.session_state:
    st.session_state.auth_step = 1
    st.session_state.authenticated = False
    st.session_state.client = None

st.title("Telegram API Authentication")

# Step 1: Check if the user is already authenticated
if st.session_state.auth_step == 1:
    try:
        # Create a client instance and connect
        client = create_client(st.session_state.get("api_id", ""), st.session_state.get("api_hash", ""))
        asyncio.run(client.connect())

        # Check if the user is already authenticated
        if asyncio.run(client.is_user_authorized()):
            st.session_state.authenticated = True
            st.session_state.client = client
            st.session_state.auth_step = 3  # Move directly to authenticated state
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
                client = create_client(int(api_id), api_hash)
                st.session_state.client = client
                st.session_state.api_id = api_id
                st.session_state.api_hash = api_hash
                st.session_state.phone_number = phone_number
                
                # Connect and request a login code
                asyncio.run(client.connect())
                if not asyncio.run(client.is_user_authorized()):
                    asyncio.run(client.send_code_request(phone_number))
                
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
            asyncio.run(st.session_state.client.sign_in(st.session_state.phone_number, verification_code))
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

            asyncio.run(fetch_channel_info())
        except Exception as e:
            st.error(f"Error fetching channel info: {e}")

    # Logout button
    if st.button("Logout"):
        delete_session_file()
