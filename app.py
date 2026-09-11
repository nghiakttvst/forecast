"""
Ứng dụng web: Dự báo thời tiết WeatherNext đa mô hình + QCVN 84:2024/BTNMT.
Đài Khí tượng Thủy văn TP. Cần Thơ
Chạy: streamlit run app.py
"""

import io

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
    geocode_address, reverse_geocode_location,
    fetch_all_models, build_ensemble_dict,
)
from analysis import (
    compute_ensemble_stats, detect_extreme_events,
    deduplicate_alerts, summarize_temperature,
    summarize_precipitation, classify_weather_phenomenon,
)
from qcvn import (
    evaluate_forecast_qcvn, summarize_qcvn_evaluation,
    grade_forecast_qcvn,
)
from storage import (
    save_forecast, save_evaluation, load_evaluations,
    save_favorite, load_favorites, delete_favorite,
)
from notifier import send_telegram, format_alerts


BAR_MAX_MODELS = 3


# ============================================================
# CẤU HÌNH TRANG
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

    html, body, .stApp, .stMarkdown,
    h1, h2, h3, h4, h5, h6,
    p, span:not([class*="material"]):not([data-testid*="Icon"]),
    label, input, textarea, button, select,
    .stTextInput label, .stSelectbox label {
        font-family: 'Be Vietnam Pro', 'Inter', 'Segoe UI',
                     system-ui, -apple-system, sans-serif !important;
    }

    [data-testid="stIconMaterial"],
    [data-testid="stExpanderToggleIcon"],
    [data-testid="stIconEmoji"],
    span[class*="material-symbols"],
    span[class*="material-icons"],
    .material-symbols-rounded,
    .material-icons,
    i.material-icons,
    .stIcon {
        font-family: 'Material Symbols Rounded',
                     'Material Icons',
                     'Material Icons Round' !important;
    }

    .stApp {
        background: linear-gradient(180deg, #eaf4fb 0%, #f4faff 45%, #fffaf0 100%);
        background-attachment: fixed;
    }

    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 1rem !important;
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
        box-shadow: none !important;
        backdrop-filter: blur(8px);
        z-index: 999;
    }

    section[data-testid="stSidebar"] * {
        font-family: inherit;
    }
    section[data-testid="stSidebar"] .material-symbols-rounded,
    section[data-testid="stSidebar"] [data-testid="stIconMaterial"],
    section[data-testid="stSidebar"] .stIcon {
        font-family: 'Material Symbols Rounded' !important;
    }

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
        box-shadow: 0 10px 28px rgba(74, 159, 224, 0.35),
                    0 1px 0 rgba(255, 255, 255, 0.5) inset;
        transform: translateY(-2px);
    }
    .header-banner .deco-icon {
        position: absolute;
        font-size: 6rem;
        opacity: 0.10;
        pointer-events: none;
        user-select: none;
        line-height: 1;
        transition: opacity 0.4s ease, transform 0.6s ease;
    }
    .header-banner .deco-icon.left {
        left: 18px; top: 50%;
        transform: translateY(-50%) rotate(-8deg);
    }
    .header-banner .deco-icon.right {
        right: 18px; top: 50%;
        transform: translateY(-50%) rotate(8deg);
    }
    .header-banner:hover .deco-icon { opacity: 0.16; }
    .header-banner-content { position: relative; z-index: 2; text-align: center; }
    .header-banner-line1 {
        font-size: 1.0rem; font-weight: 600; letter-spacing: 3.2px;
        margin: 0 0 4px 0; text-transform: uppercase;
        color: rgba(255, 255, 255, 0.92);
        text-shadow: 0 1px 2px rgba(0, 60, 100, 0.15);
    }
    .header-banner-line2 {
        font-size: 2.5rem; font-weight: 1000; letter-spacing: 1.2px;
        margin: 0; line-height: 1.25; text-transform: uppercase;
        color: #ffffff;
        text-shadow: 0 2px 4px rgba(0, 60, 100, 0.25),
                     0 0 18px rgba(255, 255, 255, 0.15);
    }
    .header-banner .inline-icon {
        display: inline-block; font-size: 1.6rem; margin: 0 12px;
        vertical-align: middle; opacity: 0.75;
        filter: drop-shadow(0 1px 3px rgba(0, 60, 100, 0.2));
        transition: opacity 0.3s ease, transform 0.3s ease;
    }
    .header-banner-line1 .inline-icon { font-size: 1.35rem; }
    .header-banner:hover .inline-icon { opacity: 0.95; transform: scale(1.08); }

    h1 {
        font-size: 1.55rem !important; font-weight: 700 !important;
        letter-spacing: 0.3px !important; margin-top: 0 !important;
        margin-bottom: 0.7rem !important; line-height: 1.35 !important;
        color: #0e4a7b !important;
    }
    h2, h3 { color: #145a92 !important; letter-spacing: 0.2px; }

    .stButton > button {
        text-align: left; border-radius: 10px;
        transition: all 0.25s ease;
    }
    .stButton > button:hover { transform: translateY(-1px); }

    .footer {
        margin-top: 40px; padding: 20px 24px;
        background: linear-gradient(90deg,
            rgba(74, 159, 224, 0.08) 0%,
            rgba(109, 200, 194, 0.10) 100%);
        border-top: 2px solid rgba(74, 159, 224, 0.28);
        border-radius: 10px 10px 0 0;
        text-align: center; color: #354a5c;
        font-size: 0.92rem; line-height: 1.75;
        transition: box-shadow 0.4s ease;
    }
    .footer:hover { box-shadow: 0 -4px 16px rgba(74, 159, 224, 0.12); }
    .footer strong { color: #0e4a7b; font-weight: 700; }
    .footer a {
        color: #1976d2; text-decoration: none;
        font-weight: 600; transition: color 0.25s ease;
    }
    .footer a:hover { color: #0d47a1; text-decoration: underline; }
    .footer-line {
        display: flex; align-items: center; justify-content: center;
        flex-wrap: wrap; gap: 8px; margin: 5px 0;
    }
    .footer-icon { font-size: 1.05rem; opacity: 0.85; }
    .footer-copyright {
        margin-top: 12px; font-size: 0.8rem;
        color: #6d8a99; letter-spacing: 0.2px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# BANNER
# ============================================================
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

# ============================================================
# SESSION STATE
# ============================================================
if "address_input" not in st.session_state:
    st.session_state["address_input"] = "Ninh Kiều, Cần Thơ"
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

if st.session_state.get("prefill_address"):
    st.session_state["address_input"] = st.session_state["prefill_address"]
    st.session_state["prefill_address"] = None
    st.session_state["pending_run"] = True


def _load_favorites_safe():
    try:
        return load_favorites()
    except Exception as e:
        print(f"[FAV] Lỗi đọc DB: {e}")
        return []


# ============================================================
# HEADER
# ============================================================
title_col, pins_col = st.columns([3, 2])

with title_col:
    st.title("🌦️ Dự báo thời tiết WeatherNext đa mô hình")

with pins_col:
    favorites = _load_favorites_safe()
    st.markdown(
        f"<div style='font-size:0.9rem; font-weight:600; "
        f"margin-bottom:0.3rem;'>⭐ Vị trí đã ghim ({len(favorites)})</div>",
        unsafe_allow_html=True,
    )

    if favorites:
        MAX_DISPLAY = 6
        shown = favorites[:MAX_DISPLAY]
        cols_per_row = 2

        for i in range(0, len(shown), cols_per_row):
            batch = shown[i:i + cols_per_row]
            row_cols = st.columns(cols_per_row, gap="small")
            for j, fav in enumerate(batch):
                with row_cols[j]:
                    btn_col, del_col = st.columns([8, 1], gap="small")
                    with btn_col:
                        if st.button(
                            fav["display"], key=f"fav_btn_{fav['id']}",
                            use_container_width=True,
                            help=f"Vĩ độ: {fav['lat']:.4f}  |  Kinh độ: {fav['lon']:.4f}",
                        ):
                            st.session_state["prefill_address"] = fav["address"]
                            st.rerun()
                    with del_col:
                        if st.button("✕", key=f"fav_del_{fav['id']}",
                                     help="Xóa ghim"):
                            delete_favorite(fav["id"])
                            st.rerun()

        if len(favorites) > MAX_DISPLAY:
            st.caption(f"+ {len(favorites) - MAX_DISPLAY} vị trí khác")
    else:
        st.caption("Chưa có vị trí nào. Sau khi tra cứu, nhấn "
                   "**⭐ Ghim vị trí này** để lưu lại.")

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
            "Nhập địa chỉ (nhấn Enter):", key="address_input",
            on_change=_on_address_submit, placeholder="VD: Ninh Kiều, Cần Thơ",
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
        "Mô hình dự báo:", options=list(ALL_MODELS.keys()),
        default=list(MODELS.keys()), format_func=_fmt_model, key="model_select",
    )

    days = st.slider("Số ngày dự báo:", 1, 15, 10, key="days_slider")

    st.header("📊 Đánh giá QCVN")
    enable_qcvn = st.checkbox("Bật đánh giá sai số QCVN", value=True,
                              key="enable_qcvn")

    st.header("🔔 Thông báo")
    enable_telegram = st.checkbox("Gửi Telegram nếu có cảnh báo", value=False,
                                  key="enable_tg")

    st.divider()

    with st.expander("📋 Chọn nhanh từ danh sách tỉnh", expanded=False):
        st.caption("⚠️ Lần đầu mở có thể mất 15–20s để nạp GeoJSON. "
                   "Các lần sau sẽ nhanh hơn nhờ cache.")
        load_btn = st.button("🔄 Tải danh sách tỉnh",
                             key="load_provinces_btn", use_container_width=True)

        if load_btn or st.session_state.get("provinces_loaded"):
            if not st.session_state.get("provinces_loaded"):
                with st.spinner("📂 Đang nạp GeoJSON tỉnh/thành…"):
                    try:
                        from geojson_lookup import list_provinces
                        provinces = list_provinces()
                        st.session_state["provinces_list"] = provinces
                        st.session_state["provinces_loaded"] = True
                    except Exception as e:
                        provinces = []
                        st.error(f"Lỗi: {e}")

            provinces = st.session_state.get("provinces_list", [])
            if provinces:
                chosen = st.selectbox("Tỉnh/Thành phố:", [""] + provinces,
                                      key="quick_province_select")
                if chosen:
                    st.session_state["prefill_address"] = chosen
                    st.session_state["pending_run"] = True
                    st.rerun()

    st.divider()
    run_btn = st.button("🚀 Lấy dự báo", type="primary",
                        use_container_width=True, key="run_btn")


# ============================================================
# XỬ LÝ CHÍNH
# ============================================================
trigger_run = run_btn or st.session_state.get("pending_run")

if trigger_run:
    st.session_state["pending_run"] = False
    lat, lon, full_name = None, None, None

    # Bước 1: Xác định tọa độ
    if input_mode == "Địa chỉ":
        with st.spinner("🔍 Đang tra cứu địa chỉ…"):
            geo = geocode_address(address)

        if not geo:
            st.error(f"❌ Không tìm thấy địa chỉ: **{address}**")
            st.markdown("""
**💡 Thử một trong các cách sau:**
1. **Viết không dấu**: `Ninh Kieu, Can Tho`
2. **Thêm quốc gia**: `Ninh Kieu, Can Tho, Vietnam`
3. **Chỉ nhập tỉnh/thành**: `Can Tho` hoặc `Cần Thơ`
4. **Dùng tọa độ trực tiếp** (chọn chế độ "Tọa độ" ở sidebar)

**Tọa độ tham khảo:**
- Cần Thơ: `10.0291, 105.7706`
- Hà Nội: `21.0285, 105.8542`
- TP.HCM: `10.8231, 106.6297`
- Đà Nẵng: `16.0544, 108.2022`
""")
            with st.expander("📌 Nhập tọa độ thủ công"):
                c1, c2 = st.columns(2)
                with c1:
                    mlat = st.number_input("Vĩ độ:", value=10.0291,
                                           format="%.4f", key="mlat")
                with c2:
                    mlon = st.number_input("Kinh độ:", value=105.7706,
                                           format="%.4f", key="mlon")
                if st.button("Dùng tọa độ này", key="use_manual"):
                    lat, lon = mlat, mlon
                    full_name = f"({lat:.4f}, {lon:.4f})"
            if lat is None:
                st.stop()
        else:
            lat, lon, full_name = geo
    else:
        lat, lon = lat_input, lon_input
        with st.spinner("🗺️ Đang tra cứu tên địa danh…"):
            rg = reverse_geocode_location(lat, lon)
        parts = [p for p in [rg.get("commune"), rg.get("province")] if p]
        full_name = ", ".join(parts) if parts else f"({lat:.4f}, {lon:.4f})"

    if not model_keys:
        st.warning("Vui lòng chọn ít nhất một mô hình.")
        st.stop()

    # Bước 2: Gọi API
    with st.spinner("☁️ Đang tải dữ liệu từ các mô hình…"):
        raw_models = fetch_all_models(lat, lon, variables=DEFAULT_VARIABLES,
                                      days=days, model_keys=model_keys)

    if not raw_models:
        st.error("❌ Không lấy được dữ liệu từ bất kỳ mô hình nào.")
        st.stop()

    _test_temp = build_ensemble_dict(raw_models, "temperature_2m")
    _test_precip = build_ensemble_dict(raw_models, "precipitation")

    if not _test_temp and not _test_precip:
        st.error("❌ Không parse được dữ liệu ensemble.")
        st.stop()

    # Lưu kết quả vào session_state
    st.session_state["has_results"] = True
    st.session_state["saved_lat"] = lat
    st.session_state["saved_lon"] = lon
    st.session_state["saved_full_name"] = full_name
    st.session_state["saved_raw_models"] = raw_models
    st.session_state["saved_days"] = days
    st.session_state["saved_model_keys"] = list(model_keys)
    st.session_state["saved_address"] = address if address else ""


# ============================================================
# RENDER KẾT QUẢ TỪ SESSION_STATE
# ============================================================
if st.session_state.get("has_results"):
    # Cảnh báo nếu settings đổi
    if (st.session_state.get("saved_days") != days or
        st.session_state.get("saved_model_keys") != list(model_keys)):
        st.warning(
            "⚠️ Thông số **số ngày / mô hình** đã thay đổi so với "
            "kết quả đang hiển thị. Nhấn **🚀 Lấy dự báo** để cập nhật."
        )

    # Lấy dữ liệu từ session
    lat = st.session_state["saved_lat"]
    lon = st.session_state["saved_lon"]
    full_name = st.session_state["saved_full_name"]
    raw_models = st.session_state["saved_raw_models"]
    days = st.session_state["saved_days"]
    model_keys = st.session_state["saved_model_keys"]
    address = st.session_state.get("saved_address", "")

    temp_ensembles = build_ensemble_dict(raw_models, "temperature_2m")
    precip_ensembles = build_ensemble_dict(raw_models, "precipitation")

    if not temp_ensembles and not precip_ensembles:
        st.error("❌ Không parse được dữ liệu ensemble.")
        st.session_state["has_results"] = False
        st.stop()

    # Hiển thị vị trí
    st.success(f"📍 {full_name} – Tọa độ: {lat:.4f}, {lon:.4f}")

    # Nút Ghim
    fav_col1, fav_col2 = st.columns([1, 4])
    with fav_col1:
        current_favs = _load_favorites_safe()
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
                        st.info("Vị trí đã có trong danh sách.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi ghim: {e}")

    # Bước 3: Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 Biểu đồ dự báo",
        "📊 So sánh mô hình",
        "🕐 Theo giờ",
        "✅ Đánh giá QCVN",
        "💾 Lịch sử",
        "🗺️ Vị trí & Vùng",
    ])

    # ============================================================
    # TAB 1: BIỂU ĐỒ
    # ============================================================
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

            fig.add_trace(go.Scatter(x=stats.index, y=stats["p90"],
                                     mode="lines", line=dict(width=0),
                                     showlegend=False, hoverinfo="skip"), row=1, col=1)
            fig.add_trace(go.Scatter(x=stats.index, y=stats["p10"],
                                     mode="lines", line=dict(width=0),
                                     fill="tonexty",
                                     fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)",
                                     name=f"{label} (10–90%)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=stats.index, y=stats["mean"],
                                     mode="lines", line=dict(color=color, width=2),
                                     name=f"{label} (TB)"), row=1, col=1)

        n_precip_models = len(precip_ensembles)
        use_bars = n_precip_models <= BAR_MAX_MODELS

        st.caption(f"💧 Mưa hiển thị dạng **{'cột' if use_bars else 'đường'}** "
                   f"({n_precip_models} mô hình {'≤' if use_bars else '>'} {BAR_MAX_MODELS})")

        for mk, ens_df in precip_ensembles.items():
            stats = compute_ensemble_stats(ens_df)
            if stats.empty:
                continue
            color = ALL_MODELS[mk]["color"]
            label = ALL_MODELS[mk]["label"]
            rgb = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

            if use_bars:
                upper = (stats["p90"] - stats["mean"]).clip(lower=0)
                lower = (stats["mean"] - stats["p10"]).clip(lower=0)
                fig.add_trace(go.Bar(
                    x=stats.index, y=stats["mean"], name=f"{label} (mưa)",
                    marker=dict(color=color),
                    error_y=dict(type="data", symmetric=False, array=upper,
                                 arrayminus=lower, color=color,
                                 thickness=1.2, width=0),
                    showlegend=False,
                    hovertemplate=f"<b>{label}</b><br>%{{x|%d/%m %H:%M}}<br>TB: %{{y:.2f}} mm<extra></extra>",
                ), row=2, col=1)
            else:
                fig.add_trace(go.Scatter(x=stats.index, y=stats["p90"],
                                         mode="lines", line=dict(width=0),
                                         showlegend=False, hoverinfo="skip"), row=2, col=1)
                fig.add_trace(go.Scatter(x=stats.index, y=stats["p10"],
                                         mode="lines", line=dict(width=0),
                                         fill="tonexty",
                                         fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)",
                                         showlegend=False), row=2, col=1)
                fig.add_trace(go.Scatter(x=stats.index, y=stats["mean"],
                                         mode="lines", line=dict(color=color, width=2),
                                         name=f"{label} (mưa)",
                                         showlegend=False), row=2, col=1)

        fig.update_layout(
            height=720, hovermode="x unified", barmode="group",
            bargap=0.15, bargroupgap=0.05,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=40, r=20, t=80, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tóm tắt
        st.subheader(f"📌 Tóm tắt dự báo {days} ngày tới")
        st.caption(f"Thống kê dựa trên **trung bình ensemble** – "
                   f"khoảng **{days * 24} giờ** dự báo "
                   f"(từ {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')} "
                   f"đến {(pd.Timestamp.now() + pd.Timedelta(days=days)).strftime('%d/%m/%Y')})")

        c1, c2, c3, c4 = st.columns(4)

        if temp_ensembles:
            first_mk = list(temp_ensembles.keys())[0]
            stats = compute_ensemble_stats(temp_ensembles[first_mk])
            t_max = float(stats["mean"].max())
            time_tmax = stats["mean"].idxmax()
            t_min = float(stats["mean"].min())
            time_tmin = stats["mean"].idxmin()

            c1.metric("🌡️ T cao nhất", f"{t_max:.1f} °C",
                      help=f"Cao nhất trong **{days} ngày** tới. "
                           f"Đạt lúc {time_tmax.strftime('%d/%m/%Y %H:%M')}.")
            c2.metric("❄️ T thấp nhất", f"{t_min:.1f} °C",
                      help=f"Thấp nhất trong **{days} ngày** tới. "
                           f"Đạt lúc {time_tmin.strftime('%d/%m/%Y %H:%M')}.")

        if precip_ensembles:
            first_mk = list(precip_ensembles.keys())[0]
            stats = compute_ensemble_stats(precip_ensembles[first_mk])
            total_rain = float(stats["mean"].sum())
            peak_rain = float(stats["mean"].max())
            time_peak = stats["mean"].idxmax()

            c3.metric("💧 Tổng lượng mưa", f"{total_rain:.1f} mm",
                      help=f"Tổng cộng dồn trong **{days} ngày** tới ({days * 24} giờ).")
            c4.metric("☔ Đỉnh mưa 1h", f"{peak_rain:.1f} mm",
                      help=f"Lượng mưa lớn nhất trong **1 giờ**, "
                           f"đạt lúc {time_peak.strftime('%d/%m/%Y %H:%M')}.")

        try:
            if temp_ensembles:
                first_mk = list(temp_ensembles.keys())[0]
                stats = compute_ensemble_stats(temp_ensembles[first_mk])
                summ = summarize_temperature(stats)
                save_forecast(full_name, lat, lon, ALL_MODELS[first_mk]["label"],
                              "temperature_2m", days, summ)
            if precip_ensembles:
                first_mk = list(precip_ensembles.keys())[0]
                stats = compute_ensemble_stats(precip_ensembles[first_mk])
                summ = summarize_precipitation(stats)
                save_forecast(full_name, lat, lon, ALL_MODELS[first_mk]["label"],
                              "precipitation", days, summ)
        except Exception as e:
            print(f"[DB] Lỗi lưu forecast: {e}")

    # ============================================================
    # TAB 2: SO SÁNH
    # ============================================================
    with tab2:
        st.subheader("📊 So sánh dự báo giữa các mô hình")

        if temp_ensembles:
            st.markdown("**Nhiệt độ 2m – Trung bình ensemble**")
            fig_cmp = go.Figure()
            for mk, ens_df in temp_ensembles.items():
                stats = compute_ensemble_stats(ens_df)
                if stats.empty:
                    continue
                fig_cmp.add_trace(go.Scatter(
                    x=stats.index, y=stats["mean"], mode="lines",
                    line=dict(color=ALL_MODELS[mk]["color"], width=2),
                    name=ALL_MODELS[mk]["label"]))
            fig_cmp.update_layout(xaxis_title="Thời gian", yaxis_title="°C",
                                  height=420, hovermode="x unified",
                                  margin=dict(l=40, r=20, t=30, b=40))
            st.plotly_chart(fig_cmp, use_container_width=True)

        if precip_ensembles:
            n_models_p = len(precip_ensembles)
            use_bars_cmp = n_models_p <= BAR_MAX_MODELS
            st.markdown(f"**Mưa 1h – Trung bình ensemble** "
                        f"(dạng {'cột' if use_bars_cmp else 'đường'}, {n_models_p} mô hình)")

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
                        hovertemplate="%{x|%d/%m %H:%M}<br>%{y:.2f} mm<extra></extra>"))
                else:
                    fig_cmp2.add_trace(go.Scatter(
                        x=stats.index, y=stats["mean"], mode="lines",
                        line=dict(color=ALL_MODELS[mk]["color"], width=2),
                        name=ALL_MODELS[mk]["label"]))

            fig_cmp2.update_layout(xaxis_title="Thời gian", yaxis_title="mm",
                                   height=420, hovermode="x unified",
                                   barmode="group", bargap=0.15, bargroupgap=0.05,
                                   margin=dict(l=40, r=20, t=30, b=40))
            st.plotly_chart(fig_cmp2, use_container_width=True)

        st.subheader("Độ bất định (std) trung bình theo mô hình")
        rows = []
        for mk, ens_df in temp_ensembles.items():
            stats = compute_ensemble_stats(ens_df)
            if not stats.empty:
                rows.append({
                    "Mô hình": ALL_MODELS[mk]["label"],
                    "Biến": "Nhiệt độ",
                    "Std TB": round(stats["std"].mean(), 3),
                    "Số thành viên": int(stats["n_members"].max()),
                })
        for mk, ens_df in precip_ensembles.items():
            stats = compute_ensemble_stats(ens_df)
            if not stats.empty:
                rows.append({
                    "Mô hình": ALL_MODELS[mk]["label"],
                    "Biến": "Mưa",
                    "Std TB": round(stats["std"].mean(), 3),
                    "Số thành viên": int(stats["n_members"].max()),
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ============================================================
    # TAB 3: THEO GIỜ
    # ============================================================
    with tab3:
        st.subheader("🕐 Chi tiết dự báo theo giờ")

        if not temp_ensembles and not precip_ensembles:
            st.warning("Không có dữ liệu dự báo để hiển thị.")
        else:
            model_options = list(temp_ensembles.keys()) or list(precip_ensembles.keys())

            st.markdown("**Chọn mô hình để xem chi tiết:**")
            selected_model = st.radio(
                "Chọn mô hình:", options=model_options,
                format_func=lambda k: ALL_MODELS[k]["label"],
                horizontal=True, key="hourly_model_radio",
                label_visibility="collapsed",
            )

            temp_df = temp_ensembles.get(selected_model)
            precip_df = precip_ensembles.get(selected_model)

            if temp_df is not None and not temp_df.empty:
                temp_mean = temp_df.mean(axis=1)
            else:
                temp_mean = pd.Series(dtype=float)

            if precip_df is not None and not precip_df.empty:
                precip_mean = precip_df.mean(axis=1)
                rain_prob = (precip_df > 0.1).sum(axis=1) / precip_df.notna().sum(axis=1)
            else:
                precip_mean = pd.Series(0.0, index=temp_mean.index)
                rain_prob = pd.Series(0.0, index=temp_mean.index)

            now = pd.Timestamp.now()
            start_time = now.floor("h") - pd.Timedelta(hours=1)

            df = pd.DataFrame({
                "time": temp_mean.index,
                "temp": temp_mean.values,
                "rain": precip_mean.values,
                "rain_prob": rain_prob.values,
            })

            df = df[df["time"] >= start_time].copy()
            df = df.sort_values("time").reset_index(drop=True)

            if df.empty:
                st.warning("Không có dữ liệu trong khoảng thời gian hiện tại trở đi.")
            else:
                df["phenomenon"] = df.apply(
                    lambda row: classify_weather_phenomenon(
                        row["time"].hour, row["rain"], row["temp"]
                    ), axis=1
                )
                df["time_str"] = df["time"].dt.strftime("%d/%m %H:%M")

                display_df = pd.DataFrame({
                    "Ngày/Giờ": df["time_str"].values,
                    "Hiện tượng": df["phenomenon"].values,
                    "Nhiệt độ (°C)": df["temp"].round(1).values,
                    "Mưa (mm)": df["rain"].round(2).values,
                    "Xác suất mưa (%)": (df["rain_prob"] * 100).round(0).astype(int).values,
                })

                st.caption(
                    f"📊 **{ALL_MODELS[selected_model]['label']}** — "
                    f"{len(display_df)} giờ "
                    f"(từ **{df['time'].min().strftime('%d/%m %H:%M')}** "
                    f"đến **{df['time'].max().strftime('%d/%m %H:%M')}**)"
                )

                st.dataframe(
                    display_df, use_container_width=True, hide_index=True,
                    height=620,
                    column_config={
                        "Ngày/Giờ": st.column_config.TextColumn("Ngày/Giờ", width="small"),
                        "Hiện tượng": st.column_config.TextColumn("Hiện tượng", width="medium"),
                        "Nhiệt độ (°C)": st.column_config.NumberColumn("Nhiệt độ (°C)", format="%.1f", width="small"),
                        "Mưa (mm)": st.column_config.NumberColumn("Mưa (mm)", format="%.2f", width="small"),
                        "Xác suất mưa (%)": st.column_config.ProgressColumn(
                            "Xác suất mưa (%)", min_value=0, max_value=100,
                            format="%d%%", width="medium"),
                    },
                )

                csv_buf = io.StringIO()
                display_df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 Tải bảng CSV",
                    data=csv_buf.getvalue().encode("utf-8-sig"),
                    file_name=f"du_bao_theo_gio_{selected_model}.csv",
                    mime="text/csv", key="dl_hourly_tab3",
                )

    # ============================================================
    # TAB 4: QCVN
    # ============================================================
    with tab4:
        st.subheader("✅ Đánh giá chất lượng dự báo theo QCVN 84:2024/BTNMT")
        st.caption("Thông tư 46/2024/TT-BTNMT, áp dụng từ 30/6/2025.")

        if not enable_qcvn:
            st.info("Bật tùy chọn 'Đánh giá sai số QCVN' ở sidebar để xem.")
        else:
            st.info("⚠️ **Lưu ý:** Đánh giá QCVN yêu cầu **dữ liệu quan trắc thực đo**. "
                    "Tải file CSV với 2 cột `time` và `observed` để đánh giá.")

            uploaded = st.file_uploader("Tải lên file quan trắc (CSV):",
                                        type=["csv"], key="obs_upload")

            if uploaded is not None:
                try:
                    obs_df = pd.read_csv(uploaded, parse_dates=["time"])
                    obs_df = obs_df.set_index("time")
                except Exception as e:
                    st.error(f"Lỗi đọc file: {e}")
                    st.stop()

                all_eval = []
                for mk in model_keys:
                    if mk in temp_ensembles:
                        try:
                            eval_df = evaluate_forecast_qcvn(
                                temp_ensembles[mk], obs_df,
                                "temperature_2m", "temperature")
                            if not eval_df.empty:
                                summ = summarize_qcvn_evaluation(eval_df)
                                summ["model"] = ALL_MODELS[mk]["label"]
                                summ["variable"] = "Nhiệt độ"
                                summ["grade"] = grade_forecast_qcvn(summ)
                                all_eval.append(summ)
                        except Exception as e:
                            print(f"[QCVN] Lỗi {mk} nhiệt độ: {e}")

                    if mk in precip_ensembles:
                        try:
                            eval_df = evaluate_forecast_qcvn(
                                precip_ensembles[mk], obs_df,
                                "precipitation", "precipitation")
                            if not eval_df.empty:
                                summ = summarize_qcvn_evaluation(eval_df)
                                summ["model"] = ALL_MODELS[mk]["label"]
                                summ["variable"] = "Mưa"
                                summ["grade"] = grade_forecast_qcvn(summ)
                                all_eval.append(summ)
                        except Exception as e:
                            print(f"[QCVN] Lỗi {mk} mưa: {e}")

                if all_eval:
                    result_df = pd.DataFrame(all_eval)
                    display_cols = ["model", "variable", "ME", "MAE", "RMSE",
                                    "Bias", "PC", "pct_within_qcvn", "grade"]
                    available = [c for c in display_cols if c in result_df.columns]
                    st.dataframe(
                        result_df[available].rename(columns={
                            "model": "Mô hình", "variable": "Biến",
                            "pct_within_qcvn": "% đạt QCVN", "grade": "Xếp hạng"}),
                        use_container_width=True, hide_index=True)

                    for row in all_eval:
                        try:
                            save_evaluation(full_name, lat, lon,
                                            row["model"], row["variable"], row)
                        except Exception as e:
                            print(f"[DB] Lỗi lưu eval: {e}")
                    st.success("💾 Đã lưu kết quả đánh giá vào lịch sử.")
                else:
                    st.warning("Không đủ dữ liệu để đánh giá.")
            else:
                st.markdown("""
**Các chỉ số đánh giá theo QCVN 84:2024/BTNMT:**

| Chỉ số | Công thức | Ý nghĩa |
|---|---|---|
| **ME** | ME = (1/N)Σ(Fᵢ − Oᵢ) | Sai số trung bình (có dấu) |
| **MAE** | MAE = (1/N)Σ abs(Fᵢ − Oᵢ) | Sai số tuyệt đối trung bình |
| **RMSE** | RMSE = sqrt[(1/N)Σ(Fᵢ − Oᵢ)²] | Sai số bình phương trung bình |
| **Bias** | Bias = mean(F) / mean(O) | Tỷ số dự báo/thực đo (lý tưởng = 1) |
| **PC** | PC = (số điểm đúng) / N | Xác suất dự báo đúng |
| **Scf** | Scf = 1.5 × sigma | Sai số cho phép |
""")
                st.markdown("**Ngưỡng sai số cho phép cho MƯA (QCVN 84):**")
                st.markdown("""
| Thời hạn | Sai số cho phép |
|---|---|
| Đến 12h | ±20% giá trị dự báo |
| 12–24h | ±30% giá trị dự báo |
| 24–48h | ±40% giá trị dự báo |
""")
                st.markdown("**Ngưỡng sai số cho phép cho NHIỆT ĐỘ (tham khảo):**")
                st.markdown("""
| Thời hạn | Ngưỡng |
|---|---|
| 0–24h | ±2.0°C |
| 24–48h | ±2.5°C |
| 48–72h | ±3.0°C |
| >72h | ±3.5°C |
""")
                st.markdown("**File CSV mẫu:**")
                st.code("time,observed\n"
                        "2026-09-10 00:00:00,28.5\n"
                        "2026-09-10 01:00:00,27.8\n"
                        "2026-09-10 02:00:00,27.2", language="csv")

    # ============================================================
    # TAB 5: LỊCH SỬ
    # ============================================================
    with tab5:
        st.subheader("💾 Lịch sử đánh giá")
        try:
            hist = load_evaluations(limit=200)
        except Exception as e:
            st.error(f"Lỗi đọc DB: {e}")
            hist = pd.DataFrame()

        if hist.empty:
            st.info("Chưa có dữ liệu lịch sử. Hãy chạy đánh giá QCVN trước.")
        else:
            st.dataframe(hist, use_container_width=True, hide_index=True)
            if "created_at" in hist.columns and "RMSE" in hist.columns:
                hist["created_at"] = pd.to_datetime(hist["created_at"])
                fig_hist = go.Figure()
                for var in hist["variable"].dropna().unique():
                    sub = hist[hist["variable"] == var].sort_values("created_at")
                    fig_hist.add_trace(go.Scatter(
                        x=sub["created_at"], y=sub["RMSE"],
                        mode="lines+markers", name=var))
                fig_hist.update_layout(
                    title="Xu hướng RMSE theo thời gian",
                    xaxis_title="Thời gian", yaxis_title="RMSE",
                    height=400, margin=dict(l=40, r=20, t=50, b=40))
                st.plotly_chart(fig_hist, use_container_width=True)

            csv_buf = io.StringIO()
            hist.to_csv(csv_buf, index=False)
            st.download_button("📥 Tải lịch sử (CSV)", data=csv_buf.getvalue(),
                               file_name="history.csv", mime="text/csv")

    # ============================================================
    # TAB 6: VỊ TRÍ & VÙNG
    # ============================================================
    with tab6:
        st.subheader("🗺️ Thông tin vị trí")
        with st.spinner("🗺️ Đang tra cứu tên địa danh…"):
            rg = reverse_geocode_location(lat, lon)

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Vĩ độ", f"{lat:.4f}")
            st.metric("Kinh độ", f"{lon:.4f}")
        with c2:
            st.metric("Tỉnh/Thành", rg.get("province") or "—")
            commune_display = rg.get("commune") or "—"
            if commune_display and "," in commune_display:
                commune_display = commune_display.split(",")[0].strip()
            st.metric("Phường/Xã", commune_display)

        st.markdown("**Vị trí trên bản đồ**")
        map_df = pd.DataFrame({"lat": [lat], "lon": [lon], "name": [full_name]})
        try:
            fig_map = px.scatter_mapbox(map_df, lat="lat", lon="lon", text="name",
                                        zoom=10, height=420)
            fig_map.update_traces(marker=dict(size=18, color="red"))
            fig_map.update_layout(mapbox_style="open-street-map",
                                  margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_map, use_container_width=True)
        except Exception as e:
            st.warning(f"Không vẽ được bản đồ: {e}")

# ============================================================
# TRANG CHÀO MỪNG
# ============================================================
else:
    st.info("👈 Nhập địa chỉ hoặc tọa độ ở sidebar, chọn mô hình, "
            "rồi nhấn **Enter** hoặc nút **🚀 Lấy dự báo** để bắt đầu.")

    st.markdown("""
### 🌟 Tính năng chính

| Tính năng | Mô tả |
|---|---|
| 🌍 **Đa mô hình** | 5 ensemble (WeatherNext 2, GFS, ECMWF, ICON, GEM) + 3 mô hình tham chiếu |
| 📊 **Dải bất định** | Percentile 10–90 từ ensemble |
| 🕐 **Theo giờ** | Bảng chi tiết từng giờ với hiện tượng, nhiệt độ, mưa, xác suất mưa |
| ✅ **Đánh giá QCVN 84:2024** | ME, MAE, RMSE, Bias, PC theo quy chuẩn |
| 💾 **Lịch sử** | Lưu theo dõi độ chính xác theo thời gian |
| 🗺️ **Định vị 2 cấp** |tỉnh/thành + phường/xã |
| ⭐ **Ghim vị trí** | Lưu và truy cập nhanh các địa điểm yêu thích |
| 🔔 **Thông báo** | Telegram tùy chọn |

### 📋 Quy trình sử dụng

1. **Nhập vị trí** – gõ địa chỉ rồi nhấn **Enter** (tự động chạy), hoặc nhập tọa độ
2. **Chọn mô hình** – 5 ensemble mặc định, thêm 3 mô hình đơn nếu muốn
3. **Xem kết quả** – biểu đồ, so sánh, bảng theo giờ, đánh giá QCVN
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
        Ứng dụng dự báo WeatherNext đa mô hình. Bảo lưu mọi quyền.
    </div>
</div>
""", unsafe_allow_html=True)