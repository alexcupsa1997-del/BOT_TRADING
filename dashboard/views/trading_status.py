import streamlit as st
import pandas as pd

def render_trading_status(status, active_orders):
    """Render Trading Engine status and Orders"""
    st.subheader("📈 Trading Operations")
    
    # KPI Row
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    pnl = status.get('daily_pnl', 0.0)
    pnl_pct = status.get('pnl_percent', 0.0)
    
    kpi1.metric("Daily PnL", f"${pnl:.2f}", delta=f"{pnl_pct:.2f}%")
    kpi2.metric("Open Positions", status.get('open_positions', 0))
    kpi3.metric("Trades Today", status.get('trades_count', 0))
    kpi4.metric("Strategy", status.get('active_strategy', 'Unknown'))
    
    # Active Orders Table
    st.write("### Active Orders")
    if active_orders:
        df = pd.DataFrame(active_orders)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No active orders.")
