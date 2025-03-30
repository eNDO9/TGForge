import pandas as pd
import time
import streamlit as st
from telethon.errors import FloodWaitError, RpcCallFailError

async def fetch_forwards(client, channel_list, start_date=None, end_date=None):
    """Fetches forwarded messages from a list of channels, with optional date range filtering."""
    all_messages_data = []
    limit = 1000  

    for channel_name in channel_list:
        try:
            channel = await client.get_entity(channel_name)
            progress_text = st.empty()
            progress_text.write(f"Processing channel: **{channel_name}**")
            offset_id = 0
            total_messages = []
        except ValueError:
            st.error(f"Channel '{channel_name}' does not exist. Skipping.")
            continue

        try:
            while True:
                messages = await client.get_messages(channel, limit=limit, offset_id=offset_id)
                if not messages:
                    progress_text.write("No more messages in this batch.")
                    break

                # Update the progress message with a batch summary.
                first_date = messages[0].date.replace(tzinfo=None) if messages[0].date else "Unknown"
                last_date = messages[-1].date.replace(tzinfo=None) if messages[-1].date else "Unknown"
                progress_text.write(f"Processing messages from {first_date.date()} to {last_date.date()}")
                
                stop_fetching = False  # Flag to stop if we go before the start_date
                
                for message in messages:
                    message_datetime = message.date.replace(tzinfo=None) if message.date else None
                    
                    # If we've reached messages older than our start_date, break out of the loop.
                    if start_date and message_datetime and message_datetime.date() < start_date:
                        progress_text.write("Reached messages older than the start date.")
                        stop_fetching = True
                        break

                    # Only add messages within the specified range
                    if ((not start_date or (message_datetime and message_datetime.date() >= start_date)) and 
                        (not end_date or (message_datetime and message_datetime.date() <= end_date))):
                        total_messages.append(message)

                if stop_fetching:
                    break

                # Inside your while loop in fetch_messages.py:
                offset_id = messages[-1].id if messages else offset_id
                time.sleep(1)

                # Check if a cancel flag was set:
                if st.session_state.get("cancel_fetch", False):
                    progress_text.write("Canceled by user.")
                    break

            
            
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


            progress_text.write(f"Collected {len(total_messages)} messages and {len(messages_data)} forwards for channel {channel_name}.")
            all_messages_data.extend(messages_data)

        except Exception as e:
            progress_text.write(f"Error fetching forwards for {channel_name}: {e}")

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
