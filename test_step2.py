"""Test 2: CSS có animation."""
import streamlit as st

st.set_page_config(page_title="Test", page_icon="🌦️", layout="wide")

st.markdown("""
<style>
    .stApp::before {
        content: "";
        position: fixed;
        top: 0; left: 0; right: 0;
        height: 180px;
        background: radial-gradient(ellipse 120px 60px at 15% 40%,
                    rgba(255,255,255,0.85), transparent 70%);
        pointer-events: none;
        animation: cloudMove 60s linear infinite;
    }
    @keyframes cloudMove {
        0%   { transform: translateX(0); }
        100% { transform: translateX(-120px); }
    }
</style>
""", unsafe_allow_html=True)

st.title("Test Animation OK")