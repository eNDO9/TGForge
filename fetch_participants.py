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
    Fetch participants from a group by collecting messages (filtered by date)
    and extracting unique senders, then supplement with API-retrieved members.
    
    Additionally, for each message that has replies, fetch those replies
    and extract the senders (i.e. commenters). This helps capture users who
    reply to channel posts.
    
    Returns a tuple of:
      - DataFrame with detailed participant information
      - Reported participant count (from channel info via API)
      - Fetched participant count (unique users collected)
      - A dictionary mapping the group to (reported_count, fetched_count)
    """
    try:
        # First, get reported count via the API method.
        from fetch_participants import fetch_default_participants
        api_df, api_reported_count = await fetch_default_participants(client, group_name)
        reported_count = api_reported_count if api_reported_count not in [None, 0] else "Not Available"

        st.write(f"Fetching messages for group '{group_name}' for participant extraction...")
        all_messages = []
        offset_id = 0
        limit = 1000
        stop_fetching = False

        while not stop_fetching:
            messages = await client.get_messages(group_name, limit=limit, offset_id=offset_id)
            if not messages:
                st.write("No more messages in batch.")
                break

            st.write(f"Fetched {len(messages)} messages in current batch.")
            for message in messages:
                if not message.date:
                    continue
                msg_date = message.date.replace(tzinfo=None).date()
                if end_date and msg_date > end_date:
                    continue
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

        from telethon.tl.types import User
        participants = {}
        # Process main messages
        for message in all_messages:
            if message.sender and isinstance(message.sender, User):
                user = message.sender
            else:
                # For channel posts without a sender, use the group/channel entity.
                user = await client.get_entity(group_name)
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
                    "Access Hash": user.access_hash if hasattr(user, "access_hash") else "Not Available",
                    "First Name": user.first_name if hasattr(user, "first_name") and user.first_name else "No First Name",
                    "Last Name": user.last_name if hasattr(user, "last_name") and user.last_name else "No Last Name",
                    "Username": user.username if hasattr(user, "username") and user.username else "Not Available",
                    "Phone": user.phone if hasattr(user, "phone") and user.phone else "Not Available",
                    "Status": str(user.status) if hasattr(user, "status") and user.status else "Not Available",
                }
        # Process replies (comments)
        for message in all_messages:
            if message.replies and message.replies.replies > 0:
                try:
                    replies = await client.get_messages(group_name, reply_to=message.id, limit=100)
                    for reply in replies:
                        if reply.sender and isinstance(reply.sender, User):
                            r_user = reply.sender
                        else:
                            r_user = await client.get_entity(group_name)
                        if r_user.id not in participants:
                            participants[r_user.id] = {
                                "User ID": r_user.id,
                                "Deleted": getattr(r_user, "deleted", False),
                                "Is Bot": getattr(r_user, "bot", False),
                                "Verified": getattr(r_user, "verified", False),
                                "Restricted": getattr(r_user, "restricted", False),
                                "Scam": getattr(r_user, "scam", False),
                                "Fake": getattr(r_user, "fake", False),
                                "Premium": getattr(r_user, "premium", False),
                                "Access Hash": r_user.access_hash if hasattr(r_user, "access_hash") else "Not Available",
                                "First Name": r_user.first_name if hasattr(r_user, "first_name") and r_user.first_name else "No First Name",
                                "Last Name": r_user.last_name if hasattr(r_user, "last_name") and r_user.last_name else "No Last Name",
                                "Username": r_user.username if hasattr(r_user, "username") and r_user.username else "Not Available",
                                "Phone": r_user.phone if hasattr(r_user, "phone") and r_user.phone else "Not Available",
                                "Status": str(r_user.status) if hasattr(r_user, "status") and r_user.status else "Not Available",
                            }
                except Exception as e:
                    st.write(f"Error fetching replies for message {message.id} in {group_name}: {e}")

        st.write(f"Extracted {len(participants)} unique participants from messages for group '{group_name}'")

        # Merge with API-based participants without overwriting existing entries.
        if not api_df.empty:
            for _, row in api_df.iterrows():
                user_id = row.get("User ID")
                if user_id not in participants:
                    participants[user_id] = row.to_dict()

        fetched_count = len(participants)
        group_counts = {group_name: (reported_count, fetched_count)}
        st.write(f"Total unique participants after merging: {fetched_count}")

        return pd.DataFrame(list(participants.values())), reported_count, fetched_count, group_counts

    except Exception as e:
        st.write(f"Error fetching participants via messages for {group_name}: {e}")
        return pd.DataFrame(), "Not Available", 0, {group_name: ("Not Available", 0)}

async def fetch_participants(client, group_list, method="default", start_date=None, end_date=None):
    all_dfs = []
    total_reported = 0
    total_fetched = 0
    group_counts = {}
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
            df, reported_count, fetched_count, counts = await fetch_participants_via_messages(client, group, start_date, end_date)
            total_fetched += fetched_count
            group_counts[group] = (reported_count, fetched_count)
            if not df.empty:
                all_dfs.append(df)
    if all_dfs:
        unified_df = pd.concat(all_dfs, ignore_index=True)
    else:
        unified_df = pd.DataFrame()
    return unified_df, total_reported, total_fetched, group_counts
