from telethon.errors import RPCError

async def get_first_valid_message_date(client, channel):
    """Find the date of the first user-generated message."""
    try:
        async for message in client.iter_messages(channel, reverse=True):
            if message and not message.action:
                if message.text or message.media:
                    return message.date.isoformat()
        return "No user-generated messages found"
    except Exception as e:
        return f"Error fetching first message: {e}"

async def get_channel_info(client, channel_name):
    """Fetch and format Telegram channel info."""
    try:
        channel = await client.get_entity(channel_name)
        result = await client(functions.channels.GetFullChannelRequest(channel=channel))
        first_message_date = await get_first_valid_message_date(client, channel)
        chat = result.chats[0]

        channel_info = {
            "Title": chat.title,
            "Description": result.full_chat.about.strip() if result.full_chat.about else 'No Description',
            "Participants": result.full_chat.participants_count if hasattr(result.full_chat, 'participants_count') else 'Not Available',
            "Channel Creation Date": first_message_date,
            "Primary Username": f"@{chat.username}" if chat.username else "No Username",
            "Chat ID": chat.id,
            "Access Hash": chat.access_hash,
            "Verified": "Yes" if chat.verified else "No",
            "Scam": "Yes" if chat.scam else "No",
        }
        return channel_info
    except RPCError as e:
        return {"Error": f"RPC Error: {e}"}
    except Exception as e:
        return {"Error": f"Could not fetch info for {channel_name}: {e}"}