"""Test 3: Đọc SQLite."""
import streamlit as st
from storage import load_favorites

st.title("Test DB")

try:
    with st.spinner("Đang đọc DB…"):
        favs = load_favorites()
    st.success(f"Đọc DB OK: {len(favs)} favorites")
    st.json(favs)
except Exception as e:
    st.error(f"Lỗi DB: {e}")