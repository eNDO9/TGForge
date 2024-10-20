import streamlit as st
from telethon.sync import TelegramClient
from telethon import TelegramClient as AsyncTelegramClient, functions
from telethon.errors import SessionPasswordNeededError
import nest_asyncio
import asyncio
import pandas as pd
from docx import Document
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

# Check to ensure values are being captured correctly
st.write(f"API ID: {api_id}, API Hash: {api_hash}, Phone: {phone}")

client = None
async_client = None

# Define explicit session file path, ensure directory is visible
session_dir = os.getcwd()  # Current directory, you can change to a specific path if needed
session_path = os.path.join(session_dir, "my_telegram_session")

# Function to delete the session file
def delete_session_file(session_path):
    session_file = f"{session_path}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        st.write("Existing session file deleted. You can try authenticating again.")

# Automatically check and clean if necessary
if "retry_authentication" in st.session_state and st.session_state["retry_authentication"]:
    delete_session_file(session_path)
    st.session_state["retry_authentication"] = False

# Check if session file already exists, indicating a previous successful login
if os.path.exists(f"{session_path}.session"):
    st.session_state['authenticated'] = True
else:
    st.session_state['authenticated'] = False

if api_id and api_hash and phone:
    try:
        # Use a specified session path in the local directory
        client = TelegramClient(session_path, api_id, api_hash)
        
        # Check if the session is already authenticated
        if st.session_state.get('authenticated'):
            st.success("Already authenticated. Skipping reauthentication.")
            
            # Ensure async_client is initialized even when reusing the session
            async_client = AsyncTelegramClient(session_path, api_id, api_hash)
        else:
            st.write("Credentials loaded. You can proceed with authentication.")
    except Exception as e:
        if "database is locked" in str(e).lower():
            st.error("Database is locked. Trying to resolve...")
            # Set a flag to delete the session file and retry authentication
            st.session_state["retry_authentication"] = True
            st.warning("Database lock detected. Click 'Retry Authentication' to proceed.")
        else:
            st.error(f"Error initializing Telegram client: {e}")

# Function to authenticate synchronously
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
                st.session_state['authenticated'] = True

        else:
            # Create async client if already authorized
            async_client = AsyncTelegramClient(session_path, api_id, api_hash)
            st.success("Already authenticated. Async client ready for further operations.")
            st.session_state['authenticated'] = True

    except SessionPasswordNeededError:
        st.error("Your account is protected by a password. Please disable it for this demo.")
    except Exception as e:
        if "database is locked" in str(e).lower():
            st.error("Database is locked. Attempting to delete the session file and retry...")
            # Trigger session file deletion and prompt for retry
            st.session_state["retry_authentication"] = True
            st.warning("Click 'Retry Authentication' to proceed.")
        else:
            st.error(f"Error during authentication: {e}")
    finally:
        client.disconnect()

# Retry Button if the database is locked
if st.session_state.get("retry_authentication"):
    if st.button("Retry Authentication"):
        delete_session_file(session_path)
        st.session_state["retry_authentication"] = False
        st.experimental_rerun()