import streamlit as st
import plotly.express as px
import pandas as pd

def render_database_health(status):
    """Render Postgres and Redis metrics"""
    st.subheader("🗄️ Database Health")
    
    col1, col2 = st.columns(2)
    
    # Postgres
    pg_conns = status.get('pg_connections', 0)
    pg_max = status.get('pg_max_connections', 100)
    pg_usage = (pg_conns / pg_max) * 100
    
    col1.write(f"**PostgreSQL Connections** ({pg_conns}/{pg_max})")
    col1.progress(min(pg_usage / 100, 1.0))
    if pg_usage > 80:
        col1.error("High Connection Usage!")
        
    # Redis Latency Chart
    latency_history = status.get('redis_latency_history', [])
    if latency_history:
        df = pd.DataFrame(latency_history, columns=['time', 'latency_ms'])
        fig = px.line(df, x='time', y='latency_ms', title="Redis Command Latency (ms)", markers=True)
        fig.add_hline(y=10, line_dash="dash", line_color="orange", annotation_text="Warning Threshold")
        col2.plotly_chart(fig, use_container_width=True)
    else:
        col2.info("No latency data available yet.")
