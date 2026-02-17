import streamlit as st
import plotly.graph_objects as go

def render_system_health(status):
    """Render CPU, RAM, and Disk metrics"""
    st.subheader("🖥️ Infrastructure Health")
    
    col1, col2, col3 = st.columns(3)
    
    # CPU Gauge
    cpu = status.get('cpu_percent', 0)
    fig_cpu = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = cpu,
        title = {'text': "CPU Usage"},
        gauge = {'axis': {'range': [None, 100]}, 'bar': {'color': "darkblue" if cpu < 80 else "red"}}
    ))
    fig_cpu.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
    col1.plotly_chart(fig_cpu, use_container_width=True)
    
    # RAM Gauge
    ram = status.get('ram_percent', 0)
    fig_ram = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = ram,
        title = {'text': "RAM Usage"},
        gauge = {'axis': {'range': [None, 100]}, 'bar': {'color': "darkgreen" if ram < 80 else "red"}}
    ))
    fig_ram.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
    col2.plotly_chart(fig_ram, use_container_width=True)

    # Disk / Network (Simple Metric)
    disk = status.get('disk_usage', 0)
    col3.metric("Disk Usage", f"{disk}%")
    col3.metric("Uptime", f"{status.get('uptime_seconds', 0) // 3600} hours")
