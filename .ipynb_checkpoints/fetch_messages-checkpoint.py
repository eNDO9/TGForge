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
    limit = 1000  

    for channel_name in channel_list:
        try:
            print(f"Fetching data for channel: {channel_name}")
            channel = await client.get_entity(channel_name)

            offset_id = 0
            total_messages = []

            while True:
                try:
                    messages = await client.get_messages(channel, limit=limit, offset_id=offset_id)
                    if not messages:
                        break

                    total_messages.extend(messages)
                    offset_id = messages[-1].id
                    time.sleep(1)

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

    # Generate Analytics (Hashtags, URLs, Volume Trends)
    def process_hashtags(df):
        df["Hashtags"] = df["Hashtags"].apply(lambda x: x if isinstance(x, list) else [])
        hashtags_list = df["Hashtags"].explode().dropna().tolist()
        hashtags_counter = Counter(hashtags_list)
        return pd.DataFrame(hashtags_counter.items(), columns=["Hashtag", "Count"]).sort_values(by="Count", ascending=False).head(50)

    def process_urls(df):
        df["URLs Shared"] = df["URLs Shared"].apply(lambda x: x if isinstance(x, list) else [])

        # Flatten the list of URLs, remove unwanted trailing characters, and normalize
        urls_list = [
            re.sub(r"[),]+$", "", re.sub(r"^https?://(www\.)?", "", url)).rstrip(".,)").lower()
            for url in df["URLs Shared"].explode().dropna().tolist()
        ]
        # Count occurrences of each cleaned URL
        urls_counter = Counter(urls_list)
        # Convert the counter to a DataFrame, sort by count, and limit to top 50
        return pd.DataFrame(urls_counter.items(), columns=["URL", "Count"]).sort_values(by="Count", ascending=False).head(50)
    
    # ✅ Process Forward Counts
    def process_forwards(df):
        fwd_df = df[df["Is Forward"] == True]  # ✅ Filter forwarded messages
        fwd_df = fwd_df[~fwd_df["Origin Username"].isin(["Unknown", "Not Available"])]  # ✅ Exclude unknown sources

        # ✅ Generate forward counts
        fwd_counts_df = fwd_df.groupby(["Channel", "Origin Username"]).size().reset_index(name="Count")
        fwd_counts_df = fwd_counts_df.pivot(index="Origin Username", columns="Channel", values="Count").fillna(0)

        # ✅ Add "Total Forwards" column & sort
        fwd_counts_df["Total Forwards"] = fwd_counts_df.sum(axis=1)
        fwd_counts_df = fwd_counts_df.sort_values(by="Total Forwards", ascending=False).reset_index()

        return fwd_counts_df
    
        def generate_volume_by_period(df, period):
            df["Message DateTime (UTC)"] = pd.to_datetime(df["Message DateTime (UTC)"])

            # Get the actual first and last message dates
            first_message_date = df["Message DateTime (UTC)"].min()
            last_message_date = pd.Timestamp.today().normalize()  # End at today

            # Adjust start_date based on period type
            if period == "D":  # Daily (No change needed)
                start_date = first_message_date.normalize()
                freq = "D"
            elif period == "W":  # Weekly (Start from the first Monday before first message)
                start_date = first_message_date - pd.DateOffset(days=first_message_date.weekday())
                freq = "W-MON"
            elif period == "M":  # Monthly (Start from the first day of the first message's month)
                start_date = first_message_date.replace(day=1)
                freq = "MS"

            # Create full date range
            all_dates = pd.date_range(start=start_date, end=last_message_date, freq=freq)
            # Group by the specified period and count messages per channel
            volume = df.groupby([df["Message DateTime (UTC)"].dt.to_period(period), "Channel"]).size().unstack(fill_value=0)
            # Add a 'Total' column summing across all channels
            volume["Total"] = volume.sum(axis=1)
            # Convert the period back to timestamps for reindexing
            volume.index = volume.index.to_timestamp()
            # Reindex with the full date range and fill missing values with 0
            volume = volume.reindex(all_dates, fill_value=0)
            return volume

    
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


    # Compute top analytics
    top_domains_df = process_domains(df)
    forward_counts_df = process_forwards(df)
    daily_volume = generate_volume_by_period(df, "D")
    weekly_volume = generate_volume_by_period(df, "W")
    monthly_volume = generate_volume_by_period(df, "M")
    top_hashtags_df = process_hashtags(df)
    top_urls_df = process_urls(df)

    return df, top_hashtags_df, top_urls_df, top_domains_df, forward_counts_df, daily_volume, weekly_volume, monthly_volume
