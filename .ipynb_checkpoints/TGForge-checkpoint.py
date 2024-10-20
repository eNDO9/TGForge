import streamlit as st
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
import os

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
    # Print the saved information
    st.write("Credentials:")
    st.write(f"API ID: {st.secrets['telegram']['api_id']}")
    st.write(f"API Hash: {st.secrets['telegram']['api_hash']}")
    st.write(f"Phone: {st.secrets['telegram']['phone']}")
    st.write(f"Session File Path: {session_path}.session")
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

    # Function to authenticate the user
    def authenticate_client(api_id, api_hash, phone):
        try:
            # Delete existing session file if there is any
            delete_session_file(session_path)
            
            # Create a new TelegramClient instance
            client = TelegramClient(session_path, api_id, api_hash)
            client.connect()

            # Check if already authorized
            if not client.is_user_authorized():
                client.send_code_request(phone)
                st.write("A verification code has been sent to your Telegram account.")
                
                st.session_state.verification_code = st.text_input("Enter the verification code:", "")

                if st.button("Verify"):
                    client.sign_in(phone, st.session_state.verification_code)
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
            client.disconnect()

        except SessionPasswordNeededError:
            st.error("Your account is protected by a password. Please disable it for this demo.")
        except Exception as e:
            st.error(f"Error during authentication: {e}")
            # Make sure to clean up session if there's an error
            delete_session_file(session_path)

    # Check if inputs are provided and start the authentication process
    if st.button("Authenticate"):
        if api_id and api_hash and phone:
            authenticate_client(api_id, api_hash, phone)
        else:
            st.error("Please enter valid API ID, API Hash, and Phone Number.")

# Automatically delete existing session if the "database is locked" error occurs
try:
    delete_session_file(session_path)
except Exception as e:
    st.write("Attempting to resolve potential session issues...")
    delete_session_file(session_path)