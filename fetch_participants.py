import pandas as pd
import time
from telethon import functions
from telethon.errors import FloodWaitError, RpcCallFailError
from telethon.tl.types import User
import streamlit as st

async def fetch_default_participants(client, group_name):
    """Fetch participants of a Telegram group using a direct API request."""
    try:
        print(f"Fetching participants for group: {group_name}...")
        # Fetch full channel info to get reported members count
        result = await client(functions.channels.GetFullChannelRequest(channel=group_name))
        reported_participants_count = result.full_chat.participants_count if hasattr(result.full_chat, "participants_count") else "Not Available"
        print(f"Reported members for {group_name}: {reported_participants_count}")

        # Fetch all participants (adjust limit if needed)
        participants = await client.get_participants(group_name, limit=200000)
        print(f"Fetched {len(participants)} participants for {group_name}")

        members_data = []
        for user in participants:
            user_data = {
                'User ID': user.id,
                'Deleted': user.deleted,
                'Is Bot': user.bot,
                'Verified': user.verified,
                'Restricted': user.restricted,
                'Scam': user.scam,
                'Fake': user.fake,
                'Premium': getattr(user, 'premium', False),
                'Access Hash': user.access_hash,
                'First Name': user.first_name if user.first_name else 'No First Name',
                'Last Name': user.last_name if user.last_name else 'No Last Name',
                'Username': user.username if user.username else 'No Username',
                'Phone': user.phone if user.phone else 'No Phone',
                'Status': str(user.status),
                'Timezone Info': user.status.was_online.tzinfo if hasattr(user.status, 'was_online') else 'Not Available',
                'Restriction Reason': ', '.join(r.text for r in user.restriction_reason) if user.restriction_reason else 'None',
                'Language Code': user.lang_code if user.lang_code else 'Unknown',
                'Last Seen': user.status.was_online.isoformat() if hasattr(user.status, 'was_online') else 'Not Available',
                'Profile Picture DC ID': user.photo.dc_id if user.photo else 'No DC ID',
                'Profile Picture Photo ID': user.photo.photo_id if user.photo else 'No Photo ID',
                group_name: 1  # Mark membership in this group
            }
            members_data.append(user_data)
        df = pd.DataFrame(members_data)
        print(f"Collected data for {len(df)} members in {group_name}")
        return df, reported_participants_count
    except Exception as e:
        print(f"Error fetching participants for {group_name}: {e}")
        return pd.DataFrame(), 0

async def fetch_participants_via_messages(client, group_name, start_date=None, end_date=None):
    """
    Fetch participants from a group by collecting messages and extracting unique senders.
    Optionally filter messages by date range.
    Additionally, supplement the list with API-retrieved members, avoiding duplicates.
    Returns a DataFrame with detailed participant information.
    """
    try:
        st.write(f"Fetching messages for group '{group_name}' for participant extraction...")
        all_messages = []
        offset_id = 0
        limit = 1000
        stop_fetching = False

        # Collect messages within the date range
        while not stop_fetching:
            messages = await client.get_messages(group_name, limit=limit, offset_id=offset_id)
            if not messages:
                st.write("No more messages in batch.")
                break

            st.write(f"Fetched {len(messages)} messages in current batch.")

            for message in messages:
                if not message.date:
                    continue

                # Remove timezone info for comparison
                msg_date = message.date.replace(tzinfo=None).date()

                # Skip messages that are newer than the end_date if provided
                if end_date and msg_date > end_date:
                    continue

                # If the message is older than the start_date, stop processing further.
                if start_date and msg_date < start_date:
                    stop_fetching = True
                    break

                all_messages.append(message)

            if stop_fetching:
                st.write("Reached messages older than start_date. Stopping further fetch.")
                break

            offset_id = messages[-1].id
            time.sleep(1)

            if st.session_state.get("cancel_fetch", False):
                st.write("Fetch participants via messages cancelled by user.")
                break

        st.write(f"Total messages collected for group '{group_name}': {len(all_messages)}")

        # Extract unique participants from the collected messages.
        from telethon.tl.types import User
        participants = {}
        for message in all_messages:
            if message.sender and isinstance(message.sender, User):
                user = message.sender
                if user.id not in participants:
                    participants[user.id] = {
                        "User ID": user.id,
                        "Deleted": getattr(user, "deleted", False),
                        "Is Bot": getattr(user, "bot", False),
                        "Verified": getattr(user, "verified", False),
                        "Restricted": getattr(user, "restricted", False),
                        "Scam": getattr(user, "scam", False),
                        "Fake": getattr(user, "fake", False),
                        "Premium": getattr(user, "premium", False),
                        "Access Hash": user.access_hash,
                        "First Name": user.first_name or "No First Name",
                        "Last Name": user.last_name or "No Last Name",
                        "Username": user.username or "No Username",
                        "Phone": user.phone or "No Phone",
                        "Status": str(user.status) if user.status else "Not Available",
                    }

        st.write(f"Extracted {len(participants)} unique participants from messages for group '{group_name}'")

        # Supplement with participants retrievable via the API.
        # Note: Ensure that fetch_default_participants is imported from its module.
        from fetch_participants import fetch_default_participants
        api_df, reported_count = await fetch_default_participants(client, group_name)
        if not api_df.empty:
            for _, row in api_df.iterrows():
                user_id = row.get("User ID")
                if user_id not in participants:
                    participants[user_id] = row.to_dict()

        st.write(f"Total unique participants after merging with API data: {len(participants)}")
        return pd.DataFrame(list(participants.values()))
    except Exception as e:
        st.write(f"Error fetching participants via messages for {group_name}: {e}")
        return pd.DataFrame()

async def fetch_participants(client, group_list, method="default", start_date=None, end_date=None):
    """
    Fetch participants for each group in group_list.
    - method: "default" uses a direct API request, "messages" extracts from messages.
    Returns a unified DataFrame, total reported count, total fetched count, and a dictionary mapping each group to (reported_count, fetched_count).
    """
    all_dfs = []
    total_reported = 0
    total_fetched = 0
    group_counts = {}  # {group_name: (reported_count, fetched_count)}
    for group in group_list:
        if method == "default":
            df, reported_count = await fetch_default_participants(client, group)
            fetched_count = len(df)
            total_reported += reported_count if isinstance(reported_count, int) else 0
            total_fetched += fetched_count
            group_counts[group] = (reported_count, fetched_count)
            if not df.empty:
                all_dfs.append(df)
        elif method == "messages":
            df = await fetch_participants_via_messages(client, group, start_date, end_date)
            fetched_count = len(df)
            total_fetched += fetched_count
            group_counts[group] = ("Not Available", fetched_count)
            if not df.empty:
                df[group] = 1  # Mark membership
                all_dfs.append(df)
    if not all_dfs:
        return pd.DataFrame(), total_reported, total_fetched, group_counts
    unified_df = pd.concat(all_dfs, ignore_index=True)
    return unified_df, total_reported, total_fetched, group_counts
