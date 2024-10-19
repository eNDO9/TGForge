from telethon import TelegramClient, functions
from telethon.tl.types import (
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaWebPage,
    MessageMediaContact,
)

from telethon.errors import FloodWaitError, RpcCallFailError
import asyncio
from aioconsole import ainput
import re
import time
from collections import Counter
from urllib.parse import urlparse
from datetime import datetime
import time

import socket

import pandas as pd
import os
from docx import Document

import streamlit as st


"""

User Verification

"""
# Load default credentials from st.secrets
default_api_id = st.secrets["telegram"]["api_id"]
default_api_hash = st.secrets["telegram"]["api_hash"]
default_phone = st.secrets["telegram"]["phone"]

# Step 1: Create Streamlit input fields for user credentials
st.title("Telegram Authentication")
st.write("Enter your Telegram API credentials or use the saved defaults.")

# Prompt user to input their credentials, with defaults pre-filled
api_id = st.text_input("API ID", value=default_api_id)
api_hash = st.text_input("API Hash", value=default_api_hash)
phone = st.text_input("Phone Number (e.g., +1 5718671248)", value=default_phone)

# Initialize the Telegram client with user-provided or default credentials
client = None
if api_id and api_hash and phone:
    try:
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
            
            # Prompt user to input verification code
            verification_code = st.text_input("Enter the verification code:", "")

            # Handle verification process when the code is provided
            if st.button("Verify"):
                await client.sign_in(phone, verification_code)
                st.success("Authentication successful!")
        except Exception as e:
            st.error(f"Error during authentication: {e}")

# Step 3: Create an authentication button to start the process
if st.button("Authenticate"):
    if client:
        asyncio.run(authenticate_client())
    else:
        st.error("Please provide valid API ID, API Hash, and Phone Number.")