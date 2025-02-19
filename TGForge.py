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

# --- Function to Get First Available User-Generated Message ---
async def get_first_valid_message_date(client, channel):
    """Finds the date of the earliest available user-generated message in a channel."""
    try:
        async for message in client.iter_messages(channel, reverse=True):
            if message and not message.action:
                if message.text or message.media:
                    return message.date.isoformat()
        return "No user-generated messages found"
    except Exception as e:
        return f"Error fetching first message: {e}"

# --- Function to Fetch Channel Info ---
async def get_channel_info(client, channel_name):
    """Fetches and formats information about a Telegram channel."""
    try:
        channel = await client.get_entity(channel_name)
        result = await client(functions.channels.GetFullChannelRequest(channel=channel))

        first_message_date = await get_first_valid_message_date(client, channel)
        chat = result.chats[0]

        title = chat.title
        description = result.full_chat.about.strip() if result.full_chat.about else 'No Description'
        participants_count = result.full_chat.participants_count if hasattr(result.full_chat, 'participants_count') else 'Not Available'

        try:
            if chat.username:
                primary_username = chat.username
                backup_usernames = 'None'
            elif chat.usernames:
                active_usernames = [u.username for u in chat.usernames if u.active]
                primary_username = active_usernames[0] if active_usernames else 'No Username'
                backup_usernames = ', '.join(active_usernames[1:]) if len(active_usernames) > 1 else 'None'
            else:
                primary_username = 'No Username'
                backup_usernames = 'None'
        except Exception as e:
            print(f"Error processing usernames for {channel_name}: {e}")
            primary_username = 'No Username'
            backup_usernames = 'None'
        
        url = f"https://t.me/{primary_username}" if primary_username != 'No Username' else "No public URL available"
        chat_type = 'Channel' if chat.broadcast else 'Group'
        chat_id = chat.id
        access_hash = chat.access_hash
        restricted = 'Yes' if chat.restricted else 'No'
        scam = 'Yes' if chat.scam else 'No'
        verified = 'Yes' if chat.verified else 'No'

        channel_info = {
            "Title": title,
            "Description": description,
            "Number of Participants": participants_count,
            "Channel Creation Date": first_message_date,
            "Primary Username": f"@{primary_username}",
            "Backup Usernames": backup_usernames,
            "URL": url,
            "Chat Type": chat_type,
            "Chat ID": chat_id,
            "Access Hash": access_hash,
            "Restricted": restricted,
            "Scam": scam,
            "Verified": verified
        }

        return channel_info

    except Exception as e:
        return {"Error": f"Could not fetch info for {channel_name}: {e}"}

# --- Streamlit UI ---
st.title("Telegram API Authentication")

# --- Step 1: Ask for API Credentials ---
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
        if st.button("Fetch Channel Info"):
            st.write("Fetching channel info...")  # Debugging Step 1
    
            async def fetch_info():
                channel_list = [channel.strip() for channel in channel_input.split(",") if channel.strip()]
                results = []
    
                for channel in channel_list:
                    st.write(f"**Processing channel: {channel}**")  # Debugging Step 2
                    try:
                        channel_info = await get_channel_info(st.session_state.client, channel)
                        results.append(channel_info)
                    except Exception as e:
                        st.error(f"Failed to fetch info for {channel}: {e}")
    
                return results, channel_list  # ✅ Now returning `channel_list`
    
            channel_data, channel_list = st.session_state.event_loop.run_until_complete(fetch_info())
    
            if not channel_data:
                st.error("No channel data retrieved. Check if channels exist.")
    
            # --- Display Results ---
            for info in channel_data:
                if "Error" in info:
                    st.error(info["Error"])
                else:
                    st.markdown("### 📌 Channel Information")
                    for key, value in info.items():
                        st.write(f"**{key}:** {value}")
                    st.markdown("---")  # Separator
    
            # ✅ Now using correctly defined `channel_list`
            if export_option in ["Save as Excel", "Print & Save as Excel"]:
                df = pd.DataFrame(channel_data)
                filename = f"{channel_list[0]}.xlsx" if len(channel_list) == 1 else "multiple_channels_info.xlsx"
                df.to_excel(filename, index=False)
                st.success(f"Channel info saved as '{filename}'")

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
    
    # Ensure UI Loads Properly
    st.write("Enter Telegram channel usernames below and click Fetch Channel Info.")

    # User Input
    channel_input = st.text_area("Enter Telegram channel usernames (comma-separated):", "unity_of_fields")

    # Export Options
    export_option = st.radio("Export Options:", ["Print Only", "Save as Excel", "Print & Save as Excel"])

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("Fetch Channel Info"):
            st.write("Fetching channel info...")  # Debugging Step 1

            async def fetch_info():
                channel_list = [channel.strip() for channel in channel_input.split(",") if channel.strip()]
                results = []

                for channel in channel_list:
                    st.write(f"**Processing channel: {channel}**")  # Debugging Step 2
                    try:
                        channel_info = await get_channel_info(st.session_state.client, channel)
                        results.append(channel_info)
                    except Exception as e:
                        st.error(f"Failed to fetch info for {channel}: {e}")

                return results

            channel_data = st.session_state.event_loop.run_until_complete(fetch_info())

            # Ensure something is printed if data is empty
            if not channel_data:
                st.error("No channel data retrieved. Check if channels exist.")

            # --- Display Results ---
            for info in channel_data:
                if "Error" in info:
                    st.error(info["Error"])
                else:
                    st.markdown("### Channel Information")
                    for key, value in info.items():
                        st.write(f"**{key}:** {value}")
                    st.markdown("---")  # Separator

            # --- Export to Excel ---
            if export_option in ["Save as Excel", "Print & Save as Excel"]:
                df = pd.DataFrame(channel_data)
                filename = f"{channel_list[0]}.xlsx" if len(channel_list) == 1 else "multiple_channels_info.xlsx"
                df.to_excel(filename, index=False)
                st.success(f"Channel info saved as '{filename}'")

            if export_option in ["Print Only", "Print & Save as Excel"]:
                for info in channel_data:
                    print("\nProcessing channel:")
                    for key, value in info.items():
                        print(f"{key}: {value}")
                    print("=" * 60)

    with col2:
        if st.button("Logout"):
            delete_session_file()
