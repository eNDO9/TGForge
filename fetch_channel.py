from telethon import functions

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
