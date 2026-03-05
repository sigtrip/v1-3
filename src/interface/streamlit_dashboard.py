"""
streamlit_dashboard.py — легкая админка Аргоса поверх FastAPI API.
Запуск:
  streamlit run src/interface/streamlit_dashboard.py
"""

import os

import requests
import streamlit as st

API = os.getenv("ARGOS_DASHBOARD_API", "http://localhost:8080").rstrip("/")

st.set_page_config(page_title="Argos Streamlit Dashboard", layout="wide")
st.title("👁️ Argos Streamlit Dashboard")
st.caption(f"API: {API}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Метрики")
    try:
        status = requests.get(f"{API}/api/status", timeout=5).json()
        st.metric("CPU", f"{status.get('cpu', 0):.1f}%")
        st.metric("RAM", f"{status.get('ram', 0):.1f}%")
        st.metric("Disk", f"{status.get('disk', 0):.1f}%")
        st.write(
            {
                "state": status.get("state"),
                "uptime": status.get("uptime"),
                "p2p_nodes": status.get("p2p_nodes"),
                "voice_on": status.get("voice_on"),
            }
        )
    except Exception as e:
        st.error(f"Не удалось получить статус: {e}")

with col2:
    st.subheader("Команда")
    cmd = st.text_input("Введите директиву")
    if st.button("Выполнить") and cmd.strip():
        try:
            resp = requests.post(f"{API}/api/cmd", json={"cmd": cmd}, timeout=20).json()
            st.code(resp.get("answer", str(resp)))
        except Exception as e:
            st.error(f"Ошибка отправки команды: {e}")

st.subheader("Логи")
try:
    logs = requests.get(f"{API}/api/log", timeout=5).json().get("lines", "")
    st.text_area("Последние строки", logs, height=300)
except Exception as e:
    st.error(f"Не удалось получить логи: {e}")


# README-совместимые обёртки
def run_streamlit():
    """Точка входа (для импорта); реальный запуск: streamlit run <этот файл>."""
    pass


StreamlitDashboard = type("StreamlitDashboard", (), {"run": staticmethod(run_streamlit)})
