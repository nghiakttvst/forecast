"""Tự động sửa hàm render_home() trong app.py."""

from pathlib import Path
import re

APP = Path(__file__).parent / "app.py"
content = APP.read_text(encoding="utf-8-sig")

NEW_FUNC = '''def render_home():
    # Banner
    st.markdown("""
<div class="header-banner">
    <div class="h1">🌊 ĐÀI KHÍ TƯỢNG THỦY VĂN NAM BỘ 🌦️</div>
    <div class="h2">ĐÀI KHÍ TƯỢNG THỦY VĂN THÀNH PHỐ CẦN THƠ</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="large")

    # ---------- KHÍ TƯỢNG ----------
    with c1:
        with st.container(key="zone_kttv"):
            st.markdown("""
<div class="zone-card zone-kttv">
    <div class="zone-icon">🌦️</div>
    <div class="zone-title">Dự báo Khí tượng</div>
    <div class="zone-desc">
        Dự báo số trị đa mô hình · Bản tin hàng ngày ·
        Cảnh báo mưa dông · Mưa lớn
    </div>
</div>
""", unsafe_allow_html=True)
            if st.button("Khí tượng", key="btn_go_kttv", width='stretch'):
                navigate("kttv", "forecast")

    # ---------- THỦY VĂN ----------
    with c2:
        with st.container(key="zone_thuyvan"):
            st.markdown("""
<div class="zone-card zone-thuyvan">
    <div class="zone-icon">🌊</div>
    <div class="zone-title">Dự báo Thủy văn</div>
    <div class="zone-desc">
        Mực nước sông · Cảnh báo ngập lụt ·
        Triều cường · Dự báo nguồn nước
    </div>
</div>
""", unsafe_allow_html=True)
            if st.button("Thủy văn", key="btn_go_tv", width='stretch'):
                navigate("thuyvan")

    # ---------- MẠNG LƯỚI ----------
    with c3:
        with st.container(key="zone_mangluoi"):
            st.markdown("""
<div class="zone-card zone-mangluoi">
    <div class="zone-icon">🗺️</div>
    <div class="zone-title">Mạng lưới & Dữ liệu</div>
    <div class="zone-desc">
        Bản đồ trạm KTTV · Dữ liệu quan trắc ·
        Lịch sử khí tượng thủy văn
    </div>
</div>
""", unsafe_allow_html=True)
            if st.button("Mạng lưới", key="btn_go_ml", width='stretch'):
                navigate("network")
'''

# Tìm hàm render_home cũ và thay thế
# Pattern: từ "def render_home():" đến "def render_kttv():" hoặc "def render_" tiếp theo
pattern = r'def render_home\(\):.*?(?=^def render_)'
replacement = NEW_FUNC + '\n\n'

if re.search(pattern, content, flags=re.DOTALL | re.MULTILINE):
    content = re.sub(pattern, replacement, content, flags=re.DOTALL | re.MULTILINE)
    APP.write_text(content, encoding="utf-8")
    print("✅ Đã sửa hàm render_home() thành công")
else:
    print("⚠️ Không tìm thấy hàm render_home()")