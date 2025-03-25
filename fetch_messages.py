import pandas as pd
import time
import re
import socket
from collections import Counter
from urllib.parse import urlparse
from telethon.errors import FloodWaitError, RpcCallFailError
from telethon.tl.types import PeerUser
import streamlit as st


async def fetch_messages(client, channel_list, start_date=None, end_date=None):
    all_messages_data = []
    limit = 1000  

    for channel_name in channel_list:
        channel = await client.get_entity(channel_name)
        offset_id = 0
        total_messages = []

        try:
            while True:
                messages = await client.get_messages(channel, limit=limit, offset_id=offset_id)
                if not messages:
                    break

                stop_fetching = False  # Flag to stop if we go before the start_date
                for message in messages:
                    message_datetime = message.date.replace(tzinfo=None) if message.date else None
                    
                    # If we've reached messages older than our start_date, break out of the loop.
                    if start_date and message_datetime and message_datetime.date() < start_date:
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
                    break

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
                
                # Determine sender info
                if message.sender:
                    sender_user_id = getattr(message.sender, "id", "Not Available")
                    sender_username = getattr(message.sender, "username", "Not Available")
                else:
                    # If there's no sender, assume this is a channel post.
                    sender_user_id = getattr(channel, "id", "Not Available")
                    sender_username = getattr(channel, "username", "Not Available")
                    
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
                    "Parent Message ID": None,  # This is for main messages; replies will have an actual Parent Message ID
                    "Sender User ID": sender_user_id,
                    "Sender Username": sender_username,                 
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
                    "Reply To Message Snippet": None,
                    "Reply To Message Sender": None,
                    "Grouped ID": str(message.grouped_id) if message.grouped_id else "Not Available",
                }
                
                # Fetch Replies (Nested Comments)
                if message.replies and message.replies.replies > 0:
                    try:
                        replies = await client.get_messages(channel, reply_to=message.id, limit=100)
                        for reply in replies:
                            reply_datetime = reply.date.replace(tzinfo=None) if reply.date else "Not Available"

                            if isinstance(reply.from_id, PeerUser):
                                reply_user_id = reply.from_id.user_id
                            else:
                                reply_user_id = channel_name  # If it's from a channel, use the channel name
            
                            reply_username = (
                                reply.sender.username
                                if reply.sender and hasattr(reply.sender, "username")
                                else (channel.username if hasattr(channel, "username") else "Not Available")
                            )
                            
                            reply_data = {
                                "Channel": channel_name,
                                "Message ID": reply.id,
                                "Parent Message ID": message.id,  # Reference to original message
                                "Sender User ID": reply_user_id,
                                "Sender Username": reply_username,
                                "Message DateTime (UTC)": reply_datetime,
                                "Text": reply.text,
                                "Message Type": type(reply.media).__name__ if reply.media else "Text",
                                "Is Forward": bool(reply.forward),
                                "Origin Username": original_username,
                                "Geo-location": f"{reply.geo.lat}, {reply.geo.long}" if reply.geo else "None",
                                "Hashtags": [tag for tag in reply.text.split() if tag.startswith("#")] if reply.text else [],
                                "URLs Shared": re.findall(r"(https?://\S+)", reply.text) if reply.text else [],
                                "Reactions": sum([reaction.count for reaction in reply.reactions.results]) if reply.reactions else 0,
                                "Message URL": f"https://t.me/{channel.username}/{reply.id}" if hasattr(channel, "username") else "No URL available",
                                "Views": reply.views if reply.views else None,
                                "Forwards": reply.forwards if reply.forwards else None,
                                "Replies": reply.replies.replies if reply.replies else "No Replies",
                                "Reply To Message Snippet": message.text[:100] + "..." if message.text else "No Text",
                                "Reply To Message Sender": message.sender.username if message.sender and hasattr(message.sender, "username") else "Not Available",
                                "Grouped ID": str(reply.grouped_id) if reply.grouped_id else "Not Available",
                                "Raw Sender": message.sender
                            }
                            messages_data.append(reply_data)
                    except Exception as e:
                        print(f"Error fetching replies for message {message.id} in {channel_name}: {e}")
                        
                messages_data.append(message_data)

            print(f"Finished processing messages for {channel_name}. Total messages collected: {len(messages_data)}\n")
            all_messages_data.extend(messages_data)

        except Exception as e:
            print(f"Error fetching messages for {channel_name}: {e}")

    # Convert to DataFrame
    df = pd.DataFrame(all_messages_data)
    
    # Deduplicate based on Grouped ID
    dedup_df = df[df["Grouped ID"] != "Not Available"].drop_duplicates(subset=["Grouped ID"], keep="first")
    df = pd.concat([df[df["Grouped ID"] == "Not Available"], dedup_df]).sort_values(by=["Channel", "Message DateTime (UTC)"]).reset_index(drop=True)
    
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
    
    # Process Forward Counts
    def process_forwards(df):
        fwd_df = df[df["Is Forward"] == True]  # Filter forwarded messages
        fwd_df = fwd_df[~fwd_df["Origin Username"].isin(["Unknown", "Not Available"])]  # Exclude unknown sources

        # Generate forward counts
        fwd_counts_df = fwd_df.groupby(["Channel", "Origin Username"]).size().reset_index(name="Count")
        fwd_counts_df = fwd_counts_df.pivot(index="Origin Username", columns="Channel", values="Count").fillna(0)

        # Add "Total Forwards" column & sort
        fwd_counts_df["Total Forwards"] = fwd_counts_df.sum(axis=1)
        fwd_counts_df = fwd_counts_df.sort_values(by="Total Forwards", ascending=False).reset_index()

        return fwd_counts_df

    # Process domain counts
    def process_domains(df):
        df["URLs Shared"] = df["URLs Shared"].apply(lambda x: x if isinstance(x, list) else [])
        domains_list = [
            re.sub(r"[^\w.-]+$", "", re.sub(r"^www\.", "", urlparse(url).netloc)).lower()
            for url in df["URLs Shared"].explode().dropna().tolist()
            if urlparse(url).netloc
        ]
        domains_counter = Counter(domains_list)
        return pd.DataFrame(domains_counter.items(), columns=["Domain", "Count"]).sort_values(by="Count", ascending=False).head(50)

    def generate_daily_volume(df, start_date=None, end_date=None):
        """Generates daily message counts per channel with date range control."""
        df["Message DateTime (UTC)"] = pd.to_datetime(df["Message DateTime (UTC)"])
        df["Date"] = df["Message DateTime (UTC)"].dt.date

        # Count messages per day per channel
        daily_counts = df.groupby(["Date", "Channel"]).size().reset_index(name="Total")
        daily_counts["Date"] = pd.to_datetime(daily_counts["Date"])

        # Determine the full range based on user selection or data min/max
        if start_date is None:
            range_start = daily_counts["Date"].min()
        else:
            range_start = pd.Timestamp(start_date)
        if end_date is None:
            range_end = daily_counts["Date"].max()
        else:
            range_end = pd.Timestamp(end_date)

        # Generate full date range (all days between range_start and range_end)
        full_range = pd.date_range(start=range_start, end=range_end, freq="D")

        # Pivot the data and reindex to fill missing days with 0
        daily_counts_pivot = daily_counts.pivot(index="Date", columns="Channel", values="Total").fillna(0)
        daily_counts_pivot = daily_counts_pivot.reindex(full_range, fill_value=0)
        daily_counts_pivot = daily_counts_pivot.reset_index().rename(columns={"index": "Date"})
        return daily_counts_pivot

    def generate_weekly_volume(df, start_date=None, end_date=None):
        """Generates weekly message counts per channel with missing weeks filled with 0 and date range control."""
        df["Message DateTime (UTC)"] = pd.to_datetime(df["Message DateTime (UTC)"])
        # Compute the week (using weeks ending on Monday but reporting Tuesday as the start)
        df["Week"] = df["Message DateTime (UTC)"].dt.to_period("W-MON").dt.start_time

        weekly_counts = df.groupby(["Week", "Channel"]).size().reset_index(name="Total")
        weekly_counts["Week"] = pd.to_datetime(weekly_counts["Week"])

        if start_date is None:
            range_start = weekly_counts["Week"].min()
        else:
            range_start = pd.Timestamp(start_date)
        if end_date is None:
            range_end = weekly_counts["Week"].max()
        else:
            range_end = pd.Timestamp(end_date)

        # Generate full weekly range using the same weekday as computed (W-TUE)
        full_range = pd.date_range(start=range_start, end=range_end, freq="W-TUE")

        weekly_counts_pivot = weekly_counts.pivot(index="Week", columns="Channel", values="Total")
        weekly_counts_pivot = weekly_counts_pivot.reindex(full_range, fill_value=0)
        weekly_counts_pivot = weekly_counts_pivot.reset_index().rename(columns={"index": "Week"})
        return weekly_counts_pivot

    
    def generate_monthly_volume(df, start_date=None, end_date=None):
        """Generates monthly message counts per channel with date range control."""
        df["Message DateTime (UTC)"] = pd.to_datetime(df["Message DateTime (UTC)"])
        # Compute the first day of the month
        df["Year-Month"] = df["Message DateTime (UTC)"].dt.to_period("M").dt.start_time

        monthly_counts = df.groupby(["Year-Month", "Channel"]).size().reset_index(name="Total")
        monthly_counts["Year-Month"] = pd.to_datetime(monthly_counts["Year-Month"])

        if start_date is None:
            range_start = monthly_counts["Year-Month"].min()
        else:
            range_start = pd.Timestamp(start_date)
        if end_date is None:
            range_end = monthly_counts["Year-Month"].max()
        else:
            range_end = pd.Timestamp(end_date)

        # Generate full monthly range using Month Start frequency
        full_range = pd.date_range(start=range_start, end=range_end, freq="MS")

        monthly_counts_pivot = monthly_counts.pivot(index="Year-Month", columns="Channel", values="Total").fillna(0)
        monthly_counts_pivot = monthly_counts_pivot.reindex(full_range, fill_value=0)
        monthly_counts_pivot = monthly_counts_pivot.reset_index().rename(columns={"index": "Year-Month"})
        return monthly_counts_pivot

    # Compute top analytics
    top_domains_df = process_domains(df)
    forward_counts_df = process_forwards(df)
    top_hashtags_df = process_hashtags(df)
    top_urls_df = process_urls(df)
    
    # Add Volume Analysis
    daily_volume = generate_daily_volume(df, start_date, end_date)
    weekly_volume = generate_weekly_volume(df, start_date, end_date)
    monthly_volume = generate_monthly_volume(df, start_date, end_date)

    #st.text("DEBUG: Weekly Volume Before Returning:")
    #st.text(weekly_volume)

    return df, top_hashtags_df, top_urls_df, top_domains_df, forward_counts_df, daily_volume, weekly_volume, monthly_volume
