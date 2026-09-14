"""
Ứng dụng Dự báo thời tiết WeatherNext — Đài KTTV TP. Cần Thơ
Public — không cần đăng nhập. Admin bảo vệ bằng password.
"""

import io
import uuid
import time as _time
from datetime import datetime, timezone, timedelta

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (
    MODELS, VARIABLE_INFO, DEFAULT_VARIABLES, ALERT_THRESHOLDS,
    ALERT_PROB_THRESHOLD, DETERMINISTIC_MODELS,
)
ALL_MODELS = {**MODELS, **DETERMINISTIC_MODELS}

from weather_api import (
    geocode_address, fetch_all_models, build_ensemble_dict,
    clear_api_cache, get_model_age_hours, get_model_run_time,
    get_next_run_time, is_data_stale, format_run_time,
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
from analytics import log_visit, get_stats
from admin import render_admin_panel


BAR_MAX_MODELS = 3
AUTO_REFRESH_MIN = 60
ADMIN_PASSWORD = "kttv2026"


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
# CSS
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    html, body, .stApp, .stMarkdown, h1, h2, h3, h4, h5, h6,
    p, span:not([class*="material"]):not([data-testid*="Icon"]),
    label, input, textarea, button, select {
        font-family: 'Be Vietnam Pro', 'Inter', 'Segoe UI',
                     system-ui, -apple-system, sans-serif !important;
    }
    [data-testid="stIconMaterial"],
    [data-testid="stExpanderToggleIcon"],
    span[class*="material-symbols"], .stIcon {
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }

    [data-testid="stToolbar"], [data-testid="stStatusWidget"],
    [data-testid="stAppDeployButton"], [data-testid="stManageAppButton"],
    [data-testid="stAppToolbar"], [data-testid="stDecoration"],
    [class*="viewerBadge"], [class*="ManageApp"],
    header[data-testid="stHeader"], button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        pointer-events: none !important;
    }
    iframe[src*="streamlit.io"] { display: none !important; }

    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
    }
    section[data-testid="stSidebar"] {
        transform: translateX(0) !important;
        margin-left: 0 !important;
        min-width: 300px !important;
        width: 300px !important;
        visibility: visible !important;
    }

    .stApp {
        background: linear-gradient(180deg, #eaf4fb 0%, #f4faff 45%, #fffaf0 100%);
        background-attachment: fixed;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 5rem !important;
    }

    .header-banner {
        position: relative; overflow: hidden;
        background: linear-gradient(120deg, #4a9fe0 0%, #5cb8d9 50%, #6dc8c2 100%);
        border-radius: 18px; padding: 22px 32px; margin-bottom: 18px;
        box-shadow: 0 4px 14px rgba(74, 159, 224, 0.22);
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
        border-radius: 10px;
        transition: all 0.25s ease;
    }
    .stButton > button:hover { transform: translateY(-1px); }

    .pin-header {
        font-size: 0.9rem; font-weight: 700;
        color: #0e4a7b; margin: 0.5rem 0 0.4rem 0;
        padding-left: 4px;
    }
    .pin-empty {
        font-size: 0.85rem; color: #6d8a99;
        font-style: italic; padding-left: 4px;
    }

    /* Widget thống kê */
    .visit-widget {
        position: fixed;
        bottom: 12px;
        right: 12px;
        background: linear-gradient(135deg, #4a9fe0 0%, #6dc8c2 100%);
        color: #ffffff;
        padding: 8px 16px;
        border-radius: 22px;
        font-family: 'Be Vietnam Pro', 'Inter', sans-serif;
        font-size: 0.78rem;
        font-weight: 500;
        box-shadow: 0 4px 14px rgba(74, 159, 224, 0.35);
        z-index: 9998;
        display: flex;
        align-items: center;
        gap: 10px;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    .visit-widget:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(74, 159, 224, 0.45);
    }
    .visit-widget .vw-item { display: inline-flex; align-items: center; gap: 4px; }
    .visit-widget .vw-num { font-weight: 800; font-size: 0.85rem; }
    .visit-widget .vw-sep { opacity: 0.5; }
    .visit-widget .vw-dot {
        width: 6px; height: 6px; border-radius: 50%;
        background: #7dff8a; box-shadow: 0 0 8px #7dff8a;
        display: inline-block; margin-right: 2px;
    }

    @media (max-width: 768px) {
        .visit-widget {
            font-size: 0.7rem;
            padding: 6px 10px;
            bottom: 8px;
            right: 8px;
        }
    }

    .footer {
        margin-top: 40px; padding: 20px 24px;
        background: linear-gradient(90deg, rgba(74,159,224,0.08), rgba(109,200,194,0.10));
        border-top: 2px solid rgba(74, 159, 224, 0.28);
        border-radius: 10px 10px 0 0;
        text-align: center; color: #354a5c; font-size: 0.92rem; line-height: 1.75;
    }
    .footer strong { color: #0e4a7b; }
    .footer a { color: #1976d2; text-decoration: none; font-weight: 600; }
    .footer-line {
        display: flex; align-items: center; justify-content: center;
        flex-wrap: wrap; gap: 8px; margin: 5px 0;
    }
    .footer-icon { font-size: 1.05rem; opacity: 0.85; }
    .footer-copyright { margin-top: 12px; font-size: 0.8rem; color: #6d8a99; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# JS ẩn Manage app
# ============================================================
components.html("""
<script>
(function() {
    const S = ['[data-testid="stStatusWidget"]',
               '[data-testid="stAppDeployButton"]',
               '[data-testid="stManageAppButton"]',
               '[data-testid="stToolbar"]',
               '[data-testid="stHeader"]',
               '[class*="viewerBadge"]', '[class*="ManageApp"]'];
    function kill() {
        S.forEach(s => document.querySelectorAll(s).forEach(el => el.remove()));
        document.querySelectorAll('iframe').forEach(f => {
            const r = f.getBoundingClientRect();
            if (r.bottom > window.innerHeight - 100 && r.right > window.innerWidth - 300)
                f.remove();
        });
    }
    kill();
    [500, 1500, 3000, 5000].forEach(t => setTimeout(kill, t));
    new MutationObserver(kill).observe(document.body, {childList:true, subtree:true});
})();
</script>
""", height=0, width=0)


# ============================================================
# SESSION STATE
# ============================================================
_defaults = {
    "session_id": str(uuid.uuid4()),
    "pending_run": False,
    "has_results": False,
    "saved_lat": None, "saved_lon": None, "saved_full_name": None,
    "saved_raw_models": None, "saved_days": None,
    "saved_model_keys": None, "saved_address": "",
    "show_admin": False,
    "admin_authed": False,
    "visit_logged": False,
    "last_fetch_ts": None,
    "last_fetch_str": None,
    "force_refresh": False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ============================================================
# LOG VISIT (1 lần / session)
# ============================================================
if not st.session_state.get("visit_logged"):
    try:
        log_visit(
            session_id=st.session_state["session_id"],
            user_id=None,
            username="guest",
            page="main",
            action="view",
        )
    except Exception as e:
        print(f"[VISIT] Lỗi: {e}")
    st.session_state["visit_logged"] = True


# ============================================================
# WIDGET THỐNG KÊ GÓC DƯỚI
# ============================================================
try:
    _stats = get_stats()
    st.markdown(f"""
<div class="visit-widget">
    <span class="vw-item">
        <span class="vw-dot"></span>
        <span class="vw-num">{_stats['views_today']:,}</span>
        <span>hôm nay</span>
    </span>
    <span class="vw-sep">·</span>
    <span class="vw-item">
        <span>👤</span>
        <span class="vw-num">{_stats['unique_today']:,}</span>
        <span>khách</span>
    </span>
    <span class="vw-sep">·</span>
    <span class="vw-item">
        <span>📊</span>
        <span class="vw-num">{_stats['total_views']:,}</span>
        <span>tổng</span>
    </span>
</div>
""", unsafe_allow_html=True)
except Exception as e:
    print(f"[WIDGET] Lỗi: {e}")


# ============================================================
# BANNER
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
# TIÊU ĐỀ
# ============================================================
st.title("🌦️ Dự báo thời tiết WeatherNext đa mô hình")


# ============================================================
# KHUNG GHIM HÀNG NGANG
# ============================================================
favs = load_favorites() if callable(load_favorites) else []

st.markdown(
    f"<div class='pin-header'>⭐ Vị trí đã ghim ({len(favs)})</div>",
    unsafe_allow_html=True,
)

if not favs:
    st.markdown(
        "<div class='pin-empty'>Chưa có vị trí nào. "
        "Sau khi tra cứu, nhấn <b>⭐ Ghim vị trí này</b> để lưu lại.</div>",
        unsafe_allow_html=True,
    )
else:
    MAX_PINS = 6
    shown = favs[:MAX_PINS]
    n = len(shown)

    pin_cols = st.columns(n, gap="small")
    for i, fav in enumerate(shown):
        with pin_cols[i]:
            display = fav["display"]
            short = display if len(display) <= 28 else display[:25] + "…"
            if st.button(
                f"📍 {short}",
                key=f"fav_btn_{fav['id']}",
                use_container_width=True,
                help=f"**{display}**\n\nTọa độ: ({fav['lat']:.4f}, {fav['lon']:.4f})",
            ):
                st.session_state["address_input"] = fav["address"]
                st.session_state["prefill_address"] = fav["address"]
                st.session_state["pending_run"] = True
                st.rerun()

    del_cols = st.columns(n, gap="small")
    for i, fav in enumerate(shown):
        with del_cols[i]:
            if st.button(
                "🗑️ Xóa",
                key=f"fav_del_{fav['id']}",
                use_container_width=True,
                help=f"Xóa ghim {fav['display']}",
            ):
                delete_favorite(fav["id"])
                st.rerun()

    if len(favs) > MAX_PINS:
        st.caption(f"_+ {len(favs) - MAX_PINS} vị trí khác_")

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
        def _on_submit():
            st.session_state["pending_run"] = True

        address = st.text_input(
            "Nhập địa chỉ (nhấn Enter):",
            value=st.session_state.get("address_input", "Ninh Kiều, Cần Thơ"),
            key="address_input",
            on_change=_on_submit,
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

    st.divider()
    with st.expander("🛡️ Quản trị viên", expanded=False):
        if not st.session_state.get("admin_authed"):
            pwd = st.text_input("Mật khẩu admin:", type="password",
                                key="admin_pwd_input")
            if st.button("🔓 Đăng nhập", key="admin_login_btn",
                         use_container_width=True):
                if pwd == ADMIN_PASSWORD:
                    st.session_state["admin_authed"] = True
                    st.success("✅ Đã xác thực.")
                    st.rerun()
                else:
                    st.error("❌ Sai mật khẩu.")
        else:
            st.success("✅ Đã xác thực admin")
            if st.button("📊 Mở bảng điều khiển", key="admin_open_btn",
                         use_container_width=True):
                st.session_state["show_admin"] = True
                st.rerun()
            if st.button("🚪 Đăng xuất admin", key="admin_logout_btn",
                         use_container_width=True):
                st.session_state["admin_authed"] = False
                st.session_state["show_admin"] = False
                st.rerun()


# ============================================================
# ADMIN PANEL
# ============================================================
if st.session_state.get("show_admin") and st.session_state.get("admin_authed"):
    fake_admin = {
        "username": "admin",
        "full_name": "Quản trị viên",
        "role": "admin",
        "id": 0,
    }
    render_admin_panel(fake_admin)
    st.markdown("---")
    if st.button("← Quay lại ứng dụng", key="admin_back_btn"):
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
    force = st.session_state.pop("force_refresh", False)

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

    if force:
        clear_api_cache()

    with st.spinner(
        f"☁️ Đang tải dữ liệu từ {len(model_keys)} mô hình"
        f"{' (làm mới)' if force else ''}…"
    ):
        raw_models = fetch_all_models(
            lat, lon, variables=DEFAULT_VARIABLES,
            days=days, model_keys=model_keys,
            force_refresh=force,
        )

    if not raw_models:
        st.error("❌ Không lấy được dữ liệu.")
        st.stop()

    _t = build_ensemble_dict(raw_models, "temperature_2m")
    _p = build_ensemble_dict(raw_models, "precipitation")
    if not _t and not _p:
        st.error("❌ Không parse được dữ liệu ensemble.")
        st.stop()

    st.session_state["has_results"] = True
    st.session_state["saved_lat"] = lat
    st.session_state["saved_lon"] = lon
    st.session_state["saved_full_name"] = full_name
    st.session_state["saved_raw_models"] = raw_models
    st.session_state["saved_days"] = days
    st.session_state["saved_model_keys"] = list(model_keys)
    st.session_state["saved_address"] = address if address else ""
    st.session_state["last_fetch_ts"] = _time.time()
    st.session_state["last_fetch_str"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")


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

    auto_refresh_needed = False
    if st.session_state.get("last_fetch_ts"):
        age_min = (_time.time() - st.session_state["last_fetch_ts"]) / 60
        if age_min > AUTO_REFRESH_MIN:
            auto_refresh_needed = True

    if auto_refresh_needed:
        age_min = (_time.time() - st.session_state["last_fetch_ts"]) / 60
        st.warning(
            f"⏰ **Dữ liệu đã cũ {age_min:.0f} phút.** "
            f"Nhấn **🔄 Làm mới dữ liệu** để cập nhật mô hình mới nhất."
        )

    res_info, res_refresh = st.columns([4, 1])

    with res_info:
        st.success(f"📍 {full_name} – Tọa độ: {lat:.4f}, {lon:.4f}")
        fetch_time = st.session_state.get("last_fetch_str", "—")
        st.caption(f"🕐 **Lần tải cuối:** {fetch_time}  ·  📊 {len(model_keys)} mô hình")

    with res_refresh:
        if st.button("🔄 Làm mới dữ liệu", key="btn_force_refresh",
                     use_container_width=True,
                     help="Bỏ qua cache, tải dữ liệu mới nhất"):
            st.session_state["force_refresh"] = True
            st.session_state["pending_run"] = True
            st.rerun()

    with st.expander("🛰️ **Trạng thái real-time các mô hình** — nhấn để xem",
                     expanded=False):
        st.caption("Các mô hình cập nhật theo chu kỳ UTC (Z): 00Z · 06Z · 12Z · 18Z")

        for mk in model_keys:
            info = ALL_MODELS[mk]
            age_h = get_model_age_hours(mk)
            run_str = format_run_time(mk)
            next_run = get_next_run_time(mk)
            next_vn = next_run.astimezone(timezone(timedelta(hours=7)))

            freq = info.get("update_freq_hours", 12)
            if age_h < freq:
                badge = "🟢"
            elif age_h < freq * 2:
                badge = "🟡"
            else:
                badge = "🔴"

            st.markdown(
                f"<div style='padding:6px 10px; border-bottom:1px solid #e8f4f8; "
                f"display:flex; font-size:0.85rem;'>"
                f"<div style='flex:2; font-weight:600; color:#0e4a7b;'>"
                f"{badge} {info['label']}</div>"
                f"<div style='flex:2; color:#354a5c;'>{run_str}</div>"
                f"<div style='flex:1; text-align:right; color:#1976d2;'>"
                f"Tiếp: {next_vn.strftime('%H:%M')} VN</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.caption(
            f"🕐 Giờ VN: **{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}**  ·  "
            f"🌍 UTC: **{datetime.now(timezone.utc).strftime('%d/%m %H:%M')}Z**"
        )

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
                    st.success("⭐ Đã ghim!") if saved else st.info("Đã có.")
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

    # TAB 1
    with tab1:
        st.subheader("📈 Dự báo nhiệt độ và mưa")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            subplot_titles=("Nhiệt độ 2m (°C)", "Mưa 1h (mm)"),
                            vertical_spacing=0.12)
        for mk, ens_df in temp_ensembles.items():
            stats = compute_ensemble_stats(ens_df)
            if stats.empty:
                continue
            color = ALL_MODELS[mk]["color"]
            label = ALL_MODELS[mk]["label"]
            rgb = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            fig.add_trace(go.Scatter(x=stats.index, y=stats["p90"], mode="lines",
                                     line=dict(width=0), showlegend=False,
                                     hoverinfo="skip"), row=1, col=1)
            fig.add_trace(go.Scatter(x=stats.index, y=stats["p10"], mode="lines",
                                     line=dict(width=0), fill="tonexty",
                                     fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)",
                                     name=f"{label} (10–90%)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=stats.index, y=stats["mean"], mode="lines",
                                     line=dict(color=color, width=2),
                                     name=f"{label} (TB)"), row=1, col=1)

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

        st.subheader(f"📌 Tóm tắt dự báo {days} ngày tới")
        c1, c2, c3, c4 = st.columns(4)
        if temp_ensembles:
            fm = list(temp_ensembles.keys())[0]
            stats = compute_ensemble_stats(temp_ensembles[fm])
            c1.metric("🌡️ T cao nhất", f"{float(stats['mean'].max()):.1f} °C")
            c2.metric("❄️ T thấp nhất", f"{float(stats['mean'].min()):.1f} °C")
        if precip_ensembles:
            fm = list(precip_ensembles.keys())[0]
            stats = compute_ensemble_stats(precip_ensembles[fm])
            c3.metric("💧 Tổng mưa", f"{float(stats['mean'].sum()):.1f} mm")
            c4.metric("☔ Đỉnh mưa 1h", f"{float(stats['mean'].max()):.1f} mm")

    # TAB 2
    with tab2:
        compare_var = st.radio(
            "Chọn biến so sánh:",
            options=["🌡️ Nhiệt độ", "💧 Lượng mưa"],
            horizontal=True, key="compare_var_radio",
            label_visibility="collapsed",
        )
        st.divider()

        if compare_var == "🌡️ Nhiệt độ":
            if not temp_ensembles:
                st.info("Không có dữ liệu nhiệt độ.")
            else:
                fig_cmp = go.Figure()
                for mk, ens_df in temp_ensembles.items():
                    stats = compute_ensemble_stats(ens_df)
                    if stats.empty:
                        continue
                    fig_cmp.add_trace(go.Scatter(
                        x=stats.index, y=stats["mean"], mode="lines",
                        line=dict(color=ALL_MODELS[mk]["color"], width=2),
                        name=ALL_MODELS[mk]["label"]))
                fig_cmp.update_layout(height=480, hovermode="x unified",
                                      xaxis_title="Thời gian",
                                      yaxis_title="Nhiệt độ (°C)",
                                      legend=dict(orientation="h", y=1.02))
                st.plotly_chart(fig_cmp, use_container_width=True)

                rows = [{"Mô hình": ALL_MODELS[mk]["label"],
                         "Std TB (°C)": round(compute_ensemble_stats(d)["std"].mean(), 3),
                         "Số thành viên": int(compute_ensemble_stats(d)["n_members"].max())}
                        for mk, d in temp_ensembles.items()
                        if not compute_ensemble_stats(d).empty]
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True,
                                 hide_index=True)
        else:
            if not precip_ensembles:
                st.info("Không có dữ liệu mưa.")
            else:
                n_models_p = len(precip_ensembles)
                use_bars_cmp = n_models_p <= BAR_MAX_MODELS
                fig_cmp2 = go.Figure()
                for mk, ens_df in precip_ensembles.items():
                    stats = compute_ensemble_stats(ens_df)
                    if stats.empty:
                        continue
                    if use_bars_cmp:
                        fig_cmp2.add_trace(go.Bar(
                            x=stats.index, y=stats["mean"],
                            marker=dict(color=ALL_MODELS[mk]["color"]),
                            name=ALL_MODELS[mk]["label"]))
                    else:
                        fig_cmp2.add_trace(go.Scatter(
                            x=stats.index, y=stats["mean"], mode="lines",
                            line=dict(color=ALL_MODELS[mk]["color"], width=2),
                            name=ALL_MODELS[mk]["label"]))
                fig_cmp2.update_layout(height=480, hovermode="x unified",
                                       xaxis_title="Thời gian",
                                       yaxis_title="Mưa 1h (mm)",
                                       barmode="group",
                                       legend=dict(orientation="h", y=1.02))
                st.plotly_chart(fig_cmp2, use_container_width=True)

                rows = [{"Mô hình": ALL_MODELS[mk]["label"],
                         "Std TB (mm)": round(compute_ensemble_stats(d)["std"].mean(), 3),
                         "Số thành viên": int(compute_ensemble_stats(d)["n_members"].max())}
                        for mk, d in precip_ensembles.items()
                        if not compute_ensemble_stats(d).empty]
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True,
                                 hide_index=True)

    # TAB 3
    with tab3:
        st.subheader("🕐 Chi tiết dự báo theo giờ")
        if not temp_ensembles and not precip_ensembles:
            st.warning("Không có dữ liệu.")
        else:
            opts = list(temp_ensembles.keys()) or list(precip_ensembles.keys())
            selected = st.radio("Chọn mô hình:", options=opts,
                                format_func=lambda k: ALL_MODELS[k]["label"],
                                horizontal=True, key="hourly_model_radio",
                                label_visibility="collapsed")

            run_str = format_run_time(selected)
            st.caption(f"🛰️ **{ALL_MODELS[selected]['label']}** — Chu kỳ: {run_str}")

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

            df = pd.DataFrame({"time": tmean.index, "temp": tmean.values,
                               "rain": pmean.values, "rain_prob": rprob.values})
            df = df[df["time"] >= start].sort_values("time").reset_index(drop=True)

            if not df.empty:
                df["phenomenon"] = df.apply(
                    lambda r: classify_weather_phenomenon(r["time"].hour,
                                                          r["rain"], r["temp"]),
                    axis=1)
                df["time_str"] = df["time"].dt.strftime("%d/%m %H:%M")

                disp = pd.DataFrame({
                    "Ngày/Giờ": df["time_str"].values,
                    "Hiện tượng": df["phenomenon"].values,
                    "Nhiệt độ (°C)": df["temp"].round(1).values,
                    "Mưa (mm)": df["rain"].round(2).values,
                    "Xác suất mưa (%)": (df["rain_prob"] * 100).round(0).astype(int).values,
                })

                st.caption(f"📊 {len(disp)} giờ — từ "
                           f"**{df['time'].min().strftime('%d/%m %H:%M')}** "
                           f"đến **{df['time'].max().strftime('%d/%m %H:%M')}**")
                st.dataframe(disp, use_container_width=True, hide_index=True,
                             height=600)

                csv_buf = io.StringIO()
                disp.to_csv(csv_buf, index=False, encoding="utf-8-sig")
                st.download_button("📥 Tải CSV",
                                   data=csv_buf.getvalue().encode("utf-8-sig"),
                                   file_name=f"du_bao_{selected}.csv",
                                   mime="text/csv", key="dl_hourly")

    # TAB 4
    with tab4:
        st.subheader("✅ Đánh giá QCVN 84:2024/BTNMT")
        if not enable_qcvn:
            st.info("Bật tùy chọn QCVN ở sidebar.")
        else:
            uploaded = st.file_uploader("File quan trắc (CSV):",
                                        type=["csv"], key="obs_upload")
            if uploaded:
                try:
                    obs_df = pd.read_csv(uploaded, parse_dates=["time"]).set_index("time")
                    all_eval = []
                    for mk in model_keys:
                        if mk in temp_ensembles:
                            edf = evaluate_forecast_qcvn(temp_ensembles[mk], obs_df,
                                                         "temperature_2m", "temperature")
                            if not edf.empty:
                                s = summarize_qcvn_evaluation(edf)
                                s["model"] = ALL_MODELS[mk]["label"]
                                s["variable"] = "Nhiệt độ"
                                s["grade"] = grade_forecast_qcvn(s)
                                all_eval.append(s)
                        if mk in precip_ensembles:
                            edf = evaluate_forecast_qcvn(precip_ensembles[mk], obs_df,
                                                         "precipitation", "precipitation")
                            if not edf.empty:
                                s = summarize_qcvn_evaluation(edf)
                                s["model"] = ALL_MODELS[mk]["label"]
                                s["variable"] = "Mưa"
                                s["grade"] = grade_forecast_qcvn(s)
                                all_eval.append(s)
                    if all_eval:
                        st.dataframe(pd.DataFrame(all_eval),
                                     use_container_width=True, hide_index=True)
                    else:
                        st.warning("Không đủ dữ liệu.")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    # TAB 5
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
# CHÀO MỪNG
# ============================================================
else:
    st.info("👈 Nhập địa chỉ hoặc tọa độ ở sidebar, chọn mô hình, "
            "rồi nhấn **🚀 Lấy dự báo** để bắt đầu.")


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
        &#169; 2026 Đài Khí tượng Thủy văn TP. Cần Thơ
    </div>
</div>
""", unsafe_allow_html=True)