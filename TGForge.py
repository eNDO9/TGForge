import streamlit as st
from telethon import TelegramClient, functions
from telethon.errors import PhoneNumberInvalidError, PhoneCodeInvalidError, SessionPasswordNeededError
import asyncio
import os
import pandas as pd
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
    st.success("Session reset successfully. Start again.")

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

# --- Function to Get First Available User-Generated Message ---
async def get_first_valid_message_date(client, channel_name):
    """Finds the date of the earliest available user-generated message in a channel."""
    try:
        channel = await client.get_entity(channel_name)
        async for message in client.iter_messages(channel, reverse=True):
            if message and not message.action:
                if message.text or message.media:
                    return message.date.isoformat()
        return "No user-generated messages found"
    except Exception as e:
        st.error(f"Error fetching first message for {channel_name}: {e}")
        return "Not Available"

# --- Function to Fetch Channel Info ---
async def get_channel_info(client, channel_name):
    """Fetches and prints detailed information about a Telegram channel."""
    try:
        result = await client(functions.channels.GetFullChannelRequest(channel=channel_name))
        first_message_date = await get_first_valid_message_date(client, channel_name)
        chat = result.chats[0]

        title = chat.title
        description = result.full_chat.about.strip() if result.full_chat.about else 'No Description'
        participants_count = result.full_chat.participants_count if hasattr(result.full_chat, 'participants_count') else 'Not Available'

        primary_username = f"@{chat.username}" if chat.username else "No Username"
        url = f"https://t.me/{chat.username}" if chat.username else "No public URL available"

        chat_info = {
            "Title": title,
            "Description": description,
            "Participants": participants_count,
            "First Message Date": first_message_date,
            "Username": primary_username,
            "URL": url,
            "Chat Type": "Channel" if chat.broadcast else "Group",
            "Chat ID": chat.id,
            "Restricted": "Yes" if chat.restricted else "No",
            "Scam": "Yes" if chat.scam else "No",
            "Verified": "Yes" if chat.verified else "No"
        }

        return chat_info

    except Exception as e:
        st.error(f"Error fetching channel info: {e}")
        return None

# --- Streamlit UI ---
st.title("Telegram API Authentication")

# --- Step 1: Ask for API Credentials ---
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

                st.session_state.event_loop.run_until_complete(sign_in())
                st.session_state.auth_step = 3  
                st.session_state.authenticated = True
                st.success("Authentication successful!")

            except PhoneCodeInvalidError:
                st.error("Invalid verification code. Please try again.")
            except SessionPasswordNeededError:
                st.error("Two-step verification is enabled. This script does not handle passwords.")
            except Exception as e:
                st.error(f"Error: {e}")

    with col2:
        if st.button("Reset Session"):
            delete_session_file()

# --- Step 3: Fetch Channel Info ---
elif st.session_state.auth_step == 3 and st.session_state.authenticated:
    st.subheader("Authenticated!")
    channel_name = st.text_input("Enter Telegram channel username (e.g., 'unity_of_fields')")

    export_option = st.radio("Export Options:", ["Print Only", "Save as Excel", "Print & Save as Excel"])

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("Fetch Channel Info"):
            async def fetch_info():
                return await get_channel_info(st.session_state.client, channel_name)

            channel_info = st.session_state.event_loop.run_until_complete(fetch_info())

            if channel_info:
                st.json(channel_info)  # Display formatted JSON

                if export_option in ["Save as Excel", "Print & Save as Excel"]:
                    df = pd.DataFrame([channel_info])
                    df.to_excel("Telegram_Channel_Info.xlsx", index=False)
                    st.success("Channel info saved as 'Telegram_Channel_Info.xlsx'")

                if export_option in ["Print Only", "Print & Save as Excel"]:
                    print("Channel Info:", channel_info)

    with col2:
        if st.button("Logout"):
            delete_session_file()
