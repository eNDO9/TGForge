import streamlit as st
from telethon import TelegramClient, functions
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError, PhoneCodeInvalidError
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

# Function to get or create an event loop
def get_or_create_eventloop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError as ex:
        if "There is no current event loop in thread" in str(ex):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return asyncio.get_event_loop()

# Initialize the event loop in session state
if "loop" not in st.session_state:
    st.session_state.loop = get_or_create_eventloop()

# Check authentication status based on session file or session state
authenticated = os.path.exists(f"{session_path}.session") or st.session_state.get("authenticated")

# Input: channel name for test call, always visible
st.title("Fetch Telegram Channel Information")
channel_name = st.text_input("Enter the Telegram channel username (e.g., 'unity_of_fields') for test call:")

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
        st.session_state.loop.run_until_complete(get_channel_info(channel_name))
    else:
        st.error("Please enter a channel name.")

# Step 1: Create Streamlit input fields for user credentials if not authenticated
if not authenticated:
    st.title("Telegram Authentication")
    st.write("Enter your Telegram API credentials to authenticate.")

    # Load default credentials from st.secrets
    default_api_id = st.secrets["telegram"].get("api_id", "")
    default_api_hash = st.secrets["telegram"].get("api_hash", "")
    default_phone = st.secrets["telegram"].get("phone", "")

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
                try:
                    await client.send_code_request(phone)
                    st.write("A verification code has been sent to your Telegram account.")
                except PhoneNumberInvalidError:
                    st.error("The phone number entered is invalid. Please check and enter a valid phone number.")
                    return
                except Exception as e:
                    st.error(f"Error sending verification code: {e}")
                    return
                
                st.session_state.verification_code = st.text_input("Enter the verification code:", "")

                if st.button("Verify"):
                    try:
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
                    except PhoneCodeInvalidError:
                        st.error("The code entered is incorrect. Please check and enter the correct code.")
                    except Exception as e:
                        st.error(f"Error during verification: {e}")

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
            st.session_state.loop.run_until_complete(authenticate_client(api_id, api_hash, phone))
        else:
            st.error("Please enter valid API ID, API Hash, and Phone Number.")

# Automatically delete existing session if the "database is locked" error occurs
try:
    delete_session_file(session_path)
except Exception as e:
    st.write("Attempting to resolve potential session issues...")
    delete_session_file(session_path)
