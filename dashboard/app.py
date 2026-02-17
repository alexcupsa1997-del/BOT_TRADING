import streamlit as st
import time
from services import data_service
from views import system_health, database_health, trading_status
import config

# Page Config
st.set_page_config(
    page_title="GOLIATH Operations Center",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Service
ds = data_service.DataService()

def main():
    st.title("🤖 GOLIATH TRADING BOT - OPS CENTER")
    
    # Sidebar
    st.sidebar.title("Controls")
    refresh_rate = st.sidebar.slider("Refresh Rate (s)", 1, 10, config.REFRESH_RATE)
    safety_switch = st.sidebar.toggle("MASTER SWITCH (Read-Only)", value=True)
    
    if not safety_switch:
        st.sidebar.warning("⚠️ WRITE ACCESS ENABLED (Not Implemented)")

    # Main Data Fetch
    status = ds.get_system_status()
    
    if not status:
        st.error("🚨 SYSTEM OFFLINE: Unable to fetch status from Redis.")
        st.info("Ensure the bot (or mock script) is running and Redis is up.")
        
        # Retry Button
        if st.button("Retry Connection"):
            st.rerun()
        return

    # Render Views
    
    # 1. System Health
    system_health.render_system_health(status)
    
    st.divider()

    # 2. Trading Status
    orders = ds.get_active_orders()
    trading_status.render_trading_status(status, orders)
    
    st.divider()

    # 3. Database Health
    database_health.render_database_health(status)
    
    st.divider()
    
    # 4. Critical Logs
    st.subheader("📜 Critical Logs")
    logs = ds.get_logs()
    for log in logs:
        st.code(log, language="text")

    # Auto-Refresh Logic
    time.sleep(refresh_rate)
    st.rerun()

if __name__ == "__main__":
    main()
