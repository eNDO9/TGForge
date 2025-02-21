import pandas as pd
import time
import re
import socket
from collections import Counter
from urllib.parse import urlparse
from telethon.errors import FloodWaitError, RpcCallFailError
from telethon.tl.types import PeerUser


async def fetch_messages(client, channel_list):
    """Fetches messages from a list of Telegram channels and processes relevant metadata."""
    all_messages_data = []
    limit = 1000  # Adjust limit per batch

    for channel_name in channel_list:
        try:
            print(f"Fetching data for channel: {channel_name}")
            channel = await client.get_entity(channel_name)

            offset_id = 0
            total_messages = []

            while True:
                try:
                    print(f"Fetching messages from {channel_name} with offset {offset_id}...")
                    messages = await client.get_messages(channel, limit=limit, offset_id=offset_id)
                    if not messages:
                        break

                    total_messages.extend(messages)
                    offset_id = messages[-1].id

                    time.sleep(1)  # Respectful delay

                except FloodWaitError as e:
                    print(f"Flood wait error. Waiting {e.seconds} seconds...")
                    time.sleep(e.seconds + 1)

                except RpcCallFailError as e:
                    print(f"Telegram internal error: {e}. Retrying in 5 seconds...")
                    time.sleep(5)

            print(f"Fetched {len(total_messages)} messages from {channel_name}")

            # Process messages
            messages_data = []
            for message in total_messages:
                message_datetime = message.date.replace(tzinfo=None) if message.date else "Not Available"
                message_type = type(message.media).__name__ if message.media else "Text"
                is_forward = bool(message.forward)
                urls_shared = re.findall(r"(https?://\S+)", message.text) if message.text else []
                hashtags = [tag for tag in message.text.split() if tag.startswith("#")] if message.text else []
                reactions = sum([reaction.count for reaction in message.reactions.results]) if message.reactions else 0
                geo_location = f"{message.geo.lat}, {message.geo.long}" if message.geo else "None"

                original_username = "Not Available"
                if is_forward:
                    try:
                        if message.forward.chat and hasattr(message.forward.chat, "username"):
                            original_username = message.forward.chat.username
                    except AttributeError:
                        original_username = "Unknown"

                message_url = f"https://t.me/{channel.username}/{message.id}" if hasattr(channel, "username") else "No URL available"

                message_data = {
                    "Channel": channel_name,
                    "Message ID": message.id,
                    "Sender User ID": message.from_id.user_id if isinstance(message.from_id, PeerUser) else channel_name,
                    "Sender Username": message.sender.username if message.sender and hasattr(message.sender, "username") else "Not Available",
                    "Message DateTime (UTC)": message_datetime,
                    "Text": message.text,
                    "Message Type": message_type,
                    "Is Forward": is_forward,
                    "Origin Username": original_username,
                    "Geo-location": geo_location,
                    "Hashtags": hashtags,
                    "URLs Shared": urls_shared,
                    "Reactions": reactions,
                    "Message URL": message_url,
                    "Views": message.views if message.views else None,
                    "Forwards": message.forwards if message.forwards else None,
                    "Replies": message.replies.replies if message.replies else "No Replies",
                }

                messages_data.append(message_data)

            print(f"Finished processing messages for {channel_name}. Total messages collected: {len(messages_data)}\n")
            all_messages_data.extend(messages_data)

        except Exception as e:
            print(f"Error fetching messages for {channel_name}: {e}")

    # Convert to DataFrame
    df = pd.DataFrame(all_messages_data)

    # ✅ Process Domains from URLs
    def process_domains(df):
        df["URLs Shared"] = df["URLs Shared"].apply(lambda x: x if isinstance(x, list) else [])

        domains_list = [
            re.sub(r"[^\w.-]+$", "", re.sub(r"^www\.", "", urlparse(url).netloc)).lower()
            for url in df["URLs Shared"].explode().dropna().tolist()
            if urlparse(url).netloc
        ]

        domains_counter = Counter(domains_list)
        return pd.DataFrame(domains_counter.items(), columns=["Domain", "Count"]).sort_values(by="Count", ascending=False).head(50)

    # ✅ Process Forward Counts
    def process_forwards(df):
        fwd_df = df[df["Is Forward"] == True]
        fwd_df = fwd_df[~fwd_df["Origin Username"].isin(["Unknown", "Not Available"])]
        fwd_counts = fwd_df.groupby(["Channel", "Origin Username"]).size().reset_index(name="Count")
        return fwd_counts.pivot(index="Origin Username", columns="Channel", values="Count").fillna(0)

    # ✅ Generate Volume Over Time
    def generate_volume_by_period(df, period):
        df["Message DateTime (UTC)"] = pd.to_datetime(df["Message DateTime (UTC)"])
        volume = df.groupby([df["Message DateTime (UTC)"].dt.to_period(period), "Channel"]).size().unstack(fill_value=0)
        volume["Total"] = volume.sum(axis=1)
        volume.index = volume.index.to_timestamp()
        return volume

    # Compute top analytics
    top_domains_df = process_domains(df)
    forward_counts_df = process_forwards(df)
    daily_volume = generate_volume_by_period(df, "D")
    weekly_volume = generate_volume_by_period(df, "W")
    monthly_volume = generate_volume_by_period(df, "M")

    return df, top_domains_df, forward_counts_df, daily_volume, weekly_volume, monthly_volume
