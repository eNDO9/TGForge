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
st.title("TGForge")

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
    
    # --- Refresh Button (Clears Display But Keeps Data) ---
    if st.button("🔄 Refresh"):
        for key in ["channel_data", "forwards_data", "messages_data", "top_hashtags",
                    "top_urls", "top_domains", "forward_counts", "daily_volume",
                    "weekly_volume", "monthly_volume"]:
            if key in st.session_state:
                del st.session_state[key]  # Remove only displayed data, not authentication
        st.rerun()  # ✅ Force Streamlit to refresh the UI

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
            st.data_editor(
                df_top_views,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Description": st.column_config.TextColumn(
                        width="large",  # Expands column width
                        max_chars=None,  # Removes character limit (default cuts off text)
                        help="Full text shown when hovered."
                    )
                }
            )
        else:            
            st.write("### Messages Data Preview (First 25 Rows)")
            st.data_editor(
                df_messages.head(25),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Description": st.column_config.TextColumn(
                        width="large",  # Expands column width
                        max_chars=None,  # Removes character limit (default cuts off text)
                        help="Full text shown when hovered."
                    )
                }
            )
            
    # ✅ Show first 25 rows of forward counts in a table
    if "forward_counts" in st.session_state and st.session_state.forward_counts is not None:
        df_counts = pd.DataFrame(st.session_state.forward_counts)
        st.write("### Top Forwarded Channels")
        st.data_editor(df_counts.head(25))

    # ✅ Show top shared domains
    if "top_domains" in st.session_state:
        st.write("### Top Domains")
        st.data_editor(pd.DataFrame(st.session_state.top_domains).head(25))

    # ✅ Show first 25 rows of top URLs
    if "top_urls" in st.session_state and st.session_state.top_urls is not None:
        df_urls = pd.DataFrame(st.session_state.top_urls)
        st.write("### Top URLs")
        st.data_editor(df_urls.head(25))
        
    # ✅ Show first 25 rows of top hashtags
    if "top_hashtags" in st.session_state and st.session_state.top_hashtags is not None:
        df_hashtags = pd.DataFrame(st.session_state.top_hashtags)
        st.write("### Top Hashtags")
        st.data_editor(df_hashtags.head(25))
        

    # ✅ Define color palette
    COLOR_PALETTE = ["#C7074D", "#B4B2B1", "#4C4193", "#0068B2", "#E76863", "#5C6771"]

    def plot_vot_chart(df, index_col, title, freq="D"):
        """Plots a line chart, ensuring missing dates are filled with 0s and colors adjust dynamically."""
        st.subheader(title)

        if df.empty:
            st.warning("No data available.")
            return

        df = df.set_index(index_col)

        # ✅ Generate a full date range (Daily, Weekly, Monthly)
        full_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq)
        df = df.reindex(full_range, fill_value=0)  # ✅ Fill missing dates with 0s
        df.index.name = index_col  # ✅ Rename index to match expected format
        df.reset_index(inplace=True)

        # ✅ Allow user to toggle between showing individual lines vs aggregated total
        show_total = st.toggle(f"Show aggregated total for {title}", value=False)

        if show_total:
            # ✅ Sum all columns to show aggregated total
            df["Total"] = df.iloc[:, 1:].sum(axis=1)  # Sum all channels
            df = df[[index_col, "Total"]]
            colors = ["#C7074D"]  # ✅ Use only one color for total view
        else:
            # ✅ Ensure the number of colors matches the number of columns
            num_lines = df.shape[1] - 1  # Excluding the index column
            colors = COLOR_PALETTE[:num_lines] if num_lines <= len(COLOR_PALETTE) else None  # Avoid mismatch

        # ✅ Plot the chart with dynamically assigned colors
        st.line_chart(df.set_index(index_col), color=colors)

    # ✅ Show Volume Over Time Charts with Missing Dates Filled
    if "daily_volume" in st.session_state:
        df_daily = pd.DataFrame(st.session_state.daily_volume)
        plot_vot_chart(df_daily, "Date", "📊 Daily Message Volume", freq="D")

    if "weekly_volume" in st.session_state:
        df_weekly = pd.DataFrame(st.session_state.weekly_volume)
        st.text("DEBUG: st.session_state.weekly_volume")
        st.text(df_weekly)
        plot_vot_chart(df_weekly, "Week", "📆 Weekly Message Volume", freq="W")

    if "monthly_volume" in st.session_state:
        df_monthly = pd.DataFrame(st.session_state.monthly_volume)
        plot_vot_chart(df_monthly, "Year-Month", "📅 Monthly Message Volume", freq="MS")
     
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
            df_daily_volume.to_excel(writer, sheet_name="Daily Volume", index=False)
            df_weekly_volume.to_excel(writer, sheet_name="Weekly Volume", index=False)
            df_monthly_volume.to_excel(writer, sheet_name="Monthly Volume", index=False)
        output_xlsx.seek(0)

        st.download_button(
            "📥 Download Messages Data (Excel)",
            data=output_xlsx.getvalue(),
            file_name="messages_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )