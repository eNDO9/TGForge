import streamlit as st
from telethon import TelegramClient
import asyncio

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
if api_id and api_hash and phone:
    try:
        # Initialize TelegramClient without starting any event loop
        client = TelegramClient('my_session', api_id, api_hash)
        st.write("Credentials loaded. You can proceed with authentication.")
    except Exception as e:
        st.error(f"Error initializing Telegram client: {e}")

# Step 2: Run authentication and wait for the verification code
async def authenticate_client():
    await client.connect()
    if not await client.is_user_authorized():
        try:
            await client.send_code_request(phone)
            st.write("A verification code has been sent to your Telegram account.")
            
            verification_code = st.text_input("Enter the verification code:", "")
            if st.button("Verify"):
                await client.sign_in(phone, verification_code)
                st.success("Authentication successful!")
        except Exception as e:
            st.error(f"Error during authentication: {e}")

# Step 3: Function to handle running async code in a new event loop
def run_async_in_loop(coro):
    # Create a new event loop and run the async function within it
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    result = new_loop.run_until_complete(coro)
    new_loop.close()
    return result

if st.button("Authenticate"):
    if client:
        # Print user's credentials for testing purposes
        st.write(f"API ID: {api_id}")
        st.write(f"API Hash: {api_hash}")
        st.write(f"Phone: {phone}")
        
        run_async_in_loop(authenticate_client())
    else:
        st.error("Please provide valid API ID, API Hash, and Phone Number.")
