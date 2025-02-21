from telethon import TelegramClient
import os
import streamlit as st

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