import pandas as pd
import time
from telethon import functions
from telethon.errors import FloodWaitError, RpcCallFailError

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
    """
    try:
        print(f"Fetching messages for group {group_name} for participant extraction...")
        all_messages = []
        offset_id = 0
        limit = 1000
        while True:
            messages = await client.get_messages(group_name, limit=limit, offset_id=offset_id)
            if not messages:
                break
            # If messages are returned sorted by date descending,
            # check if the oldest message in this batch is older than start_date.
            if start_date and messages[-1].date:
                last_msg_date = messages[-1].date.replace(tzinfo=None).date()
                if last_msg_date < start_date:
                    break
            for message in messages:
                if message.date:
                    msg_date = message.date.replace(tzinfo=None).date()
                    if start_date and msg_date < start_date:
                        continue
                    if end_date and msg_date > end_date:
                        continue
                all_messages.append(message)
            offset_id = messages[-1].id
            time.sleep(1)
            # Check if a cancel flag was set:
            if st.session_state.get("cancel_fetch", False):
                break
                
        print(f"Fetched {len(all_messages)} messages from {group_name}")

        # Extract unique participants from message senders
        participants = {}
        for message in all_messages:
            if message.sender:
                uid = message.sender.id
                if uid not in participants:
                    participants[uid] = {
                        'User ID': uid,
                        'Username': message.sender.username if message.sender.username else 'No Username',
                        'First Name': message.sender.first_name if message.sender.first_name else 'No First Name',
                        'Last Name': message.sender.last_name if message.sender.last_name else 'No Last Name',
                    }
        df = pd.DataFrame(list(participants.values()))
        print(f"Extracted {len(df)} unique participants from messages in {group_name}")
        return df
    except Exception as e:
        print(f"Error fetching participants via messages for {group_name}: {e}")
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