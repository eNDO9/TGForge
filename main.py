import streamlit as st
import asyncio
import pandas as pd
import io
from telegram_client import create_client, delete_session_file
from fetch_channel import fetch_channel_data
from fetch_forwards import fetch_forwards
from fetch_messages import fetch_messages
from telethon.errors import PhoneNumberInvalidError, PhoneCodeInvalidError, SessionPasswordNeededError

# --- Ensure an Event Loop Exists ---
import sys

if "event_loop" not in st.session_state:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # Windows fix
    st.session_state.event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.event_loop)
else:
    asyncio.set_event_loop(st.session_state.event_loop)  # ✅ Keep the same event loop

# --- Streamlit UI ---
st.title("TGForge - MADE BY NATHAN")

# Ensure session state variables are initialized
if "auth_step" not in st.session_state:
    st.session_state.auth_step = 1
    st.session_state.authenticated = False
    st.session_state.client = None

# --- Step 1: Enter API Credentials ---
if st.session_state.auth_step == 1:
    st.subheader("Step 1: Enter Telegram API Credentials")

    api_id = st.text_input("API ID", value=st.session_state.get("api_id", ""))
    api_hash = st.text_input("API Hash", value=st.session_state.get("api_hash", ""))
    phone_number = st.text_input("Phone Number (e.g., +123456789)")

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("Next"):
            if api_id and api_hash and phone_number:
                try:
                    st.session_state.api_id = api_id
                    st.session_state.api_hash = api_hash
                    st.session_state.phone_number = phone_number

                    if st.session_state.client is None:
                        st.session_state.client = create_client(int(api_id), api_hash)

                    async def connect_and_send_code():
                        await st.session_state.client.connect()
                        if not await st.session_state.client.is_user_authorized():
                            await st.session_state.client.send_code_request(phone_number)

                    st.session_state.event_loop.run_until_complete(connect_and_send_code())
                    st.session_state.auth_step = 2  

                except PhoneNumberInvalidError:
                    st.error("Invalid phone number. Please check and try again.")
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        if st.button("Reset Session"):
            delete_session_file()

# --- Step 2: Enter Verification Code ---
elif st.session_state.auth_step == 2:
    st.subheader("Step 2: Enter Verification Code")
    verification_code = st.text_input("Enter the verification code")

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("Authenticate"):
            try:
                async def sign_in():
                    await st.session_state.client.sign_in(st.session_state.phone_number, verification_code)

                st.session_state.event_loop.run_until_complete(sign_in())  # ✅ Ensure same event loop is used
                st.session_state.auth_step = 3  
                st.session_state.authenticated = True
                st.success("Authentication successful!")

            except PhoneCodeInvalidError:
                st.error("Invalid verification code. Please try again.")
            except SessionPasswordNeededError:
                st.error("Two-step verification is enabled. This script does not handle passwords.")
            except Exception as e:
                st.error(f"Error: {e}")

    with col2:
        if st.button("Reset Session"):
            delete_session_file()

# --- Step 3: Fetch Channel Info UI ---
elif st.session_state.auth_step == 3 and st.session_state.authenticated:
    st.subheader("Fetch Telegram Channel Data")

    # User Input
    channel_input = st.text_area("Enter Telegram channel usernames (comma-separated):", "unity_of_fields")
    
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Fetch Channel Info"):
            st.session_state.channel_data = st.session_state.event_loop.run_until_complete(
                fetch_channel_data(st.session_state.client, channel_input.split(","))
            )

    with col2:
        if st.button("Fetch Forwards"):
            st.session_state.forwards_data, st.session_state.forward_counts = st.session_state.event_loop.run_until_complete(
                fetch_forwards(st.session_state.client, channel_input.split(","))
            )

    with col3:
        if st.button("Fetch Messages"):
            st.session_state.messages_data, st.session_state.top_hashtags, st.session_state.top_urls, \
            st.session_state.top_domains, st.session_state.forward_counts, \
            st.session_state.daily_volume, st.session_state.weekly_volume, st.session_state.monthly_volume = \
            st.session_state.event_loop.run_until_complete(fetch_messages(st.session_state.client, channel_input.split(",")))

    # ✅ Restore original printing format for channel info
    if "channel_data" in st.session_state and st.session_state.channel_data:
        for info in st.session_state.channel_data:
            if "Error" in info:
                st.error(info["Error"])
            else:
                st.markdown("### 📌 Channel Information")
                for key, value in info.items():
                    st.write(f"**{key}:** {value}")
                st.markdown("---")

    # ✅ Show first 25 rows of forwards data in a table
    if "forwards_data" in st.session_state and st.session_state.forwards_data is not None:
        df_fwd = pd.DataFrame(st.session_state.forwards_data)
        st.write("### Forwarded Messages Preview (First 25 Rows)")
        st.dataframe(df_fwd.head(25))

        # ✅ Fix CSV Download (use BytesIO)
        csv_output = io.BytesIO()
        df_fwd.to_csv(csv_output, index=False)
        csv_output.seek(0)
        st.download_button(
            "📥 Download Forwards (CSV)",
            data=csv_output.getvalue(),
            file_name="forwards.csv",
            mime="text/csv",
        )

    # ✅ Show top 25 most viewed posts
    if "messages_data" in st.session_state:
        df_messages = pd.DataFrame(st.session_state.messages_data)

        if "Views" in df_messages.columns:
            df_top_views = df_messages.sort_values(by="Views", ascending=False).head(25)
            st.write("### Top 25 Most Viewed Posts")
            st.dataframe(df_top_views)
        else:
            st.write("### Messages Data Preview (First 25 Rows)")
            st.dataframe(df_messages.head(25))
            
    # ✅ Show first 25 rows of forward counts in a table
    if "forward_counts" in st.session_state and st.session_state.forward_counts is not None:
        df_counts = pd.DataFrame(st.session_state.forward_counts)
        st.write("### Top Forwarded Channels")
        st.dataframe(df_counts.head(25))

        # ✅ Fix XLSX Download (use BytesIO)
        output_counts = io.BytesIO()
        with pd.ExcelWriter(output_counts, engine="openpyxl") as writer:
            df_counts.to_excel(writer, index=False)
        output_counts.seek(0)
        st.download_button(
            "📥 Download Forward Counts (Excel)",
            data=output_counts.getvalue(),
            file_name="forward_counts.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ✅ Show top shared domains
    if "top_domains" in st.session_state:
        st.write("### Top Domains")
        st.dataframe(pd.DataFrame(st.session_state.top_domains).head(25))

    # ✅ Show first 25 rows of top hashtags
    if "top_hashtags" in st.session_state and st.session_state.top_hashtags is not None:
        df_hashtags = pd.DataFrame(st.session_state.top_hashtags)
        st.write("### Top Hashtags")
        st.dataframe(df_hashtags.head(25))

    # ✅ Show first 25 rows of top URLs
    if "top_urls" in st.session_state and st.session_state.top_urls is not None:
        df_urls = pd.DataFrame(st.session_state.top_urls)
        st.write("### Top URLs")
        st.dataframe(df_urls.head(25))
        
    # Function to ensure a continuous date range with 0s
    def format_vo_time_series(df):
        df = df.copy()
        df.index = pd.to_datetime(df.index)  # Ensure index is datetime

        # ✅ Create full date range from the first to last message date
        full_date_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq='D')
        df = df.reindex(full_date_range, fill_value=0).reset_index()
        df.columns = ['Date'] + list(df.columns[1:])  # Rename first column to 'Date'

        # ✅ Format as "Jan '24"
        df['Date Label'] = df['Date'].dt.strftime("%b '%y")
        return df

    # Function to ensure continuous dates **without dropping to 0**
    def format_vo_time_series(df):
        df = df.copy()
        df.index = pd.to_datetime(df.index)  # Ensure datetime index

        # ✅ Create full date range from first to last message date
        full_date_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq="D")

        # ✅ Fill missing dates **without forcing zeroes**
        df = df.reindex(full_date_range).fillna(method="ffill").fillna(0).reset_index()
        df.columns = ["Date"] + list(df.columns[1:])  # Rename first column to "Date"

        # ✅ Format labels as "Jan '24"
        df["Date Label"] = df["Date"].dt.strftime("%b '%y")
        return df

    # ✅ Display Daily Volume with Streamlit's Line Chart
    if "daily_volume" in st.session_state:
        st.subheader("📊 Daily Message Volume")
        df_daily = format_vo_time_series(pd.DataFrame(st.session_state.daily_volume))
        st.line_chart(df_daily.set_index("Date")["Total"])  # ✅ FIX: No artificial zeroes

    # ✅ Display Weekly Volume
    if "weekly_volume" in st.session_state:
        st.subheader("📊 Weekly Message Volume")
        df_weekly = format_vo_time_series(pd.DataFrame(st.session_state.weekly_volume))
        st.line_chart(df_weekly.set_index("Date")["Total"])

    # ✅ Display Monthly Volume
    if "monthly_volume" in st.session_state:
        st.subheader("📊 Monthly Message Volume")
        df_monthly = format_vo_time_series(pd.DataFrame(st.session_state.monthly_volume))
        st.line_chart(df_monthly.set_index("Date")["Total"])
    # CSV Download
    if "messages_data" in st.session_state and st.session_state.messages_data is not None:
        df_messages = pd.DataFrame(st.session_state.messages_data)

        csv_output = io.BytesIO()
        df_messages.to_csv(csv_output, index=False)
        csv_output.seek(0)
        st.download_button(
            "📥 Download Messages (CSV)",
            data=csv_output.getvalue(),
            file_name="messages.csv",
            mime="text/csv",
        )

    # ✅ Fix XLSX Download
    if (
        "messages_data" in st.session_state and "top_hashtags" in st.session_state
        and "top_urls" in st.session_state and "top_domains" in st.session_state
        and "forward_counts" in st.session_state and "daily_volume" in st.session_state
        and "weekly_volume" in st.session_state and "monthly_volume" in st.session_state
    ):
        df_messages = pd.DataFrame(st.session_state.messages_data).nlargest(50, "Views")  # ✅ Top 50 most viewed messages
        df_top_domains = pd.DataFrame(st.session_state.top_domains).head(25)  # ✅ Top 25 most shared domains
        df_top_urls = pd.DataFrame(st.session_state.top_urls).head(25)  # ✅ Top 25 most shared URLs
        df_forward_counts = pd.DataFrame(st.session_state.forward_counts)  # ✅ Forward counts
        df_top_hashtags = pd.DataFrame(st.session_state.top_hashtags).head(25)  # ✅ Top 25 hashtags
        df_daily_volume = pd.DataFrame(st.session_state.daily_volume)  # ✅ Daily volume
        df_weekly_volume = pd.DataFrame(st.session_state.weekly_volume)  # ✅ Weekly volume
        df_monthly_volume = pd.DataFrame(st.session_state.monthly_volume)  # ✅ Monthly volume

        output_xlsx = io.BytesIO()
        with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
            df_messages.to_excel(writer, sheet_name="Top 50 Viewed Posts", index=False)
            df_top_domains.to_excel(writer, sheet_name="Top 25 Shared Domains", index=False)
            df_top_urls.to_excel(writer, sheet_name="Top 25 Shared URLs", index=False)
            df_forward_counts.to_excel(writer, sheet_name="Forward Counts", index=False)
            df_top_hashtags.to_excel(writer, sheet_name="Top 25 Hashtags", index=False)
            df_daily_volume.to_excel(writer, sheet_name="Daily Volume", index=True)
            df_weekly_volume.to_excel(writer, sheet_name="Weekly Volume", index=True)
            df_monthly_volume.to_excel(writer, sheet_name="Monthly Volume", index=True)
        output_xlsx.seek(0)

        st.download_button(
            "📥 Download Messages Data (Excel)",
            data=output_xlsx.getvalue(),
            file_name="messages_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )