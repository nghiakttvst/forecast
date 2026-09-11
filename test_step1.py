"""Test 1: Chỉ CSS + Banner."""
import streamlit as st

st.set_page_config(page_title="Test", page_icon="🌦️", layout="wide")

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #e8f4f8 0%, #f0f9ff 100%);
    }
    .block-container {
        padding-top: 0.6rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background: linear-gradient(135deg, #1565c0, #26a69a);
            color: white; padding: 18px; border-radius: 12px;
            text-align: center;">
    <h2>ĐÀI KHÍ TƯỢNG THỦY VĂN TP. CẦN THƠ</h2>
</div>
""", unsafe_allow_html=True)

st.title("Test CSS + Banner OK")