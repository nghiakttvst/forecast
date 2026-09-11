"""
Ứng dụng Dự báo thời tiết WeatherNext — Đài KTTV TP. Cần Thơ
Bao gồm: đăng nhập, thống kê, admin panel.
Chạy: streamlit run app.py
"""

import io
import uuid

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from config import (
    MODELS, VARIABLE_INFO, DEFAULT_VARIABLES, ALERT_THRESHOLDS,
    ALERT_PROB_THRESHOLD, DETERMINISTIC_MODELS,
)
ALL_MODELS = {**MODELS, **DETERMINISTIC_MODELS}

from weather_api import (
    geocode_address, fetch_all_models, build_ensemble_dict,
)
from analysis import (
    compute_ensemble_stats, summarize_temperature,
    summarize_precipitation, classify_weather_phenomenon,
)
from qcvn import (
    evaluate_forecast_qcvn, summarize_qcvn_evaluation, grade_forecast_qcvn,
)
from storage import (
    save_forecast, save_evaluation, load_evaluations,
    save_favorite, load_favorites, delete_favorite,
)
from auth import ensure_admin_exists, login_user, register_user, change_password
from analytics import log_visit
from admin import render_admin_panel


BAR_MAX_MODELS = 3


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Dự báo thời tiết - Đài KTTV TP. Cần Thơ",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS — Ẩn toolbar + cố định sidebar
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    html, body, .stApp, .stMarkdown,
    h1, h2, h3, h4, h5, h6,
    p, span:not([class*="material"]):not([data-testid*="Icon"]),
    label, input, textarea, button, select {
        font-family: 'Be Vietnam Pro', 'Inter', 'Segoe UI',
                     system-ui, -apple-system, sans-serif !important;
    }

    [data-testid="stIconMaterial"],
    [data-testid="stExpanderToggleIcon"],
    span[class*="material-symbols"],
    span[class*="material-icons"],
    .material-symbols-rounded,
    .material-icons, .stIcon {
        font-family: 'Material Symbols Rounded',
                     'Material Icons' !important;
    }

    /* ============================================
       ẨN TOÀN BỘ TOOLBAR STREAMLIT CLOUD
       ============================================ */
    [data-testid="stToolbar"],
    [data-testid="stHeader"],
    [data-testid="stStatusWidget"],
    [data-testid="stAppDeployButton"],
    [data-testid="stManageAppButton"],
    [data-testid="stAppToolbar"],
    [data-testid="stDecoration"],
    .stStatusWidget,
    .stAppDeployButton,
    .stAppToolbar,
    .stDeployButton,
    .manage-app-button,
    #MainMenu,
    header[data-testid="stHeader"],
    button[kind="header"],
    button[kind="headerNoPadding"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
        overflow: hidden !important;
        pointer-events: none !important;
    }

    /* Ẩn iframe badge của Streamlit Cloud */
    iframe[title="streamlit_cloud"],
    iframe[src*="streamlit.io"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* ============================================
       CỐ ĐỊNH SIDEBAR — Không cho thu gọn
       ============================================ */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
    }

    section[data-testid="stSidebar"] {
        transform: translateX(0) !important;
        margin-left: 0 !important;
        min-width: 300px !important;
        width: 300px !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    /* ============================================
       NỀN + LAYOUT CHÍNH
       ============================================ */
    .stApp {
        background: linear-gradient(180deg, #eaf4fb 0%, #f4faff 45%, #fffaf0 100%);
        background-attachment: fixed;
    }

    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }

    /* ============================================
       BANNER
       ============================================ */
    .header-banner {
        position: relative;
        overflow: hidden;
        background: linear-gradient(120deg, #4a9fe0 0%, #5cb8d9 50%, #6dc8c2 100%);
        border-radius: 18px;
        padding: 22px 32px;
        margin-bottom: 18px;
        box-shadow: 0 4px 14px rgba(74, 159, 224, 0.22),
                    0 1px 0 rgba(255, 255, 255, 0.4) inset;
        transition: box-shadow 0.4s ease, transform 0.4s ease;
    }
    .header-banner:hover {
        box-shadow: 0 10px 28px rgba(74, 159, 224, 0.35);
        transform: translateY(-2px);
    }
    .header-banner .deco-icon {
        position: absolute; font-size: 6rem; opacity: 0.10;
        pointer-events: none; line-height: 1;
    }
    .header-banner .deco-icon.left { left: 18px; top: 50%; transform: translateY(-50%); }
    .header-banner .deco-icon.right { right: 18px; top: 50%; transform: translateY(-50%); }
    .header-banner-content { text-align: center; position: relative; z-index: 2; }
    .header-banner-line1 {
        font-size: 1.0rem; font-weight: 600; letter-spacing: 3.2px;
        margin: 0 0 4px 0; text-transform: uppercase;
        color: rgba(255, 255, 255, 0.92);
    }
    .header-banner-line2 {
        font-size: 1.85rem; font-weight: 800; letter-spacing: 1.2px;
        margin: 0; text-transform: uppercase; color: #ffffff;
        text-shadow: 0 2px 4px rgba(0, 60, 100, 0.25);
    }
    .header-banner .inline-icon {
        display: inline-block; font-size: 1.6rem; margin: 0 12px;
        vertical-align: middle; opacity: 0.75;
    }

    h1 { font-size: 1.55rem !important; color: #0e4a7b !important; }
    h2, h3 { color: #145a92 !important; }

    .stButton > button {
        text-align: left; border-radius: 10px;
        transition: all 0.25s ease;
    }
    .stButton > button:hover { transform: translateY(-1px); }

    /* ============================================
       USER INFO HEADER
       ============================================ */
    .user-info-box {
        text-align: right;
        font-size: 0.9rem;
        padding-top: 0.3rem;
        line-height: 1.6;
    }
    .user-info-box strong {
        color: #0e4a7b;
    }
    .fav-count {
        font-size: 0.85rem;
        color: #1976d2;
    }

    /* ============================================
       FOOTER
       ============================================ */
    .footer {
        margin-top: 40px; padding: 20px 24px;
        background: linear-gradient(90deg,
            rgba(74, 159, 224, 0.08) 0%,
            rgba(109, 200, 194, 0.10) 100%);
        border-top: 2px solid rgba(74, 159, 224, 0.28);
        border-radius: 10px 10px 0 0;
        text-align: center; color: #354a5c;
        font-size: 0.92rem; line-height: 1.75;
    }
    .footer strong { color: #0e4a7b; }
    .footer a { color: #1976d2; text-decoration: none; font-weight: 600; }
    .footer-line {
        display: flex; align-items: center; justify-content: center;
        flex-wrap: wrap; gap: 8px; margin: 5px 0;
    }
    .footer-icon { font-size: 1.05rem; opacity: 0.85; }
    .footer-copyright {
        margin-top: 12px; font-size: 0.8rem; color: #6d8a99;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION STATE & AUTH INIT
# ============================================================
ensure_admin_exists()

if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
if "user" not in st.session_state:
    st.session_state["user"] = None
if "pending_run" not in st.session_state:
    st.session_state["pending_run"] = False
if "has_results" not in st.session_state:
    st.session_state["has_results"] = False
if "saved_lat" not in st.session_state:
    st.session_state["saved_lat"] = None
if "saved_lon" not in st.session_state:
    st.session_state["saved_lon"] = None
if "saved_full_name" not in st.session_state:
    st.session_state["saved_full_name"] = None
if "saved_raw_models" not in st.session_state:
    st.session_state["saved_raw_models"] = None
if "saved_days" not in st.session_state:
    st.session_state["saved_days"] = None
if "saved_model_keys" not in st.session_state:
    st.session_state["saved_model_keys"] = None
if "saved_address" not in st.session_state:
    st.session_state["saved_address"] = ""
if "show_admin" not in st.session_state:
    st.session_state["show_admin"] = False


# ============================================================
# LOGIN SCREEN
# ============================================================
def render_login():
    st.markdown("""
<div class="header-banner">
    <span class="deco-icon left">&#x1F4A7;</span>
    <span class="deco-icon right">&#x2601;&#xFE0F;</span>
    <div class="header-banner-content">
        <p class="header-banner-line1">
            <span class="inline-icon">&#x1F4A7;</span>
            Đài Khí tượng Thủy văn Nam Bộ
            <span class="inline-icon">&#x2601;&#xFE0F;</span>
        </p>
        <p class="header-banner-line2">
            Đài Khí tượng Thủy văn Thành phố Cần Thơ
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("### 🔐 Đăng nhập hệ thống")
        tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký"])

        with tab_login:
            with st.form("form_login"):
                username = st.text_input("Tên đăng nhập", key="login_user")
                password = st.text_input("Mật khẩu", type="password", key="login_pwd")
                submit = st.form_submit_button(
                    "🔓 Đăng nhập", use_container_width=True
                )

                if submit:
                    result = login_user(username, password)
                    if result["success"]:
                        st.session_state["user"] = result["user"]
                        log_visit(
                            session_id=st.session_state["session_id"],
                            user_id=result["user"]["id"],
                            username=result["user"]["username"],
                            page="login",
                            action="login",
                        )
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

            st.caption("💡 Tài khoản mặc định: `admin` / `admin123`")

        with tab_register:
            with st.form("form_register"):
                ru = st.text_input("Tên đăng nhập *", key="reg_user")
                rp = st.text_input("Mật khẩu *", type="password", key="reg_pwd")
                rp2 = st.text_input("Nhập lại mật khẩu *", type="password", key="reg_pwd2")
                re = st.text_input("Email", key="reg_email")
                rf = st.text_input("Họ và tên", key="reg_fullname")
                rsub = st.form_submit_button(
                    "✅ Đăng ký", use_container_width=True
                )

                if rsub:
                    if rp != rp2:
                        st.error("Mật khẩu nhập lại không khớp.")
                    else:
                        result = register_user(
                            username=ru, password=rp,
                            email=re, full_name=rf, role="user",
                        )
                        if result["success"]:
                            st.success("Đăng ký thành công! Hãy đăng nhập.")
                        else:
                            st.error(result["message"])


# Kiểm tra đăng nhập
if st.session_state["user"] is None:
    render_login()
    st.stop()

current_user = st.session_state["user"]

# Log visit mỗi lần load app
log_visit(
    session_id=st.session_state["session_id"],
    user_id=current_user["id"],
    username=current_user["username"],
    page="main",
    action="view",
)


# ============================================================
# BANNER CHÍNH
# ============================================================
st.markdown("""
<div class="header-banner">
    <span class="deco-icon left">&#x1F4A7;</span>
    <span class="deco-icon right">&#x2601;&#xFE0F;</span>
    <div class="header-banner-content">
        <p class="header-banner-line1">
            <span class="inline-icon">&#x1F30A;</span>
            Đài Khí tượng Thủy văn Nam Bộ
            <span class="inline-icon">&#x1F30A;</span>
        </p>
        <p class="header-banner-line2">
            Đài Khí tượng Thủy văn Thành phố Cần Thơ
        </p>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# HEADER: TIÊU ĐỀ + USER INFO + ĐĂNG XUẤT
# ============================================================
title_col, user_col = st.columns([3, 2])

with title_col:
    st.title("🌦️ Dự báo thời tiết WeatherNext đa mô hình")

with user_col:
    # Dòng 1: Tên + Vai trò (trái) | Nút Đăng xuất (phải) — CÙNG HÀNG
    info_col, logout_col = st.columns([3, 1])

    with info_col:
        st.markdown(
            f"<div class='user-info-box'>"
            f"👤 <strong>{current_user.get('full_name') or current_user['username']}</strong>"
            f" &nbsp;|&nbsp; Vai trò: <strong>{current_user['role']}</strong>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with logout_col:
        if st.button("🚪 Đăng xuất", key="btn_logout", use_container_width=True):
            st.session_state["user"] = None
            st.session_state["has_results"] = False
            st.session_state["show_admin"] = False
            st.rerun()

    # Dòng 2: Vị trí đã ghim
    favs = load_favorites() if callable(load_favorites) else []
    st.markdown(
        f"<div class='user-info-box fav-count'>"
        f"⭐ Vị trí đã ghim: <strong>{len(favs)}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.divider()


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("📍 Vị trí")
    input_mode = st.radio("Cách nhập:", ["Địa chỉ", "Tọa độ"], key="input_mode")

    address = None
    lat_input, lon_input = None, None

    if input_mode == "Địa chỉ":
        def _on_address_submit():
            st.session_state["pending_run"] = True

        address = st.text_input(
            "Nhập địa chỉ (nhấn Enter):",
            value=st.session_state.get("address_input", "Ninh Kiều, Cần Thơ"),
            key="address_input",
            on_change=_on_address_submit,
        )
    else:
        c1, c2 = st.columns(2)
        with c1:
            lat_input = st.number_input("Vĩ độ:", value=10.0291,
                                        format="%.4f", key="lat_input")
        with c2:
            lon_input = st.number_input("Kinh độ:", value=105.7706,
                                        format="%.4f", key="lon_input")

    st.header("⚙️ Tùy chọn")

    def _fmt_model(k):
        info = ALL_MODELS[k]
        tag = "ensemble" if info.get("ensemble") else "đơn"
        return f"{info['label']}  [{tag} · {info['members']} members]"

    model_keys = st.multiselect(
        "Mô hình dự báo:",
        options=list(ALL_MODELS.keys()),
        default=list(MODELS.keys()),
        format_func=_fmt_model,
        key="model_select",
    )

    days = st.slider("Số ngày dự báo:", 1, 15, 10, key="days_slider")

    st.header("📊 Đánh giá QCVN")
    enable_qcvn = st.checkbox("Bật đánh giá sai số QCVN", value=True,
                              key="enable_qcvn")

    st.divider()
    run_btn = st.button("🚀 Lấy dự báo", type="primary",
                        use_container_width=True, key="run_btn")

    # Admin link
    if current_user["role"] == "admin":
        st.divider()
        st.markdown("### 🛡️ Quản trị")
        if st.button("📊 Mở bảng Admin", use_container_width=True, key="btn_admin"):
            st.session_state["show_admin"] = not st.session_state.get("show_admin", False)
            st.rerun()


# ============================================================
# ADMIN PANEL
# ============================================================
if st.session_state.get("show_admin") and current_user["role"] == "admin":
    render_admin_panel(current_user)
    st.markdown("---")
    if st.button("← Quay lại ứng dụng"):
        st.session_state["show_admin"] = False
        st.rerun()
    st.stop()


# ============================================================
# XỬ LÝ CHÍNH
# ============================================================
trigger_run = run_btn or st.session_state.get("pending_run")

if trigger_run:
    st.session_state["pending_run"] = False
    lat, lon, full_name = None, None, None

    if input_mode == "Địa chỉ":
        with st.spinner("🔍 Đang tra cứu địa chỉ…"):
            geo = geocode_address(address)
        if not geo:
            st.error(f"❌ Không tìm thấy địa chỉ: **{address}**")
            st.stop()
        lat, lon, full_name = geo
    else:
        lat, lon = lat_input, lon_input
        full_name = f"({lat:.4f}, {lon:.4f})"

    if not model_keys:
        st.warning("Vui lòng chọn ít nhất một mô hình.")
        st.stop()

    with st.spinner("☁️ Đang tải dữ liệu từ các mô hình…"):
        raw_models = fetch_all_models(lat, lon, variables=DEFAULT_VARIABLES,
                                      days=days, model_keys=model_keys)

    if not raw_models:
        st.error("❌ Không lấy được dữ liệu.")
        st.stop()

    _test_temp = build_ensemble_dict(raw_models, "temperature_2m")
    _test_precip = build_ensemble_dict(raw_models, "precipitation")
    if not _test_temp and not _test_precip:
        st.error("❌ Không parse được dữ liệu ensemble.")
        st.stop()

    # Lưu vào session
    st.session_state["has_results"] = True
    st.session_state["saved_lat"] = lat
    st.session_state["saved_lon"] = lon
    st.session_state["saved_full_name"] = full_name
    st.session_state["saved_raw_models"] = raw_models
    st.session_state["saved_days"] = days
    st.session_state["saved_model_keys"] = list(model_keys)
    st.session_state["saved_address"] = address if address else ""

    log_visit(
        session_id=st.session_state["session_id"],
        user_id=current_user["id"],
        username=current_user["username"],
        page="forecast",
        action="run",
    )


# ============================================================
# RENDER KẾT QUẢ
# ============================================================
if st.session_state.get("has_results"):
    lat = st.session_state["saved_lat"]
    lon = st.session_state["saved_lon"]
    full_name = st.session_state["saved_full_name"]
    raw_models = st.session_state["saved_raw_models"]
    days = st.session_state["saved_days"]
    model_keys = st.session_state["saved_model_keys"]
    address = st.session_state.get("saved_address", "")

    temp_ensembles = build_ensemble_dict(raw_models, "temperature_2m")
    precip_ensembles = build_ensemble_dict(raw_models, "precipitation")

    st.success(f"📍 {full_name} – Tọa độ: {lat:.4f}, {lon:.4f}")

    fav_col1, fav_col2 = st.columns([1, 4])
    with fav_col1:
        current_favs = load_favorites()
        already = any(f["display"] == full_name for f in current_favs)
        if already:
            st.button("⭐ Đã ghim", disabled=True, key="already_pinned")
        else:
            if st.button("⭐ Ghim vị trí này", key="pin_btn"):
                try:
                    saved = save_favorite(address or full_name, full_name, lat, lon)
                    if saved:
                        st.success(f"⭐ Đã ghim: **{full_name}**")
                    else:
                        st.info("Đã có trong danh sách.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi ghim: {e}")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Biểu đồ dự báo",
        "📊 So sánh mô hình",
        "🕐 Theo giờ",
        "✅ Đánh giá QCVN",
        "💾 Lịch sử",
    ])

    # ============================================================
    # TAB 1: BIỂU ĐỒ
    # ============================================================
    with tab1:
        st.subheader("📈 Dự báo nhiệt độ và mưa")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            subplot_titles=("Nhiệt độ 2m (°C)", "Mưa 1h (mm)"),
                            vertical_spacing=0.12)

        # Nhiệt độ
        for mk, ens_df in temp_ensembles.items():
            stats = compute_ensemble_stats(ens_df)
            if stats.empty:
                continue
            color = ALL_MODELS[mk]["color"]
            label = ALL_MODELS[mk]["label"]
            rgb = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            fig.add_trace(go.Scatter(x=stats.index, y=stats["p90"],
                                     mode="lines", line=dict(width=0),
                                     showlegend=False, hoverinfo="skip"),
                          row=1, col=1)
            fig.add_trace(go.Scatter(x=stats.index, y=stats["p10"],
                                     mode="lines", line=dict(width=0),
                                     fill="tonexty",
                                     fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)",
                                     name=f"{label} (10–90%)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=stats.index, y=stats["mean"],
                                     mode="lines",
                                     line=dict(color=color, width=2),
                                     name=f"{label} (TB)"), row=1, col=1)

        # Mưa
        n_p = len(precip_ensembles)
        use_bars = n_p <= BAR_MAX_MODELS
        for mk, ens_df in precip_ensembles.items():
            stats = compute_ensemble_stats(ens_df)
            if stats.empty:
                continue
            color = ALL_MODELS[mk]["color"]
            if use_bars:
                upper = (stats["p90"] - stats["mean"]).clip(lower=0)
                lower = (stats["mean"] - stats["p10"]).clip(lower=0)
                fig.add_trace(go.Bar(x=stats.index, y=stats["mean"],
                                     marker=dict(color=color),
                                     error_y=dict(type="data", symmetric=False,
                                                  array=upper, arrayminus=lower,
                                                  color=color, thickness=1.2, width=0),
                                     showlegend=False), row=2, col=1)
            else:
                fig.add_trace(go.Scatter(x=stats.index, y=stats["mean"],
                                         mode="lines",
                                         line=dict(color=color, width=2),
                                         showlegend=False), row=2, col=1)

        fig.update_layout(height=720, hovermode="x unified",
                          barmode="group", bargap=0.15, bargroupgap=0.05,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02),
                          margin=dict(l=40, r=20, t=80, b=40))
        st.plotly_chart(fig, use_container_width=True)

        # Tóm tắt
        st.subheader(f"📌 Tóm tắt dự báo {days} ngày tới")
        st.caption(f"Thống kê dựa trên **trung bình ensemble** – "
                   f"khoảng **{days * 24} giờ** dự báo")

        c1, c2, c3, c4 = st.columns(4)
        if temp_ensembles:
            fm = list(temp_ensembles.keys())[0]
            stats = compute_ensemble_stats(temp_ensembles[fm])
            t_max = float(stats["mean"].max())
            time_tmax = stats["mean"].idxmax()
            t_min = float(stats["mean"].min())
            time_tmin = stats["mean"].idxmin()

            c1.metric("🌡️ T cao nhất", f"{t_max:.1f} °C",
                      help=f"Đạt lúc {time_tmax.strftime('%d/%m/%Y %H:%M')}")
            c2.metric("❄️ T thấp nhất", f"{t_min:.1f} °C",
                      help=f"Đạt lúc {time_tmin.strftime('%d/%m/%Y %H:%M')}")

        if precip_ensembles:
            fm = list(precip_ensembles.keys())[0]
            stats = compute_ensemble_stats(precip_ensembles[fm])
            total_rain = float(stats["mean"].sum())
            peak_rain = float(stats["mean"].max())
            time_peak = stats["mean"].idxmax()

            c3.metric("💧 Tổng mưa", f"{total_rain:.1f} mm",
                      help=f"Tổng cộng dồn {days} ngày")
            c4.metric("☔ Đỉnh mưa 1h", f"{peak_rain:.1f} mm",
                      help=f"Đạt lúc {time_peak.strftime('%d/%m/%Y %H:%M')}")

    # ============================================================
    # TAB 2: SO SÁNH MÔ HÌNH (radio Nhiệt độ / Lượng mưa)
    # ============================================================
    with tab2:
        compare_var = st.radio(
            "Chọn biến so sánh:",
            options=["🌡️ Nhiệt độ", "💧 Lượng mưa"],
            horizontal=True,
            key="compare_var_radio",
            label_visibility="collapsed",
        )

        st.divider()

        # -------------------- NHIỆT ĐỘ --------------------
        if compare_var == "🌡️ Nhiệt độ":
            if not temp_ensembles:
                st.info("Không có dữ liệu nhiệt độ từ các mô hình đã chọn.")
            else:
                st.markdown("**Nhiệt độ 2m — Trung bình ensemble các mô hình**")

                fig_cmp = go.Figure()
                for mk, ens_df in temp_ensembles.items():
                    stats = compute_ensemble_stats(ens_df)
                    if stats.empty:
                        continue
                    fig_cmp.add_trace(go.Scatter(
                        x=stats.index, y=stats["mean"],
                        mode="lines",
                        line=dict(color=ALL_MODELS[mk]["color"], width=2),
                        name=ALL_MODELS[mk]["label"],
                        hovertemplate=(
                            f"<b>{ALL_MODELS[mk]['label']}</b><br>"
                            "%{x|%d/%m %H:%M}<br>"
                            "Nhiệt độ: %{y:.1f}°C<extra></extra>"
                        ),
                    ))
                fig_cmp.update_layout(
                    height=480, hovermode="x unified",
                    xaxis_title="Thời gian", yaxis_title="Nhiệt độ (°C)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    margin=dict(l=40, r=20, t=40, b=40),
                )
                st.plotly_chart(fig_cmp, use_container_width=True)

                st.markdown("**Độ bất định (std) trung bình — Nhiệt độ**")
                rows = []
                for mk, ens_df in temp_ensembles.items():
                    stats = compute_ensemble_stats(ens_df)
                    if not stats.empty:
                        rows.append({
                            "Mô hình": ALL_MODELS[mk]["label"],
                            "Std TB (°C)": round(stats["std"].mean(), 3),
                            "Số thành viên": int(stats["n_members"].max()),
                        })
                if rows:
                    st.dataframe(pd.DataFrame(rows),
                                 use_container_width=True, hide_index=True)

        # -------------------- LƯỢNG MƯA --------------------
        else:
            if not precip_ensembles:
                st.info("Không có dữ liệu mưa từ các mô hình đã chọn.")
            else:
                st.markdown("**Mưa 1h — Trung bình ensemble các mô hình**")

                n_models_p = len(precip_ensembles)
                use_bars_cmp = n_models_p <= BAR_MAX_MODELS
                st.caption(
                    f"Dạng hiển thị: **{'cột' if use_bars_cmp else 'đường'}** "
                    f"({n_models_p} mô hình)"
                )

                fig_cmp2 = go.Figure()
                for mk, ens_df in precip_ensembles.items():
                    stats = compute_ensemble_stats(ens_df)
                    if stats.empty:
                        continue

                    if use_bars_cmp:
                        fig_cmp2.add_trace(go.Bar(
                            x=stats.index, y=stats["mean"],
                            marker=dict(color=ALL_MODELS[mk]["color"]),
                            name=ALL_MODELS[mk]["label"],
                            hovertemplate=(
                                f"<b>{ALL_MODELS[mk]['label']}</b><br>"
                                "%{x|%d/%m %H:%M}<br>"
                                "Mưa: %{y:.2f} mm<extra></extra>"
                            ),
                        ))
                    else:
                        fig_cmp2.add_trace(go.Scatter(
                            x=stats.index, y=stats["mean"],
                            mode="lines",
                            line=dict(color=ALL_MODELS[mk]["color"], width=2),
                            name=ALL_MODELS[mk]["label"],
                            hovertemplate=(
                                f"<b>{ALL_MODELS[mk]['label']}</b><br>"
                                "%{x|%d/%m %H:%M}<br>"
                                "Mưa: %{y:.2f} mm<extra></extra>"
                            ),
                        ))

                fig_cmp2.update_layout(
                    height=480, hovermode="x unified",
                    xaxis_title="Thời gian", yaxis_title="Mưa 1h (mm)",
                    barmode="group", bargap=0.15, bargroupgap=0.05,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    margin=dict(l=40, r=20, t=40, b=40),
                )
                st.plotly_chart(fig_cmp2, use_container_width=True)

                st.markdown("**Độ bất định (std) trung bình — Mưa**")
                rows = []
                for mk, ens_df in precip_ensembles.items():
                    stats = compute_ensemble_stats(ens_df)
                    if not stats.empty:
                        rows.append({
                            "Mô hình": ALL_MODELS[mk]["label"],
                            "Std TB (mm)": round(stats["std"].mean(), 3),
                            "Số thành viên": int(stats["n_members"].max()),
                        })
                if rows:
                    st.dataframe(pd.DataFrame(rows),
                                 use_container_width=True, hide_index=True)

    # ============================================================
    # TAB 3: THEO GIỜ
    # ============================================================
    with tab3:
        st.subheader("🕐 Chi tiết dự báo theo giờ")

        if not temp_ensembles and not precip_ensembles:
            st.warning("Không có dữ liệu.")
        else:
            opts = list(temp_ensembles.keys()) or list(precip_ensembles.keys())
            selected = st.radio(
                "Chọn mô hình:", options=opts,
                format_func=lambda k: ALL_MODELS[k]["label"],
                horizontal=True, key="hourly_model_radio",
                label_visibility="collapsed",
            )

            tdf = temp_ensembles.get(selected)
            pdf = precip_ensembles.get(selected)

            tmean = (tdf.mean(axis=1) if tdf is not None and not tdf.empty
                     else pd.Series(dtype=float))
            if pdf is not None and not pdf.empty:
                pmean = pdf.mean(axis=1)
                rprob = (pdf > 0.1).sum(axis=1) / pdf.notna().sum(axis=1)
            else:
                pmean = pd.Series(0.0, index=tmean.index)
                rprob = pd.Series(0.0, index=tmean.index)

            now = pd.Timestamp.now()
            start = now.floor("h") - pd.Timedelta(hours=1)

            df = pd.DataFrame({
                "time": tmean.index, "temp": tmean.values,
                "rain": pmean.values, "rain_prob": rprob.values,
            })
            df = df[df["time"] >= start].sort_values("time").reset_index(drop=True)

            if not df.empty:
                df["phenomenon"] = df.apply(
                    lambda r: classify_weather_phenomenon(
                        r["time"].hour, r["rain"], r["temp"]
                    ), axis=1)
                df["time_str"] = df["time"].dt.strftime("%d/%m %H:%M")

                disp = pd.DataFrame({
                    "Ngày/Giờ": df["time_str"].values,
                    "Hiện tượng": df["phenomenon"].values,
                    "Nhiệt độ (°C)": df["temp"].round(1).values,
                    "Mưa (mm)": df["rain"].round(2).values,
                    "Xác suất mưa (%)": (df["rain_prob"] * 100).round(0).astype(int).values,
                })

                st.caption(
                    f"📊 **{ALL_MODELS[selected]['label']}** — "
                    f"{len(disp)} giờ "
                    f"(từ **{df['time'].min().strftime('%d/%m %H:%M')}** "
                    f"đến **{df['time'].max().strftime('%d/%m %H:%M')}**)"
                )
                st.dataframe(disp, use_container_width=True,
                             hide_index=True, height=600)

                csv_buf = io.StringIO()
                disp.to_csv(csv_buf, index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 Tải bảng CSV",
                    data=csv_buf.getvalue().encode("utf-8-sig"),
                    file_name=f"du_bao_theo_gio_{selected}.csv",
                    mime="text/csv", key="dl_hourly_tab3",
                )

    # ============================================================
    # TAB 4: ĐÁNH GIÁ QCVN
    # ============================================================
    with tab4:
        st.subheader("✅ Đánh giá chất lượng dự báo theo QCVN 84:2024/BTNMT")
        st.caption("Thông tư 46/2024/TT-BTNMT, áp dụng từ 30/6/2025.")

        if not enable_qcvn:
            st.info("Bật tùy chọn 'Đánh giá sai số QCVN' ở sidebar để xem.")
        else:
            st.info("⚠️ **Lưu ý:** Cần file CSV quan trắc với 2 cột `time` và `observed`.")

            uploaded = st.file_uploader("Tải file quan trắc (CSV):",
                                        type=["csv"], key="obs_upload")
            if uploaded:
                try:
                    obs_df = pd.read_csv(uploaded, parse_dates=["time"]).set_index("time")
                    all_eval = []
                    for mk in model_keys:
                        if mk in temp_ensembles:
                            edf = evaluate_forecast_qcvn(
                                temp_ensembles[mk], obs_df,
                                "temperature_2m", "temperature")
                            if not edf.empty:
                                s = summarize_qcvn_evaluation(edf)
                                s["model"] = ALL_MODELS[mk]["label"]
                                s["variable"] = "Nhiệt độ"
                                s["grade"] = grade_forecast_qcvn(s)
                                all_eval.append(s)
                        if mk in precip_ensembles:
                            edf = evaluate_forecast_qcvn(
                                precip_ensembles[mk], obs_df,
                                "precipitation", "precipitation")
                            if not edf.empty:
                                s = summarize_qcvn_evaluation(edf)
                                s["model"] = ALL_MODELS[mk]["label"]
                                s["variable"] = "Mưa"
                                s["grade"] = grade_forecast_qcvn(s)
                                all_eval.append(s)
                    if all_eval:
                        rdf = pd.DataFrame(all_eval)
                        st.dataframe(rdf, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Không đủ dữ liệu.")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    # ============================================================
    # TAB 5: LỊCH SỬ
    # ============================================================
    with tab5:
        st.subheader("💾 Lịch sử đánh giá")
        try:
            hist = load_evaluations(limit=200)
        except Exception as e:
            st.error(f"Lỗi: {e}")
            hist = pd.DataFrame()
        if hist.empty:
            st.info("Chưa có dữ liệu.")
        else:
            st.dataframe(hist, use_container_width=True, hide_index=True)


# ============================================================
# TRANG CHÀO MỪNG
# ============================================================
else:
    st.info("👈 Nhập địa chỉ hoặc tọa độ ở sidebar, chọn mô hình, "
            "rồi nhấn **🚀 Lấy dự báo** để bắt đầu.")
    st.markdown("""
### 🌟 Tính năng chính

| Tính năng | Mô tả |
|---|---|
| 🌍 **Đa mô hình** | 5 ensemble (WeatherNext 2, GFS, ECMWF, ICON, GEM) + 3 mô hình tham chiếu |
| 📊 **Dải bất định** | Percentile 10–90 từ ensemble |
| ✅ **Đánh giá QCVN 84:2024** | ME, MAE, RMSE, Bias, PC theo quy chuẩn |
| 💾 **Lịch sử** | Lưu theo dõi độ chính xác theo thời gian |
| 🗺️ **Định vị 2 cấp** | tỉnh/thành + phường/xã |
| ⭐ **Ghim vị trí** | Lưu và truy cập nhanh các địa điểm yêu thích |

### 📋 Quy trình sử dụng

1. **Nhập vị trí** – gõ địa chỉ rồi nhấn **Enter** (tự động chạy), hoặc nhập tọa độ
2. **Chọn mô hình** – 5 ensemble mặc định, thêm 3 mô hình đơn nếu muốn
3. **Xem kết quả** – biểu đồ, so sánh, cảnh báo, đánh giá QCVN
4. **Ghim vị trí** – nhấn ⭐ để lưu vào góc trên bên phải, click lại để chạy nhanh
""")
# ============================================================
# FOOTER
# ============================================================
st.markdown("""
<div class="footer">
    <div class="footer-line">
        <span class="footer-icon">&#x1F3E0;</span>
        <span><strong>Địa chỉ:</strong>
        Số 45 Đường 3/2, Phường Ninh Kiều, Thành phố Cần Thơ</span>
    </div>
    <div class="footer-line">
        <span class="footer-icon">&#x1F468;&#x200D;&#x1F4BB;</span>
        <span><strong>Phát triển:</strong>
        Power by <strong>Nguyễn Trọng Nghĩa</strong> &#8211; IT</span>
    </div>
    <div class="footer-line">
        <span class="footer-icon">&#x1F4DE;</span>
        <span><strong>Điện thoại:</strong>
        <a href="tel:0974749863">0974 749 863</a></span>
    </div>
    <div class="footer-copyright">
        &#169; 2026 Đài Khí tượng Thủy văn TP. Cần Thơ &#8211;
        Ứng dụng dự báo WeatherNext đa mô hình.
    </div>
</div>
""", unsafe_allow_html=True)