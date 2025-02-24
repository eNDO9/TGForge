import pandas as pd
import time
from telethon.errors import FloodWaitError, RpcCallFailError

async def fetch_forwards(client, channel_list, start_date=None, end_date=None):
    """Fetches forwarded messages from a list of channels, with optional date range filtering."""
    all_messages_data = []

    for channel_name in channel_list:
        try:
            print(f"Fetching data for channel: {channel_name}")
            channel = await client.get_entity(channel_name)

            limit = 1000
            offset_id = 0
            total_messages = []

            while True:
                try:
                    print(f"Fetching messages from {channel_name} with offset {offset_id}...")
                    messages = await client.get_messages(channel, limit=limit, offset_id=offset_id)
                    if not messages:
                        break

                    stop_fetching = False
                    # Process each message in this batch
                    for message in messages:
                        # Only consider forwarded messages
                        if not message.forward:
                            continue

                        # Determine the filter date: if the forwarded message has its own date, use that;
                        # otherwise, fallback to the message's date.
                        if message.forward and message.forward.date:
                            filter_date = message.forward.date.replace(tzinfo=None)
                        else:
                            filter_date = message.date.replace(tzinfo=None) if message.date else None

                        # If a start_date is provided and this message is older, signal to stop fetching further.
                        if start_date and filter_date and filter_date.date() < start_date:
                            stop_fetching = True
                            break

                        # Only include messages within the specified range
                        if ((not start_date or (filter_date and filter_date.date() >= start_date)) and 
                            (not end_date or (filter_date and filter_date.date() <= end_date))):
                            total_messages.append(message)

                    if stop_fetching:
                        break
                except FloodWaitError as e:
                    time.sleep(e.seconds + 1)
                except RpcCallFailError as e:
                    time.sleep(5)

            print(f"Fetched {len(total_messages)} messages from {channel_name}")

            # Process messages
            messages_data = []
            for message in total_messages:
                if message.forward:
                    forward_datetime = message.date.replace(tzinfo=None) if message.date else "Not Available"
                    original_message_datetime = (
                        message.forward.date.replace(tzinfo=None) if message.forward and message.forward.date else "Not Available"
                    )

                    message_type = type(message.media).__name__ if message.media else "Text"

                    original_url = "No URL available"
                    original_username = "Unknown"
                    original_chat_name = "Unknown"

                    if message.forward.chat:
                        original_chat_name = message.forward.chat.title or "Unknown"
                        if hasattr(message.forward.chat, "username"):
                            original_username = message.forward.chat.username or "Unknown"
                            original_url = f"https://t.me/{original_username}/{message.forward.channel_post}" if message.forward.channel_post else "No URL available"

                    forward_url = f"https://t.me/{channel.username}/{message.id}" if hasattr(channel, "username") else "No URL available"

                    message_data = {
                        "Channel": channel_name,
                        "Message DateTime (UTC)": original_message_datetime,
                        "Forward Datetime (UTC)": forward_datetime,
                        "Origin Username": original_username,
                        "Origin Chat Name": original_chat_name,
                        "Text": message.text,
                        "Forwarded Chat ID": message.forward.chat_id if message.forward else "Unknown",
                        "Reply To": message.reply_to_msg_id if message.reply_to_msg_id else "No Reply",
                        "Replies": message.replies.replies if message.replies else "No Replies",
                        "Views": message.views if message.views else "Not Available",
                        "Forwards": message.forwards if message.forwards else "Not Available",
                        "Message Type": message_type,
                        "Forwarded URL": forward_url,
                        "Origin URL": original_url,
                        "Grouped ID": str(message.grouped_id) if message.grouped_id else "Not Available",
                    }

                    messages_data.append(message_data)

            print(f"Finished processing messages for {channel_name}. Total forwarded messages collected: {len(messages_data)}")
            all_messages_data.extend(messages_data)

        except Exception as e:
            print(f"Error fetching forwards for {channel_name}: {e}")

    # Convert to DataFrame
    df = pd.DataFrame(all_messages_data)

    # Deduplicate based on Grouped ID
    dedup_df = df[df["Grouped ID"] != "Not Available"].drop_duplicates(subset=["Grouped ID"], keep="first")
    df = pd.concat([df[df["Grouped ID"] == "Not Available"], dedup_df]).sort_values(by=["Channel", "Message DateTime (UTC)"]).reset_index(drop=True)

    # Generate forward counts
    fwd_counts_df = df.groupby(["Channel", "Origin Username"]).size().reset_index(name="Count").pivot(index="Origin Username", columns="Channel", values="Count").fillna(0)
    fwd_counts_df["Total Forwards"] = fwd_counts_df.sum(axis=1)
    fwd_counts_df = fwd_counts_df.sort_values(by="Total Forwards", ascending=False).reset_index()

    return df, fwd_counts_df