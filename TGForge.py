import streamlit as st
from telethon import TelegramClient, functions
from telethon.errors import SessionPasswordNeededError
import nest_asyncio
import asyncio
import os

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Define session file path
session_dir = os.getcwd()
session_path = os.path.join(session_dir, "my_telegram_session")

# Function to delete the session file
def delete_session_file(session_path):
    session_file = f"{session_path}.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        st.write("Existing session file deleted. You can try authenticating again.")

# Check if session file exists to determine authentication status
if os.path.exists(f"{session_path}.session"):
    st.title("Authenticated")
    st.write("You are authenticated. You can now fetch information from Telegram channels.")
else:
    # Load default credentials from st.secrets
    default_api_id = st.secrets["telegram"].get("api_id", "")
    default_api_hash = st.secrets["telegram"].get("api_hash", "")
    default_phone = st.secrets["telegram"].get("phone", "")

    # Step 1: Create Streamlit input fields for user credentials
    st.title("Telegram Authentication")
    st.write("Enter your Telegram API credentials to authenticate.")

    # Prompt user to input their credentials, with defaults pre-filled
    api_id = st.text_input("API ID", value=default_api_id)
    api_hash = st.text_input("API Hash", value=default_api_hash)
    phone = st.text_input("Phone Number (e.g., +1 5718671248)", value=default_phone)

    # Store verification code entry in session state to ensure it only appears during authentication
    if "verification_code" not in st.session_state:
        st.session_state.verification_code = ""

    # Function to authenticate the user asynchronously
    async def authenticate_client(api_id, api_hash, phone):
        try:
            # Delete existing session file if there is any
            delete_session_file(session_path)
            
            # Create a new TelegramClient instance
            client = TelegramClient(session_path, api_id, api_hash)
            await client.connect()

            # Check if already authorized
            if not await client.is_user_authorized():
                await client.send_code_request(phone)
                st.write("A verification code has been sent to your Telegram account.")
                
                st.session_state.verification_code = st.text_input("Enter the verification code:", "")

                if st.button("Verify"):
                    await client.sign_in(phone, st.session_state.verification_code)
                    st.success("Authentication successful!")
                    
                    # Save the credentials to Streamlit secrets
                    st.secrets["telegram"] = {
                        "api_id": api_id,
                        "api_hash": api_hash,
                        "phone": phone
                    }
                    
                    # Show confirmation message and reload the app to show "Authenticated"
                    st.session_state.authenticated = True
                    st.experimental_rerun()

            else:
                st.success("Already authenticated.")
                st.session_state.authenticated = True
                
            # Disconnect after authentication to avoid database locks
            await client.disconnect()

        except SessionPasswordNeededError:
            st.error("Your account is protected by a password. Please disable it for this demo.")
        except Exception as e:
            st.error(f"Error during authentication: {e}")
            # Make sure to clean up session if there's an error
            delete_session_file(session_path)

    # Check if inputs are provided and start the authentication process
    if st.button("Authenticate"):
        if api_id and api_hash and phone:
            asyncio.run(authenticate_client(api_id, api_hash, phone))
        else:
            st.error("Please enter valid API ID, API Hash, and Phone Number.")

# Automatically delete existing session if the "database is locked" error occurs
try:
    delete_session_file(session_path)
except Exception as e:
    st.write("Attempting to resolve potential session issues...")
    delete_session_file(session_path)

# If authenticated, show option to fetch Telegram channel info
if st.session_state.get("authenticated") or os.path.exists(f"{session_path}.session"):
    st.title("Fetch Telegram Channel Information")
    
    # Input: channel name
    channel_name = st.text_input("Enter the Telegram channel username (e.g., 'unity_of_fields'): ")
    
    # Function to get basic channel info
    async def get_channel_info(channel_name):
        try:
            client = TelegramClient(session_path, st.secrets["telegram"]["api_id"], st.secrets["telegram"]["api_hash"])
            await client.connect()
            
            # Fetch channel information
            result = await client(functions.channels.GetFullChannelRequest(channel=channel_name))
            chat = result.chats[0]

            # Extract relevant channel information
            title = chat.title
            description = result.full_chat.about.strip() if result.full_chat.about else 'No Description'
            participants_count = result.full_chat.participants_count if hasattr(result.full_chat, 'participants_count') else 'Not Available'

            # Display the gathered information
            st.write(f"Channel Information for {title}:")
            st.write(f"Title: {title}")
            st.write(f"Description: {description}")
            st.write(f"Number of Participants: {participants_count}")

            await client.disconnect()

        except Exception as e:
            st.error(f"Error fetching info for {channel_name}: {e}")

    # Button to fetch the information
    if st.button("Fetch Channel Info"):
        if channel_name:
            asyncio.run(get_channel_info(channel_name))
        else:
            st.error("Please enter a channel name.")
