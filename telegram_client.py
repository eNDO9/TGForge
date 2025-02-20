from telethon import TelegramClient, functions
import os

class TelegramSession:
    def __init__(self, api_id, api_hash, session_name="my_session"):
        self.client = TelegramClient(session_name, api_id, api_hash)

    async def connect(self):
        """Connect to Telegram API"""
        await self.client.connect()

    async def send_code(self, phone_number):
        """Send a login code to the phone number"""
        try:
            return await self.client.send_code_request(phone_number)
        except Exception as e:
            return f"Error: {e}"

    async def sign_in(self, phone_number, code):
        """Sign in with the code received"""
        try:
            return await self.client.sign_in(phone_number, code)
        except Exception as e:
            return f"Error: {e}"

    async def logout(self):
        """Log out and reset session"""
        await self.client.log_out()
        session_file = f"{self.client.session.filename}.session"
        if os.path.exists(session_file):
            os.remove(session_file)