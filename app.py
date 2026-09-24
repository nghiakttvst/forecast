"""
Đài KTTV TP. Cần Thơ — Ứng dụng dự báo đa mô hình
"""

import io
import base64
import uuid
import time as _time
from datetime import datetime, timezone, timedelta

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from config import (
    MODELS, VARIABLE_INFO, DEFAULT_VARIABLES, ALERT_THRESHOLDS,
    ALERT_PROB_THRESHOLD, DETERMINISTIC_MODELS, MAIN_MODELS,
    BULLETIN_CATEGORIES,
)
ALL_MODELS = {**MODELS, **DETERMINISTIC_MODELS}

from weather_api import (
    geocode_address, fetch_all_models, build_ensemble_dict,
    clear_api_cache, get_model_age_hours, get_model_run_time,
    get_next_run_time, format_run_time,
)
from analysis import (
    compute_ensemble_stats, compute_median_ensemble,
    summarize_temperature, summarize_precipitation,
    classify_weather_phenomenon, classify_rain_24h,
)
from qcvn import (
    evaluate_forecast_qcvn, summarize_qcvn_evaluation, grade_forecast_qcvn,
)
from storage import (
    save_forecast, save_evaluation, load_evaluations,
    save_favorite, load_favorites, delete_favorite,
    list_bulletins, get_bulletin,
)
from analytics import log_visit, get_stats
from admin import render_admin_panel


BAR_MAX_MODELS = 3
AUTO_REFRESH_MIN = 60
ADMIN_PASSWORD = "kttv2026"
_VN_TZ = timezone(timedelta(hours=7))


def _pct_to_color(pct: float) -> str:
    if pct <= 0:
        return "#e0e0e0"
    pct = max(0.0, min(100.0, float(pct)))
    anchors = [
        (0,   ( 76, 175,  80)), (25,  (139, 195,  74)),
        (50,  (255, 193,   7)), (75,  (255,  87,  34)),
        (90,  (244,  67,  54)), (100, (156,  39, 176)),
    ]
    for i in range(len(anchors) - 1):
        p1, c1 = anchors[i]
        p2, c2 = anchors[i + 1]
        if p1 <= pct <= p2:
            t = (pct - p1) / (p2 - p1) if p2 > p1 else 0
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            return f"rgb({r}, {g}, {b})"
    return "rgb(156, 39, 176)"


def _render_hourly_table(df: pd.DataFrame):
    rows_html = ""
    for _, r in df.iterrows():
        pct = int(round(float(r["rain_prob_pct"])))
        temp_v = float(r["temp"])
        rain_v = float(r["rain"])
        if pct > 0:
            color = _pct_to_color(pct)
            bar_html = (
                '<div style="display:flex; align-items:center; gap:8px;">'
                '<div style="flex:1; background:#f0f0f0; border-radius:4px; '
                'height:18px; overflow:hidden; min-width:80px;">'
                f'<div style="width:{pct}%; height:100%; '
                f'background:{color};"></div></div>'
                f'<span style="min-width:42px; text-align:right; '
                f'font-weight:700; color:{color}; font-size:0.85rem;">'
                f'{pct}%</span></div>')
        else:
            bar_html = ('<span style="color:#c0c0c0; font-size:0.85rem;">'
                        '—</span>')
        rows_html += (
            '<tr>'
            f'<td style="padding:6px 10px; border-bottom:1px solid #e8f4f8; '
            f'font-size:0.85rem; white-space:nowrap;">{r["time_str"]}</td>'
            f'<td style="padding:6px 10px; border-bottom:1px solid #e8f4f8; '
            f'font-size:0.85rem; white-space:nowrap;">{r["phenomenon"]}</td>'
            f'<td style="padding:6px 10px; border-bottom:1px solid #e8f4f8; '
            f'font-size:0.85rem; text-align:right; font-weight:600; '
            f'color:#d32f2f;">{temp_v:.1f}</td>'
            f'<td style="padding:6px 10px; border-bottom:1px solid #e8f4f8; '
            f'font-size:0.85rem; text-align:right; font-weight:600; '
            f'color:#0288d1;">{rain_v:.2f}</td>'
            f'<td style="padding:6px 10px; border-bottom:1px solid #e8f4f8;">'
            f'{bar_html}</td></tr>')
    html = (
        '<div style="max-height:620px; overflow-y:auto; '
        'border:1px solid #d0e4f0; border-radius:10px; '
        'box-shadow:0 2px 8px rgba(74,159,224,0.08);">'
        '<table style="width:100%; border-collapse:collapse; '
        "font-family:'Be Vietnam Pro', sans-serif;\">"
        '<thead style="position:sticky; top:0; z-index:10; '
        'background:linear-gradient(135deg, #4a9fe0 0%, #6dc8c2 100%); '
        'color:#ffffff;"><tr>'
        '<th style="padding:10px; text-align:left; font-size:0.82rem; '
        'font-weight:700; text-transform:uppercase;">Ngày/Giờ</th>'
        '<th style="padding:10px; text-align:left; font-size:0.82rem; '
        'font-weight:700; text-transform:uppercase;">Hiện tượng</th>'
        '<th style="padding:10px; text-align:right; font-size:0.82rem; '
        'font-weight:700; text-transform:uppercase;">Nhiệt độ (°C)</th>'
        '<th style="padding:10px; text-align:right; font-size:0.82rem; '
        'font-weight:700; text-transform:uppercase;">Mưa 1h (mm)</th>'
        '<th style="padding:10px; text-align:left; font-size:0.82rem; '
        'font-weight:700; text-transform:uppercase; min-width:180px;">'
        'Xác suất mưa</th>'
        '</tr></thead>'
        f'<tbody>{rows_html}</tbody></table></div>')
    st.markdown(html, unsafe_allow_html=True)


st.set_page_config(
    page_title="Đài KTTV TP. Cần Thơ",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');

    html, body, .stApp, .stMarkdown, h1, h2, h3, h4, h5, h6,
    p, span:not([class*="material"]):not([data-testid*="Icon"]),
    label, input, textarea, button, select,
    div[data-testid="stMetricValue"] {
        font-family: 'Be Vietnam Pro', 'Segoe UI', system-ui, sans-serif !important;
    }
    [data-testid="stIconMaterial"], span[class*="material-symbols"], .stIcon {
        font-family: 'Material Symbols Rounded' !important;
    }
    [data-testid="stToolbar"], [data-testid="stStatusWidget"],
    [data-testid="stAppDeployButton"], [data-testid="stManageAppButton"],
    [data-testid="stAppToolbar"], [data-testid="stDecoration"],
    [class*="viewerBadge"], [class*="ManageApp"],
    header[data-testid="stHeader"], button[kind="header"] {
        display: none !important; visibility: hidden !important;
        height: 0 !important;
    }
    iframe[src*="streamlit.io"] { display: none !important; }
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    section[data-testid="stSidebar"] {
        transform: translateX(0) !important; margin-left: 0 !important;
        min-width: 300px !important; width: 300px !important;
    }
    .stApp {
        background: linear-gradient(180deg, #eaf4fb 0%, #f4faff 45%, #fffaf0 100%);
        background-attachment: fixed;
    }
    .block-container { padding: 1rem 1rem 5rem !important; }
    .header-banner {
        background: linear-gradient(120deg, #4a9fe0 0%, #5cb8d9 50%, #6dc8c2 100%);
        border-radius: 18px; padding: 20px 28px;
        box-shadow: 0 4px 14px rgba(74,159,224,0.22);
        text-align: center; color: white;
    }
    .header-banner .h1 {
        font-size: 1.0rem; font-weight: 600; letter-spacing: 3px;
        text-transform: uppercase; color: rgba(255,255,255,0.92);
        margin: 0 0 4px 0;
    }
    .header-banner .h2 {
        font-size: 1.7rem; font-weight: 800; letter-spacing: 1.2px;
        text-transform: uppercase; color: #fff; margin: 0;
        text-shadow: 0 2px 4px rgba(0,60,100,0.25);
    }
    h1 { font-size: 1.5rem !important; color: #0e4a7b !important; }
    h2, h3 { color: #145a92 !important; }
    .stButton > button { border-radius: 10px; transition: all 0.25s ease; }
    .stButton > button:hover { transform: translateY(-1px); }

    .zone-card-link {
        text-decoration: none !important;
        color: inherit !important;
        display: block !important;
        height: 100% !important;
        transition: all 0.3s ease !important;
    }
    .zone-card-link:hover {
        text-decoration: none !important;
        color: inherit !important;
        transform: translateY(-6px) !important;
    }
    .zone-card {
        border-radius: 18px; padding: 24px 20px;
        min-height: 280px; text-align: center;
        transition: all 0.3s ease;
        box-shadow: 0 6px 20px rgba(0,60,120,0.10);
        border: 3px solid transparent;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
    }
    .zone-kttv     { background: linear-gradient(150deg, #e3f2fd 0%, #bbdefb 100%); }
    .zone-thuyvan  { background: linear-gradient(150deg, #e0f7fa 0%, #b2ebf2 100%); }
    .zone-mangluoi { background: linear-gradient(150deg, #f1f8e9 0%, #dcedc8 100%); }
    .zone-icon { font-size: 5rem; line-height: 1; margin-bottom: 12px; }
    .zone-title {
        font-size: 1.3rem; font-weight: 800; color: #0e4a7b;
        margin: 8px 0 6px 0; text-transform: uppercase; letter-spacing: 1px;
    }
    .zone-desc { font-size: 0.9rem; color: #455a64; line-height: 1.5; }
    .zone-card-link:hover .zone-card {
        box-shadow: 0 12px 30px rgba(0,60,120,0.20);
        border-color: #4a9fe0;
    }
    .visit-widget {
        position: fixed; bottom: 12px; right: 12px;
        background: linear-gradient(135deg, #4a9fe0 0%, #6dc8c2 100%);
        color: #fff; padding: 8px 16px; border-radius: 22px;
        font-size: 0.78rem; font-weight: 500;
        box-shadow: 0 4px 14px rgba(74,159,224,0.35);
        z-index: 9998; display: flex; gap: 10px; align-items: center;
    }
    .visit-widget .vw-num { font-weight: 800; font-size: 0.85rem; }
    .visit-widget .vw-sep { opacity: 0.5; }
    .visit-widget .vw-dot {
        width: 6px; height: 6px; border-radius: 50%;
        background: #7dff8a; box-shadow: 0 0 8px #7dff8a;
        display: inline-block; margin-right: 2px;
    }
    .bulletin-item {
        background: #ffffff; border-radius: 12px;
        padding: 14px 20px; margin-bottom: 10px;
        border-left: 5px solid #4a9fe0;
        box-shadow: 0 2px 8px rgba(74,159,224,0.08);
    }
    .bulletin-item:hover {
        box-shadow: 0 6px 18px rgba(74,159,224,0.20);
        border-left-color: #ea4335;
    }
    .bulletin-title { font-size: 1rem; font-weight: 700;
                      color: #0e4a7b; margin: 0 0 4px 0; }
    .bulletin-meta { font-size: 0.82rem; color: #6d8a99; }
    .footer {
        margin-top: 40px; padding: 20px 24px;
        background: linear-gradient(90deg,
            rgba(74,159,224,0.08), rgba(109,200,194,0.10));
        border-top: 2px solid rgba(74,159,224,0.28);
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
    .footer-copyright { margin-top: 12px; font-size: 0.8rem; color: #6d8a99; }
</style>
""", unsafe_allow_html=True)


components.html("""
<script>
(function() {
    var doc;
    try { doc = window.parent.document; } catch(e) { return; }

    var SELECTORS = [
        '[data-testid="stStatusWidget"]',
        '[data-testid="stAppDeployButton"]',
        '[data-testid="stManageAppButton"]',
        '[data-testid="stToolbar"]',
        '[data-testid="stHeader"]',
        '[class*="viewerBadge"]',
        '[class*="ManageApp"]'
    ];

    function run() {
        SELECTORS.forEach(function(s) {
            try {
                doc.querySelectorAll(s).forEach(function(el) {
                    el.style.display = 'none';
                });
            } catch(e) {}
        });
        try {
            var top = doc.querySelector('.st-key-kttv_top');
            var sub = doc.querySelector('.st-key-kttv_submenu');
            if (top) {
                top.style.position = 'sticky';
                top.style.top = '0';
                top.style.zIndex = '1000';
                top.style.background = '#eaf4fb';
                top.style.padding = '12px 0 8px 0';
                top.style.borderBottom = '1px solid rgba(74,159,224,0.15)';
            }
            if (sub) {
                sub.style.position = 'sticky';
                sub.style.top = '68px';
                sub.style.zIndex = '999';
                sub.style.background = '#eaf4fb';
                sub.style.padding = '8px 0 12px 0';
                sub.style.borderBottom = '2px solid rgba(74,159,224,0.28)';
            }
        } catch(e) {}
    }

    run();
    setTimeout(run, 500);
})();
</script>
""", height=0, width=0)
_defaults = {
    "session_id": str(uuid.uuid4()),
    "page": "home",
    "kttv_tab": "forecast",
    "pending_run": False,
    "has_results": False,
    "saved_lat": None, "saved_lon": None, "saved_full_name": None,
    "saved_raw_models": None, "saved_days": None,
    "saved_model_keys": None, "saved_address": "",
    "show_admin": False, "admin_authed": False,
    "visit_logged": False,
    "last_fetch_ts": None, "last_fetch_str": None,
    "force_refresh": False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


try:
    qp_page = st.query_params.get("page", None)
    qp_tab = st.query_params.get("tab", None)
    if qp_page and qp_page != st.session_state.get("page"):
        st.session_state["page"] = qp_page
    if qp_tab and qp_tab != st.session_state.get("kttv_tab"):
        st.session_state["kttv_tab"] = qp_tab
except Exception as e:
    print(f"[QP] {e}")


def filter_ensemble_from_run(ens_dict: dict) -> dict:
    out = {}
    for mk, df in ens_dict.items():
        if df is None or df.empty:
            out[mk] = df
            continue
        try:
            run_utc = get_model_run_time(mk)
            run_vn = run_utc.astimezone(_VN_TZ).replace(tzinfo=None)
            if not isinstance(df.index, pd.DatetimeIndex):
                out[mk] = df
                continue
            filt = df[df.index >= run_vn]
            out[mk] = filt if not filt.empty else df
        except Exception:
            out[mk] = df
    return out


if not st.session_state.get("visit_logged"):
    try:
        log_visit(session_id=st.session_state["session_id"],
                  user_id=None, username="guest",
                  page="main", action="view")
    except Exception as e:
        print(f"[VISIT] {e}")
    st.session_state["visit_logged"] = True


try:
    _stats = get_stats()
    st.markdown(f"""
<div class="visit-widget">
    <span><span class="vw-dot"></span>
    <span class="vw-num">{_stats['views_today']:,}</span> hôm nay</span>
    <span class="vw-sep">·</span>
    <span>👤 <span class="vw-num">{_stats['unique_today']:,}</span> khách</span>
    <span class="vw-sep">·</span>
    <span>📊 <span class="vw-num">{_stats['total_views']:,}</span> tổng</span>
</div>
""", unsafe_allow_html=True)
except Exception as e:
    print(f"[WIDGET] {e}")


def navigate(page: str, tab: str = None):
    st.session_state["page"] = page
    if tab:
        st.session_state["kttv_tab"] = tab
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.rerun()


def render_home():
    st.markdown("""
<div class="header-banner">
    <div class="h1">🌊 ĐÀI KHÍ TƯỢNG THỦY VĂN NAM BỘ 🌦️</div>
    <div class="h2">ĐÀI KHÍ TƯỢNG THỦY VĂN THÀNH PHỐ CẦN THƠ</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="large")

    with c1:
        st.markdown("""
<a href="?page=kttv&tab=forecast" target="_self" class="zone-card-link">
    <div class="zone-card zone-kttv">
        <div class="zone-icon">🌦️</div>
        <div class="zone-title">Dự báo Khí tượng</div>
        <div class="zone-desc">
            Dự báo số trị đa mô hình · Bản tin hàng ngày ·
            Cảnh báo mưa dông · Mưa lớn
        </div>
    </div>
</a>
""", unsafe_allow_html=True)

    with c2:
        st.markdown("""
<a href="?page=thuyvan" target="_self" class="zone-card-link">
    <div class="zone-card zone-thuyvan">
        <div class="zone-icon">🌊</div>
        <div class="zone-title">Dự báo Thủy văn</div>
        <div class="zone-desc">
            Mực nước sông · Cảnh báo ngập lụt ·
            Triều cường · Dự báo nguồn nước
        </div>
    </div>
</a>
""", unsafe_allow_html=True)

    with c3:
        st.markdown("""
<a href="?page=network" target="_self" class="zone-card-link">
    <div class="zone-card zone-mangluoi">
        <div class="zone-icon">🗺️</div>
        <div class="zone-title">Mạng lưới & Dữ liệu</div>
        <div class="zone-desc">
            Bản đồ trạm KTTV · Dữ liệu quan trắc ·
            Lịch sử khí tượng thủy văn
        </div>
    </div>
</a>
""", unsafe_allow_html=True)
        def render_kttv():
    with st.container(key="kttv_top"):
        col_back, col_title = st.columns([1, 4], gap="medium")

        with col_back:
            st.markdown("""
<a href="?page=home" target="_self"
   style="display:block; padding:10px 16px; text-align:center;
          background:#ffffff; border:1px solid #d0e4f0;
          border-radius:10px; text-decoration:none;
          color:#0e4a7b; font-weight:700; font-size:0.9rem;
          box-shadow:0 2px 6px rgba(74,159,224,0.10);">
    🏠 Trang chủ
</a>
""", unsafe_allow_html=True)

        with col_title:
            st.markdown("""
<div style='display:flex; align-items:center; padding-left:12px;
            height:42px;'>
    <span style='font-size:1.5rem; margin-right:10px;'>🌦️</span>
    <span style='font-size:1.35rem; font-weight:800;
                 color:#0e4a7b; letter-spacing:0.5px;'>
        Dự báo Khí tượng
    </span>
</div>
""", unsafe_allow_html=True)

    with st.container(key="kttv_submenu"):
        active_tab = st.session_state.get("kttv_tab", "forecast")
        tabs = [
            ("forecast",   "📊 Dự báo số trị"),
            ("daily",      "📰 Bản tin hàng ngày"),
            ("rain_storm", "⛈️ Bản tin mưa dông"),
            ("heavy_rain", "🌧️ Bản tin mưa lớn"),
        ]

        cols = st.columns(4)
        for i, (key, label) in enumerate(tabs):
            with cols[i]:
                is_active = (key == active_tab)
                bg = "#ff4b4b" if is_active else "#ffffff"
                color = "#ffffff" if is_active else "#0e4a7b"
                border = "#ff4b4b" if is_active else "#d0e4f0"
                st.markdown(f"""
<a href="?page=kttv&tab={key}" target="_self"
   style="display:block; padding:12px 8px; text-align:center;
          background:{bg}; color:{color}; border:2px solid {border};
          border-radius:10px; text-decoration:none;
          font-weight:700; font-size:0.85rem;
          box-shadow:0 2px 6px rgba(74,159,224,0.08);">
    {label}
</a>
""", unsafe_allow_html=True)

    tab = st.session_state.get("kttv_tab", "forecast")

    if tab == "forecast":
        render_forecast_page()
    elif tab in ("daily", "rain_storm", "heavy_rain"):
        render_bulletins_page(tab)


def render_bulletins_page(category: str):
    cat_info = BULLETIN_CATEGORIES.get(category, {})
    icon = cat_info.get("icon", "📄")
    label = cat_info.get("label", category)

    st.subheader(f"{icon} {label}")
    bulletins = list_bulletins(category=category, limit=50)

    if not bulletins:
        st.markdown("""
<div style='text-align:center; padding:60px 20px; color:#6d8a99;
            font-size:1.05rem;'>
    📭 Chưa có bản tin nào.
</div>
""", unsafe_allow_html=True)
        return

    viewing_key = f"viewing_bulletin_{category}"
    viewing_id = st.session_state.get(viewing_key)

    st.markdown(
        f"<div style='font-size:0.9rem; color:#6d8a99; margin-bottom:10px;'>"
        f"📚 <b>{len(bulletins)} bản tin</b> — mới nhất ở trên cùng</div>",
        unsafe_allow_html=True)

    for b in bulletins:
        bid = b["id"]
        size_kb = (b.get("file_size") or 0) / 1024
        created = (b.get("created_at") or "")[:16].replace("T", " ")

        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"<div class='bulletin-item'>"
                f"<div class='bulletin-title'>{icon} {b['title']}</div>"
                f"<div class='bulletin-meta'>"
                f"📅 {created} &nbsp;·&nbsp; "
                f"📎 {b['filename']} ({size_kb:.0f} KB)"
                f"{' &nbsp;·&nbsp; ' + b['description'] if b.get('description') else ''}"
                f"</div></div>",
                unsafe_allow_html=True)

        with col_btn:
            is_viewing = (viewing_id == bid)
            btn_label = "✖ Đóng" if is_viewing else "👁 Xem"
            btn_type = "primary" if is_viewing else "secondary"
            if st.button(btn_label, key=f"view_bul_{bid}",
                         width='stretch', type=btn_type):
                if is_viewing:
                    st.session_state[viewing_key] = None
                else:
                    st.session_state[viewing_key] = bid
                st.rerun()

        if is_viewing:
            bulletin = get_bulletin(bid)
            if not bulletin:
                st.error("Không tìm thấy bản tin.")
            else:
                try:
                    pdf_bytes = base64.b64decode(bulletin["file_data"])
                    st.download_button(
                        "📥 Tải bản tin (PDF)",
                        data=pdf_bytes,
                        file_name=bulletin["filename"],
                        mime="application/pdf",
                        width='stretch',
                        key=f"dl_bul_{bid}")
                    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,'
                        f'{pdf_b64}" width="100%" height="800px" '
                        'style="border:1px solid #d0e4f0; '
                        'border-radius:10px;"></iframe>',
                        unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Lỗi hiển thị PDF: {e}")


def render_placeholder(title: str, icon: str, message: str):
    st.markdown(f"""
<div class="header-banner">
    <div class="h1">{icon} {title}</div>
</div>
""", unsafe_allow_html=True)

    cback, _ = st.columns([1, 5])
    with cback:
        st.markdown("""
<a href="?page=home" target="_self"
   style="display:block; padding:10px 16px; text-align:center;
          background:#ffffff; border:1px solid #d0e4f0;
          border-radius:10px; text-decoration:none;
          color:#0e4a7b; font-weight:700; font-size:0.9rem;">
    🏠 Trang chủ
</a>
""", unsafe_allow_html=True)

    st.info(f"🚧 {message}")
    st.markdown("""
    <div style='text-align:center; padding:40px; color:#78909c;'>
        <h3>🚧 Đang xây dựng</h3>
        <p>Chức năng này sẽ được cập nhật trong phiên bản tiếp theo.</p>
    </div>
    """, unsafe_allow_html=True)
    def render_forecast_page():
    st.markdown("### 📊 Dự báo số trị đa mô hình")
    st.caption("Chọn địa điểm, mô hình, số ngày → xem dự báo từ 5 mô hình "
               "ensemble + tổ hợp **trung vị (median ensemble)**.")


def render_forecast_sidebar():
    with st.sidebar:
        st.markdown("---")
        st.header("📍 Vị trí")
        input_mode = st.radio("Cách nhập:", ["Địa chỉ", "Tọa độ"],
                              key="input_mode")

        address = None
        lat_input, lon_input = None, None

        if input_mode == "Địa chỉ":
            def _on_submit():
                st.session_state["pending_run"] = True

            address = st.text_input(
                "Nhập địa chỉ (nhấn Enter):",
                value=st.session_state.get("address_input",
                                            "Ninh Kiều, Cần Thơ"),
                key="address_input", on_change=_on_submit)
        else:
            cc1, cc2 = st.columns(2)
            with cc1:
                lat_input = st.number_input("Vĩ độ:", value=10.0291,
                                            format="%.4f", key="lat_input")
            with cc2:
                lon_input = st.number_input("Kinh độ:", value=105.7706,
                                            format="%.4f", key="lon_input")

        st.header("⚙️ Tùy chọn")

        def _fmt_model(k):
            info = ALL_MODELS[k]
            tag = "ensemble" if info.get("ensemble") else "đơn"
            return f"{info['label']} [{tag}·{info['members']}m]"

        model_keys = st.multiselect(
            "Mô hình:", options=list(ALL_MODELS.keys()),
            default=list(MODELS.keys()), format_func=_fmt_model,
            key="model_select")

        days = st.slider("Số ngày:", 1, 15, 10, key="days_slider")

        st.header("📊 Đánh giá QCVN")
        enable_qcvn = st.checkbox("Bật QCVN", value=True, key="enable_qcvn")

        st.divider()
        run_btn = st.button("🚀 Lấy dự báo", type="primary",
                            width='stretch', key="run_btn")

        st.divider()
        with st.expander("🛡️ Quản trị viên", expanded=False):
            if not st.session_state.get("admin_authed"):
                pwd = st.text_input("Mật khẩu:", type="password",
                                    key="admin_pwd_input")
                if st.button("🔓 Đăng nhập", key="admin_login_btn",
                             width='stretch'):
                    if pwd == ADMIN_PASSWORD:
                        st.session_state["admin_authed"] = True
                        st.rerun()
                    else:
                        st.error("Sai mật khẩu.")
            else:
                st.success("✅ Đã xác thực")
                if st.button("📊 Mở Admin", key="admin_open_btn",
                             width='stretch'):
                    st.session_state["show_admin"] = True
                    st.rerun()
                if st.button("🚪 Đăng xuất", key="admin_logout_btn",
                             width='stretch'):
                    st.session_state["admin_authed"] = False
                    st.session_state["show_admin"] = False
                    st.rerun()

    return (input_mode, address, lat_input, lon_input,
            model_keys, days, enable_qcvn, run_btn)


def handle_forecast_run(input_mode, address, lat_input, lon_input,
                        model_keys, days, enable_qcvn, run_btn):
    # Lazy import plotly
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    trigger_run = run_btn or st.session_state.get("pending_run")

    if trigger_run:
        st.session_state["pending_run"] = False
        lat, lon, full_name = None, None, None
        force = st.session_state.pop("force_refresh", False)

        if input_mode == "Địa chỉ":
            with st.spinner("🔍 Đang tra cứu địa chỉ…"):
                geo = geocode_address(address)
            if not geo:
                st.error(f"❌ Không tìm thấy: **{address}**")
                st.stop()
            lat, lon, full_name = geo
        else:
            lat, lon = lat_input, lon_input
            full_name = f"({lat:.4f}, {lon:.4f})"

        if not model_keys:
            st.warning("Chọn ít nhất 1 mô hình.")
            st.stop()

        if force:
            clear_api_cache()

        with st.spinner(f"☁️ Đang tải {len(model_keys)} mô hình…"):
            raw_models = fetch_all_models(
                lat, lon, variables=DEFAULT_VARIABLES,
                days=days, model_keys=model_keys, force_refresh=force)

        if not raw_models:
            st.error("❌ Không lấy được dữ liệu.")
            st.stop()

        _t = build_ensemble_dict(raw_models, "temperature_2m")
        _p = build_ensemble_dict(raw_models, "precipitation")
        if not _t and not _p:
            st.error("❌ Không parse được dữ liệu.")
            st.stop()

        st.session_state.update({
            "has_results": True,
            "saved_lat": lat, "saved_lon": lon,
            "saved_full_name": full_name,
            "saved_raw_models": raw_models,
            "saved_days": days,
            "saved_model_keys": list(model_keys),
            "saved_address": address if address else "",
            "last_fetch_ts": _time.time(),
            "last_fetch_str": datetime.now(_VN_TZ).strftime("%d/%m/%Y %H:%M:%S"),
        })

    if not st.session_state.get("has_results"):
        st.info("👈 Nhập địa chỉ hoặc tọa độ ở sidebar rồi nhấn "
                "**🚀 Lấy dự báo** để bắt đầu.")
        return

    lat = st.session_state["saved_lat"]
    lon = st.session_state["saved_lon"]
    full_name = st.session_state["saved_full_name"]
    raw_models = st.session_state["saved_raw_models"]
    days = st.session_state["saved_days"]
    model_keys = st.session_state["saved_model_keys"]
    address = st.session_state.get("saved_address", "")

    temp_ensembles = build_ensemble_dict(raw_models, "temperature_2m")
    precip_ensembles = build_ensemble_dict(raw_models, "precipitation")
    temp_ensembles = filter_ensemble_from_run(temp_ensembles)
    precip_ensembles = filter_ensemble_from_run(precip_ensembles)

    st.success(f"📍 {full_name} – ({lat:.4f}, {lon:.4f})")
    st.caption(f"🕐 Lần tải cuối: "
               f"**{st.session_state.get('last_fetch_str','—')}** (giờ VN) · "
               f"📊 {len(model_keys)} mô hình")

    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("🔄 Làm mới", width='stretch', key="btn_refresh"):
            st.session_state["force_refresh"] = True
            st.session_state["pending_run"] = True
            st.rerun()

    current_favs = load_favorites()
    already = any(f["display"] == full_name for f in current_favs)
    if not already:
        if st.button("⭐ Ghim vị trí này", key="pin_btn"):
            try:
                save_favorite(address or full_name, full_name, lat, lon)
                st.success("⭐ Đã ghim!")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi: {e}")

    with st.expander("🛰️ Trạng thái real-time các mô hình", expanded=False):
        for mk in model_keys:
            info = ALL_MODELS[mk]
            age_h = get_model_age_hours(mk)
            run_str = format_run_time(mk)
            next_vn = get_next_run_time(mk).astimezone(_VN_TZ)
            freq = info.get("update_freq_hours", 12)
            badge = "🟢" if age_h < freq else ("🟡" if age_h < freq*2 else "🔴")
            st.markdown(
                f"<div style='padding:5px 10px; "
                f"border-bottom:1px solid #e8f4f8; display:flex; "
                f"font-size:0.85rem;'>"
                f"<div style='flex:2; font-weight:600; color:#0e4a7b;'>"
                f"{badge} {info['label']}</div>"
                f"<div style='flex:2; color:#354a5c;'>{run_str}</div>"
                f"<div style='flex:1; text-align:right; color:#1976d2;'>"
                f"Tiếp: {next_vn.strftime('%H:%M')} VN</div></div>",
                unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Biểu đồ dự báo", "📊 So sánh mô hình",
        "🕐 Theo giờ", "✅ Đánh giá QCVN", "💾 Lịch sử"])

    with tab1:
        st.subheader("📈 Dự báo nhiệt độ và mưa")

        has_median = False
        median_temp = None
        median_precip = None
        try:
            if len(temp_ensembles) >= 2:
                _mt = compute_median_ensemble(temp_ensembles)
                if (_mt is not None and not _mt.empty
                        and "median" in _mt.columns):
                    median_temp = _mt
                    has_median = True
            if len(precip_ensembles) >= 2:
                _mp = compute_median_ensemble(precip_ensembles)
                if (_mp is not None and not _mp.empty
                        and "median" in _mp.columns):
                    median_precip = _mp
        except Exception as e:
            print(f"[MEDIAN] Lỗi: {e}")

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=(
                "<b style='font-size:15px; color:#0e4a7b;'>"
                "🌡️ Nhiệt độ 2m (°C)</b>",
                "<b style='font-size:15px; color:#0e4a7b;'>"
                "💧 Mưa 1h (mm)</b>"),
            vertical_spacing=0.20)

        for mk, ens_df in temp_ensembles.items():
            try:
                stats = compute_ensemble_stats(ens_df)
                if stats.empty or "mean" not in stats.columns:
                    continue
                color = ALL_MODELS[mk]["color"]
                label = ALL_MODELS[mk]["label"]
                rgb = tuple(int(color.lstrip("#")[i:i+2], 16)
                            for i in (0, 2, 4))
                fig.add_trace(go.Scatter(
                    x=stats.index, y=stats["p90"], mode="lines",
                    line=dict(width=0), showlegend=False, hoverinfo="skip"),
                    row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=stats.index, y=stats["p10"], mode="lines",
                    line=dict(width=0), fill="tonexty",
                    fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)",
                    name=f"{label} (10–90%)"), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=stats.index, y=stats["mean"], mode="lines",
                    line=dict(color=color, width=2),
                    name=f"{label} (TB)"), row=1, col=1)
            except Exception as e:
                print(f"[TEMP] {e}")

        if has_median and median_temp is not None and not median_temp.empty:
            try:
                _y = pd.to_numeric(median_temp["median"], errors="coerce")
                _mask = _y.notna()
                if _mask.any():
                    fig.add_trace(go.Scatter(
                        x=median_temp.index[_mask], y=_y[_mask], mode="lines",
                        line=dict(color="#000000", width=3, dash="dash"),
                        name="🌟 Trung vị tổ hợp (5 mô hình)"), row=1, col=1)
            except Exception as e:
                print(f"[MEDIAN-TEMP] {e}")

        n_p = len(precip_ensembles)
        use_bars = n_p <= BAR_MAX_MODELS
        for mk, ens_df in precip_ensembles.items():
            try:
                stats = compute_ensemble_stats(ens_df)
                if stats.empty or "mean" not in stats.columns:
                    continue
                color = ALL_MODELS[mk]["color"]
                if use_bars:
                    upper = (stats["p90"] - stats["mean"]).clip(lower=0)
                    lower = (stats["mean"] - stats["p10"]).clip(lower=0)
                    fig.add_trace(go.Bar(
                        x=stats.index, y=stats["mean"],
                        marker=dict(color=color),
                        error_y=dict(type="data", symmetric=False,
                                     array=upper, arrayminus=lower,
                                     color=color, thickness=1.2, width=0),
                        showlegend=False), row=2, col=1)
                else:
                    fig.add_trace(go.Scatter(
                        x=stats.index, y=stats["mean"], mode="lines",
                        line=dict(color=color, width=2),
                        showlegend=False), row=2, col=1)
            except Exception as e:
                print(f"[PRECIP] {e}")

        if has_median and median_precip is not None and not median_precip.empty:
            try:
                _y = pd.to_numeric(median_precip["median"], errors="coerce")
                _mask = _y.notna()
                if _mask.any():
                    if use_bars:
                        fig.add_trace(go.Bar(
                            x=median_precip.index[_mask], y=_y[_mask],
                            marker=dict(color="#000000", opacity=0.7),
                            name="🌟 Trung vị tổ hợp",
                            showlegend=False), row=2, col=1)
                    else:
                        fig.add_trace(go.Scatter(
                            x=median_precip.index[_mask], y=_y[_mask],
                            mode="lines",
                            line=dict(color="#000000", width=3, dash="dash"),
                            name="🌟 Trung vị tổ hợp"), row=2, col=1)
            except Exception as e:
                print(f"[MEDIAN-PRECIP] {e}")

        fig.update_layout(
            height=820, hovermode="x unified",
            barmode="group", bargap=0.15, bargroupgap=0.05,
            legend=dict(orientation="h", yanchor="bottom", y=1.15,
                        xanchor="center", x=0.5,
                        bgcolor="rgba(255,255,255,0.92)",
                        bordercolor="#d0e4f0", borderwidth=1,
                        font=dict(size=11)),
            margin=dict(l=50, r=30, t=150, b=50))
        for ann in fig.layout.annotations:
            if ann.text and ("Nhiệt độ" in ann.text or "Mưa 1h" in ann.text):
                ann.update(yshift=15, font=dict(size=15))

        st.plotly_chart(fig, width='stretch')

        if has_median:
            st.success(
                f"🌟 **Tổ hợp trung vị (Median Ensemble)** từ "
                f"{len(temp_ensembles)} mô hình chính — đường đen nét đứt.")

        st.subheader(f"📌 Tóm tắt dự báo {days} ngày tới")
        c1, c2, c3, c4 = st.columns(4)

        if temp_ensembles:
            vals, vals_min = [], []
            for d in temp_ensembles.values():
                s = compute_ensemble_stats(d)
                if s.empty or "mean" not in s.columns:
                    continue
                try:
                    vals.append(float(s["mean"].max()))
                    vals_min.append(float(s["mean"].min()))
                except Exception:
                    continue
            if vals:
                c1.metric("🌡️ T cao nhất", f"{max(vals):.1f} °C")
            if vals_min:
                c2.metric("❄️ T thấp nhất", f"{min(vals_min):.1f} °C")

        if precip_ensembles:
            r_tot, r_pk = [], []
            for d in precip_ensembles.values():
                s = compute_ensemble_stats(d)
                if s.empty or "mean" not in s.columns:
                    continue
                try:
                    r_tot.append(float(s["mean"].sum()))
                    r_pk.append(float(s["mean"].max()))
                except Exception:
                    continue
            if r_tot:
                c3.metric("💧 Tổng mưa (max)", f"{max(r_tot):.1f} mm")
            if r_pk:
                c4.metric("☔ Đỉnh mưa 1h", f"{max(r_pk):.1f} mm")

    with tab2:
        cv = st.radio("Chọn biến:", ["🌡️ Nhiệt độ", "💧 Lượng mưa"],
                      horizontal=True, key="compare_var_radio",
                      label_visibility="collapsed")
        st.divider()
        ens_to_use = (temp_ensembles if cv == "🌡️ Nhiệt độ"
                      else precip_ensembles)
        unit = "°C" if cv == "🌡️ Nhiệt độ" else "mm"
        if not ens_to_use:
            st.info("Không có dữ liệu.")
        else:
            fig_cmp = go.Figure()
            for mk, ens_df in ens_to_use.items():
                try:
                    stats = compute_ensemble_stats(ens_df)
                    if stats.empty or "mean" not in stats.columns:
                        continue
                    fig_cmp.add_trace(go.Scatter(
                        x=stats.index, y=stats["mean"], mode="lines",
                        line=dict(color=ALL_MODELS[mk]["color"], width=2),
                        name=ALL_MODELS[mk]["label"]))
                except Exception:
                    continue
            fig_cmp.update_layout(
                height=500, hovermode="x unified",
                xaxis_title="Thời gian", yaxis_title=unit,
                legend=dict(orientation="h", y=1.02))
            st.plotly_chart(fig_cmp, width='stretch')

    with tab3:
        st.subheader("🕐 Chi tiết theo giờ")
        if not temp_ensembles and not precip_ensembles:
            st.warning("Không có dữ liệu.")
        else:
            opts = (list(temp_ensembles.keys())
                    or list(precip_ensembles.keys()))
            selected = st.radio("Chọn mô hình:", options=opts,
                                format_func=lambda k: ALL_MODELS[k]["label"],
                                horizontal=True, key="hourly_model_radio",
                                label_visibility="collapsed")

            try:
                _run_utc = get_model_run_time(selected)
                _start_vn = _run_utc.astimezone(_VN_TZ).replace(tzinfo=None)
                _start_str = _start_vn.strftime("%d/%m/%Y %H:%M")
                start = pd.Timestamp(_start_vn)
            except Exception:
                start = pd.Timestamp(
                    datetime.now(_VN_TZ).replace(tzinfo=None)
                ).floor("h") - pd.Timedelta(hours=1)
                _start_str = start.strftime("%d/%m/%Y %H:%M")

            st.caption(f"🛰️ **{ALL_MODELS[selected]['label']}** — "
                       f"Hiển thị từ **{_start_str} VN** trở đi")

            tdf = temp_ensembles.get(selected)
            pdf = precip_ensembles.get(selected)

            if tdf is not None and not tdf.empty:
                try:
                    _tdf_num = tdf.apply(pd.to_numeric, errors="coerce")
                    _tdf_num = _tdf_num.dropna(axis=1, how="all")
                    tmean = (_tdf_num.mean(axis=1).astype(float)
                             if not _tdf_num.empty else pd.Series(dtype=float))
                except Exception:
                    tmean = pd.Series(dtype=float)
            else:
                tmean = pd.Series(dtype=float)

            if pdf is not None and not pdf.empty:
                try:
                    _pdf_num = pdf.apply(pd.to_numeric, errors="coerce")
                    _pdf_num = _pdf_num.dropna(axis=1, how="all")
                    if _pdf_num.empty:
                        pmean = pd.Series(0.0, index=tmean.index)
                        rprob = pd.Series(0.0, index=tmean.index)
                    else:
                        pmean = _pdf_num.mean(axis=1).astype(float)
                        rprob = ((_pdf_num > 0.1).sum(axis=1)
                                 / _pdf_num.notna().sum(axis=1)).astype(float)
                except Exception:
                    pmean = pd.Series(0.0, index=tmean.index)
                    rprob = pd.Series(0.0, index=tmean.index)
            else:
                pmean = pd.Series(0.0, index=tmean.index)
                rprob = pd.Series(0.0, index=tmean.index)

            df = pd.DataFrame({
                "time": tmean.index,
                "temp": pd.to_numeric(tmean.values, errors="coerce"),
                "rain": pd.to_numeric(pmean.values, errors="coerce"),
                "rain_prob": pd.to_numeric(rprob.values, errors="coerce")})
            df["rain"] = df["rain"].fillna(0.0)
            df["rain_prob"] = df["rain_prob"].fillna(0.0)
            df["temp"] = df["temp"].astype(float)
            df["rain"] = df["rain"].astype(float)
            df["rain_prob"] = df["rain_prob"].astype(float)
            df = df[df["time"] >= start].sort_values("time").reset_index(drop=True)
            df = df.dropna(subset=["temp"]).reset_index(drop=True)

            if df.empty:
                st.warning("Không có dữ liệu.")
            else:
                df["phenomenon"] = df.apply(
                    lambda r: classify_weather_phenomenon(
                        r["time"].hour, r["rain"], r["temp"]), axis=1)
                df["time_str"] = df["time"].dt.strftime("%d/%m %H:%M")

                disp = pd.DataFrame({
                    "Ngày/Giờ": df["time_str"].values,
                    "Hiện tượng": df["phenomenon"].values,
                    "Nhiệt độ (°C)": df["temp"].round(1).values,
                    "Mưa 1h (mm)": df["rain"].round(2).values,
                    "Xác suất mưa (%)": (df["rain_prob"] * 100)
                        .round(0).astype(int).values})

                st.caption(f"📊 {len(disp)} giờ")
                render_df = pd.DataFrame({
                    "time_str": df["time_str"].values,
                    "phenomenon": df["phenomenon"].values,
                    "temp": df["temp"].round(1).values,
                    "rain": df["rain"].round(2).values,
                    "rain_prob_pct": (df["rain_prob"] * 100).round(0).values})
                _render_hourly_table(render_df)

                csv_buf = io.StringIO()
                disp.to_csv(csv_buf, index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 Tải CSV",
                    data=csv_buf.getvalue().encode("utf-8-sig"),
                    file_name=f"du_bao_{selected}.csv",
                    mime="text/csv", key="dl_hourly")

    with tab4:
        st.subheader("✅ Đánh giá QCVN 84:2024/BTNMT")
        if not enable_qcvn:
            st.info("Bật QCVN ở sidebar.")
        else:
            uploaded = st.file_uploader("File quan trắc (CSV):",
                                        type=["csv"], key="obs_upload")
            if uploaded:
                try:
                    obs_df = pd.read_csv(uploaded,
                                         parse_dates=["time"]).set_index("time")
                    obs_temp = obs_precip = None
                    if "temperature" in obs_df.columns:
                        obs_temp = obs_df.assign(observed=obs_df["temperature"])
                    elif "observed" in obs_df.columns:
                        obs_temp = obs_df
                    if "precipitation" in obs_df.columns:
                        obs_precip = obs_df.assign(observed=obs_df["precipitation"])
                    elif "observed" in obs_df.columns and obs_temp is None:
                        obs_precip = obs_df

                    all_eval = []
                    for mk in model_keys:
                        if mk in temp_ensembles and obs_temp is not None:
                            try:
                                edf = evaluate_forecast_qcvn(
                                    temp_ensembles[mk], obs_temp,
                                    "temperature_2m", "temperature")
                                if not edf.empty:
                                    s = summarize_qcvn_evaluation(edf)
                                    s["model"] = ALL_MODELS[mk]["label"]
                                    s["variable"] = "Nhiệt độ"
                                    s["grade"] = grade_forecast_qcvn(s)
                                    all_eval.append(s)
                            except Exception:
                                pass
                        if mk in precip_ensembles and obs_precip is not None:
                            try:
                                edf = evaluate_forecast_qcvn(
                                    precip_ensembles[mk], obs_precip,
                                    "precipitation", "precipitation")
                                if not edf.empty:
                                    s = summarize_qcvn_evaluation(edf)
                                    s["model"] = ALL_MODELS[mk]["label"]
                                    s["variable"] = "Mưa"
                                    s["grade"] = grade_forecast_qcvn(s)
                                    all_eval.append(s)
                            except Exception:
                                pass
                    if all_eval:
                        st.dataframe(pd.DataFrame(all_eval),
                                     width='stretch', hide_index=True)
                    else:
                        st.warning("Không đủ dữ liệu.")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

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
            st.dataframe(hist, width='stretch', hide_index=True)
            page = st.session_state.get("page", "home")

if page == "kttv" and st.session_state.get("kttv_tab") == "forecast":
    sidebar_data = render_forecast_sidebar()
    if sidebar_data:
        handle_forecast_run(*sidebar_data)
elif page == "kttv":
    with st.sidebar:
        st.markdown("### 📂 Danh mục KTTV")
        st.markdown("""
<a href="?page=kttv&tab=forecast" target="_self"
   style="display:block; padding:10px; margin-bottom:6px;
          background:#ffffff; border:1px solid #d0e4f0;
          border-radius:8px; text-decoration:none;
          color:#0e4a7b; font-weight:600; font-size:0.85rem;">
    📊 Dự báo số trị
</a>
<a href="?page=kttv&tab=daily" target="_self"
   style="display:block; padding:10px; margin-bottom:6px;
          background:#ffffff; border:1px solid #d0e4f0;
          border-radius:8px; text-decoration:none;
          color:#0e4a7b; font-weight:600; font-size:0.85rem;">
    📰 Bản tin hàng ngày
</a>
<a href="?page=kttv&tab=rain_storm" target="_self"
   style="display:block; padding:10px; margin-bottom:6px;
          background:#ffffff; border:1px solid #d0e4f0;
          border-radius:8px; text-decoration:none;
          color:#0e4a7b; font-weight:600; font-size:0.85rem;">
    ⛈️ Bản tin mưa dông
</a>
<a href="?page=kttv&tab=heavy_rain" target="_self"
   style="display:block; padding:10px; margin-bottom:6px;
          background:#ffffff; border:1px solid #d0e4f0;
          border-radius:8px; text-decoration:none;
          color:#0e4a7b; font-weight:600; font-size:0.85rem;">
    🌧️ Bản tin mưa lớn
</a>
<a href="?page=home" target="_self"
   style="display:block; padding:10px; margin-top:12px;
          background:#e3f2fd; border:1px solid #4a9fe0;
          border-radius:8px; text-decoration:none;
          color:#0e4a7b; font-weight:700; font-size:0.85rem;
          text-align:center;">
    🏠 Trang chủ
</a>
""", unsafe_allow_html=True)


if (st.session_state.get("show_admin")
        and st.session_state.get("admin_authed")):
    fake_admin = {"username": "admin", "full_name": "Quản trị viên",
                  "role": "admin", "id": 0}
    render_admin_panel(fake_admin)
    st.markdown("---")
    if st.button("← Quay lại", key="adm_back"):
        st.session_state["show_admin"] = False
        st.rerun()
    st.stop()


if page == "home":
    render_home()
elif page == "kttv":
    render_kttv()
elif page == "thuyvan":
    render_placeholder(
        "Dự báo Thủy văn", "🌊",
        "Chức năng dự báo thủy văn đang được xây dựng.")
elif page == "network":
    render_placeholder(
        "Mạng lưới & Dữ liệu KTTV", "🗺️",
        "Chức năng bản đồ mạng lưới trạm đang được xây dựng.")
else:
    render_home()


st.markdown("""
<div class="footer">
    <div class="footer-line">
        <span>🏠</span>
        <span><strong>Địa chỉ:</strong>
        Số 45 Đường 3/2, Phường Ninh Kiều, Thành phố Cần Thơ</span>
    </div>
    <div class="footer-line">
        <span>👨‍💻</span>
        <span><strong>Phát triển:</strong>
        Power by <strong>Nguyễn Trọng Nghĩa</strong> &#8211; IT</span>
    </div>
    <div class="footer-line">
        <span>📞</span>
        <span><strong>Điện thoại:</strong>
        <a href="tel:0974749863">0974 749 863</a></span>
    </div>
    <div class="footer-copyright">
        &#169; 2026 Đài Khí tượng Thủy văn TP. Cần Thơ
    </div>
</div>
""", unsafe_allow_html=True)