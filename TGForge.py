import streamlit as st
from telethon.sync import TelegramClient  # Use synchronous version for authentication
from telethon import TelegramClient as AsyncTelegramClient  # For async operations if needed
from telethon.errors import SessionPasswordNeededError
import nest_asyncio
import asyncio
import os

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Load default credentials from st.secrets
default_api_id = st.secrets["telegram"].get("api_id", "")
default_api_hash = st.secrets["telegram"].get("api_hash", "")
default_phone = st.secrets["telegram"].get("phone", "")

# Step 1: Create Streamlit input fields for user credentials
st.title("Telegram Authentication")
st.write("Enter your Telegram API credentials or use the saved defaults.")

# Prompt user to input their credentials, with defaults pre-filled
api_id = st.text_input("API ID", value=default_api_id)
api_hash = st.text_input("API Hash", value=default_api_hash)
phone = st.text_input("Phone Number (e.g., +1 5718671248)", value=default_phone)

client = None
async_client = None

# Specify an absolute path for the session file
session_path = os.path.join(os.getcwd(), "my_telegram_session")

# Automatically delete existing session file if it exists
def delete_session_file(session_path):
    session_file = f"{session_path}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        st.write("Existing session file deleted.")

# Delete the session file if it exists
delete_session_file(session_path)

if api_id and api_hash and phone:
    try:
        # Use a specified session path for better control
        client = TelegramClient(session_path, api_id, api_hash)
        st.write("Credentials loaded. You can proceed with authentication.")
    except Exception as e:
        st.error(f"Error initializing Telegram client: {e}")

# Step 2: Function to authenticate synchronously
def authenticate_client():
    global client, async_client
    try:
        client.connect()
        if not client.is_user_authorized():
            client.send_code_request(phone)
            st.write("A verification code has been sent to your Telegram account.")
            
            verification_code = st.text_input("Enter the verification code:", "")
            if st.button("Verify"):
                client.sign_in(phone, verification_code)
                st.success("Authentication successful!")

                # Create an async client for further use, with the same session path
                async_client = AsyncTelegramClient(session_path, api_id, api_hash)
                st.write("Async client ready for further operations.")
        else:
            # Create async client if already authorized
            async_client = AsyncTelegramClient(session_path, api_id, api_hash)
            st.success("Already authenticated. Async client ready for further operations.")
    except SessionPasswordNeededError:
        st.error("Your account is protected by a password. Please disable it for this demo.")
    except Exception as e:
        st.error(f"Error during authentication: {e}")
    finally:
        client.disconnect()
        # Clean up temporary session files
        delete_session_file(session_path)

# Step 3: Authenticate on button click
if st.button("Authenticate"):
    if client:
        # Print user's credentials for testing purposes
        st.write(f"API ID: {api_id}")
        st.write(f"API Hash: {api_hash}")
        st.write(f"Phone: {phone}")
        
        authenticate_client()
    else:
        st.error("Please provide valid API ID, API Hash, and Phone Number.")

# Optional: Example of async operations (you would call this later after authentication)
async def perform_async_tasks():
    if async_client:
        await async_client.connect()
        me = await async_client.get_me()
        st.write(f"Logged in as: {me.username}")
        await async_client.disconnect()
