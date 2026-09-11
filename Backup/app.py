"""
Ung dung web: Du bao thoi tiet WeatherNext da mo hinh + QCVN 84:2024/BTNMT.
Chay: streamlit run app.py
"""

import io
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from config import (
    MODELS, VARIABLE_INFO, DEFAULT_VARIABLES, ALERT_THRESHOLDS,
    ALERT_PROB_THRESHOLD, DETERMINISTIC_MODELS,
)

# ============================================================
# GOP 2 NHOM MO HINH - DUNG O MOI NOI TRONG APP
# ============================================================
ALL_MODELS = {**MODELS, **DETERMINISTIC_MODELS}

from weather_api import (
    geocode_address,
    reverse_geocode_location,
    get_geojson_status,
    fetch_all_models,
    build_ensemble_dict,
)
from analysis import (
    compute_ensemble_stats,
    detect_extreme_events,
    deduplicate_alerts,
    summarize_temperature,
    summarize_precipitation,
)
from qcvn import (
    evaluate_forecast_qcvn,
    summarize_qcvn_evaluation,
    grade_forecast_qcvn,
)
from storage import (
    save_forecast, save_evaluation, load_evaluations,
    save_favorite, load_favorites, delete_favorite,
)
from notifier import send_telegram, format_alerts


# ============================================================
# NGUONG CHUYEN DOI DANG MUA
# ============================================================
BAR_MAX_MODELS = 3   # <= 3 mo hinh: cot | > 3: duong


# ============================================================
# CAU HINH TRANG
# ============================================================
st.set_page_config(
    page_title="WeatherNext Forecast",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 1rem !important;
    }
    h1 {
        font-size: 1.55rem !important;
        margin-top: 0 !important;
        margin-bottom: 0.6rem !important;
        line-height: 1.3 !important;
    }
    .stButton > button {
        text-align: left;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION STATE
# ============================================================
if "address_input" not in st.session_state:
    st.session_state["address_input"] = "Ninh Kiều, Cần Thơ"
if "pending_run" not in st.session_state:
    st.session_state["pending_run"] = False

if st.session_state.get("prefill_address"):
    st.session_state["address_input"] = st.session_state["prefill_address"]
    st.session_state["prefill_address"] = None
    st.session_state["pending_run"] = True


# ============================================================
# HAM TIEN ICH
# ============================================================
def _load_favorites_safe():
    try:
        return load_favorites()
    except Exception as e:
        print(f"[FAV] Loi doc DB: {e}")
        return []


# ============================================================
# HEADER: TIEU DE + VI TRI DA GHIM
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
                            fav["display"],
                            key=f"fav_btn_{fav['id']}",
                            use_container_width=True,
                            help=(
                                f"Vĩ độ: {fav['lat']:.4f}  |  "
                                f"Kinh độ: {fav['lon']:.4f}"
                            ),
                        ):
                            st.session_state["prefill_address"] = fav["address"]
                            st.rerun()
                    with del_col:
                        if st.button(
                            "✕",
                            key=f"fav_del_{fav['id']}",
                            help="Xóa ghim",
                        ):
                            delete_favorite(fav["id"])
                            st.rerun()

        if len(favorites) > MAX_DISPLAY:
            st.caption(f"+ {len(favorites) - MAX_DISPLAY} vị trí khác")
    else:
        st.caption(
            "Chưa có vị trí nào. Sau khi tra cứu, nhấn "
            "**⭐ Ghim vị trí này** để lưu lại."
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
            key="address_input",
            on_change=_on_address_submit,
            placeholder="VD: Ninh Kiều, Cần Thơ",
        )
    else:
        c1, c2 = st.columns(2)
        with c1:
            lat_input = st.number_input(
                "Vĩ độ:", value=10.0291, format="%.4f", key="lat_input"
            )
        with c2:
            lon_input = st.number_input(
                "Kinh độ:", value=105.7706, format="%.4f", key="lon_input"
            )

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
    enable_qcvn = st.checkbox(
        "Bật đánh giá sai số QCVN", value=True, key="enable_qcvn"
    )

    st.header("🔔 Thông báo")
    enable_telegram = st.checkbox(
        "Gửi Telegram nếu có cảnh báo", value=False, key="enable_tg"
    )

    st.divider()

    with st.expander("📋 Chọn nhanh từ danh sách tỉnh"):
        try:
            from geojson_lookup import list_provinces
            provinces = list_provinces()
            if provinces:
                chosen = st.selectbox(
                    "Tỉnh/Thành phố:",
                    [""] + provinces,
                    key="quick_province_select",
                )
                if chosen:
                    st.session_state["prefill_address"] = chosen
                    st.session_state["pending_run"] = True
                    st.rerun()
            else:
                st.warning("Chưa load được danh sách tỉnh.")
        except FileNotFoundError:
            st.warning("Chưa có file GeoJSON tỉnh.")
        except Exception as e:
            st.warning(f"Lỗi load GeoJSON: {e}")

    st.divider()
    run_btn = st.button(
        "🚀 Lấy dự báo", type="primary", use_container_width=True, key="run_btn"
    )


# ============================================================
# XU LY CHINH
# ============================================================
if run_btn or st.session_state.get("pending_run"):
    st.session_state["pending_run"] = False

    lat, lon, full_name = None, None, None

    # ---------- Buoc 1: Xac dinh toa do ----------
    if input_mode == "Địa chỉ":
        with st.spinner("Đang tìm tọa độ…"):
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
                    mlat = st.number_input(
                        "Vĩ độ:", value=10.0291, format="%.4f", key="mlat"
                    )
                with c2:
                    mlon = st.number_input(
                        "Kinh độ:", value=105.7706, format="%.4f", key="mlon"
                    )
                if st.button("Dùng tọa độ này", key="use_manual"):
                    lat, lon = mlat, mlon
                    full_name = f"({lat:.4f}, {lon:.4f})"

            if lat is None:
                st.stop()
        else:
            lat, lon, full_name = geo
    else:
        lat, lon = lat_input, lon_input
        with st.spinner("Đang tra cứu tên địa danh…"):
            rg = reverse_geocode_location(lat, lon)
        parts = [p for p in [rg.get("commune"), rg.get("province")] if p]
        if parts:
            full_name = ", ".join(parts)
        else:
            full_name = f"({lat:.4f}, {lon:.4f})"

    # ---------- Hien thi vi tri ----------
    st.success(f"📍 {full_name} – Tọa độ: {lat:.4f}, {lon:.4f}")

    # ---------- Nut Ghim ----------
    fav_col1, fav_col2 = st.columns([1, 4])
    with fav_col1:
        current_favs = _load_favorites_safe()
        already = any(f["display"] == full_name for f in current_favs)

        if already:
            st.button("⭐ Đã ghim", disabled=True, key="already_pinned")
        else:
            if st.button("⭐ Ghim vị trí này", key="pin_btn"):
                try:
                    saved = save_favorite(
                        address or full_name, full_name, lat, lon
                    )
                    if saved:
                        st.success(f"⭐ Đã ghim: **{full_name}**")
                    else:
                        st.info("Vị trí đã có trong danh sách.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi ghim: {e}")

    if not model_keys:
        st.warning("Vui lòng chọn ít nhất một mô hình.")
        st.stop()

    # ---------- Buoc 2: Goi API ----------
    with st.spinner("Đang tải dữ liệu từ các mô hình…"):
        raw_models = fetch_all_models(
            lat, lon, variables=DEFAULT_VARIABLES, days=days, model_keys=model_keys
        )

    if not raw_models:
        st.error("❌ Không lấy được dữ liệu từ bất kỳ mô hình nào.")
        st.stop()

    # ---------- Buoc 3: Parse ----------
    temp_ensembles = build_ensemble_dict(raw_models, "temperature_2m")
    precip_ensembles = build_ensemble_dict(raw_models, "precipitation")

    if not temp_ensembles and not precip_ensembles:
        st.error("❌ Không parse được dữ liệu ensemble.")
        st.stop()

    # ---------- Buoc 4: Tabs ----------
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 Biểu đồ dự báo",
        "📊 So sánh mô hình",
        "⚠️ Cảnh báo cực đoan",
        "✅ Đánh giá QCVN",
        "💾 Lịch sử",
        "🗺️ Vị trí & Vùng",
    ])

    # ============================================================
    # TAB 1: BIEU DO DU BAO
    # ============================================================
    with tab1:
        st.subheader("📈 Dự báo nhiệt độ và mưa")

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=("Nhiệt độ 2m (°C)", "Mưa 1h (mm)"),
            vertical_spacing=0.12,
        )

        # ---------- Nhiet do (luon la duong) ----------
        for mk, ens_df in temp_ensembles.items():
            stats = compute_ensemble_stats(ens_df)
            if stats.empty:
                continue
            color = ALL_MODELS[mk]["color"]
            label = ALL_MODELS[mk]["label"]
            rgb = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

            fig.add_trace(go.Scatter(
                x=stats.index, y=stats["p90"],
                mode="lines", line=dict(width=0),
                showlegend=False, hoverinfo="skip",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=stats.index, y=stats["p10"],
                mode="lines", line=dict(width=0),
                fill="tonexty",
                fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)",
                name=f"{label} (10–90%)",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=stats.index, y=stats["mean"],
                mode="lines", line=dict(color=color, width=2),
                name=f"{label} (TB)",
            ), row=1, col=1)

        # ---------- Mua (tu dong chon cot/duong) ----------
        n_precip_models = len(precip_ensembles)
        use_bars = n_precip_models <= BAR_MAX_MODELS

        st.caption(
            f"💧 Mưa hiển thị dạng "
            f"**{'cột' if use_bars else 'đường'}** "
            f"({n_precip_models} mô hình "
            f"{'≤' if use_bars else '>'} {BAR_MAX_MODELS})"
        )

        for mk, ens_df in precip_ensembles.items():
            stats = compute_ensemble_stats(ens_df)
            if stats.empty:
                continue
            color = ALL_MODELS[mk]["color"]
            label = ALL_MODELS[mk]["label"]
            rgb = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

            if use_bars:
                # --- Dang COT ---
                upper = (stats["p90"] - stats["mean"]).clip(lower=0)
                lower = (stats["mean"] - stats["p10"]).clip(lower=0)

                fig.add_trace(go.Bar(
                    x=stats.index,
                    y=stats["mean"],
                    name=f"{label} (mưa)",
                    marker=dict(color=color),
                    error_y=dict(
                        type="data",
                        symmetric=False,
                        array=upper,
                        arrayminus=lower,
                        color=color,
                        thickness=1.2,
                        width=0,
                    ),
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{label}</b><br>"
                        "%{x|%d/%m %H:%M}<br>"
                        "TB: %{y:.2f} mm<extra></extra>"
                    ),
                ), row=2, col=1)
            else:
                # --- Dang DUONG ---
                fig.add_trace(go.Scatter(
                    x=stats.index, y=stats["p90"],
                    mode="lines", line=dict(width=0),
                    showlegend=False, hoverinfo="skip",
                ), row=2, col=1)
                fig.add_trace(go.Scatter(
                    x=stats.index, y=stats["p10"],
                    mode="lines", line=dict(width=0),
                    fill="tonexty",
                    fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)",
                    showlegend=False,
                ), row=2, col=1)
                fig.add_trace(go.Scatter(
                    x=stats.index, y=stats["mean"],
                    mode="lines", line=dict(color=color, width=2),
                    name=f"{label} (mưa)",
                    showlegend=False,
                ), row=2, col=1)

        fig.update_layout(
            height=720,
            hovermode="x unified",
            barmode="group",
            bargap=0.15,
            bargroupgap=0.05,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=40, r=20, t=80, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ---------- Tom tat ----------
        st.subheader("📌 Tóm tắt")
        c1, c2, c3, c4 = st.columns(4)

        if temp_ensembles:
            first_mk = list(temp_ensembles.keys())[0]
            stats = compute_ensemble_stats(temp_ensembles[first_mk])
            summ = summarize_temperature(stats)
            if summ:
                c1.metric("T cao nhất (TB)", f"{summ['max_mean']:.1f} °C")
                c2.metric("T thấp nhất (TB)", f"{summ['min_mean']:.1f} °C")

        if precip_ensembles:
            first_mk = list(precip_ensembles.keys())[0]
            stats = compute_ensemble_stats(precip_ensembles[first_mk])
            summ = summarize_precipitation(stats)
            if summ:
                c3.metric("Tổng mưa (TB)", f"{summ['total_rain_mm']:.1f} mm")
                c4.metric("Đỉnh mưa 1h", f"{summ['peak_hourly_mm']:.1f} mm")

        # ---------- Luu vao DB ----------
        try:
            if temp_ensembles:
                first_mk = list(temp_ensembles.keys())[0]
                stats = compute_ensemble_stats(temp_ensembles[first_mk])
                summ = summarize_temperature(stats)
                save_forecast(
                    full_name, lat, lon,
                    ALL_MODELS[first_mk]["label"], "temperature_2m", days, summ,
                )
            if precip_ensembles:
                first_mk = list(precip_ensembles.keys())[0]
                stats = compute_ensemble_stats(precip_ensembles[first_mk])
                summ = summarize_precipitation(stats)
                save_forecast(
                    full_name, lat, lon,
                    ALL_MODELS[first_mk]["label"], "precipitation", days, summ,
                )
        except Exception as e:
            print(f"[DB] Loi luu forecast: {e}")

    # ============================================================
    # TAB 2: SO SANH MO HINH
    # ============================================================
    with tab2:
        st.subheader("📊 So sánh dự báo giữa các mô hình")

        # ---------- Nhiet do: duong ----------
        if temp_ensembles:
            st.markdown("**Nhiệt độ 2m – Trung bình ensemble**")
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
                ))
            fig_cmp.update_layout(
                xaxis_title="Thời gian", yaxis_title="°C",
                height=420, hovermode="x unified",
                margin=dict(l=40, r=20, t=30, b=40),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

        # ---------- Mua: tu dong cot/duong ----------
        if precip_ensembles:
            n_models_p = len(precip_ensembles)
            use_bars_cmp = n_models_p <= BAR_MAX_MODELS

            st.markdown(
                f"**Mưa 1h – Trung bình ensemble** "
                f"(dạng {'cột' if use_bars_cmp else 'đường'}, "
                f"{n_models_p} mô hình)"
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
                            "%{x|%d/%m %H:%M}<br>"
                            "%{y:.2f} mm<extra></extra>"
                        ),
                    ))
                else:
                    fig_cmp2.add_trace(go.Scatter(
                        x=stats.index, y=stats["mean"],
                        mode="lines",
                        line=dict(color=ALL_MODELS[mk]["color"], width=2),
                        name=ALL_MODELS[mk]["label"],
                    ))

            fig_cmp2.update_layout(
                xaxis_title="Thời gian", yaxis_title="mm",
                height=420, hovermode="x unified",
                barmode="group",
                bargap=0.15,
                bargroupgap=0.05,
                margin=dict(l=40, r=20, t=30, b=40),
            )
            st.plotly_chart(fig_cmp2, use_container_width=True)

        # ---------- Bang so sanh do bat dinh ----------
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
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

    # ============================================================
    # TAB 3: CANH BAO CUC DOAN
    # ============================================================
    with tab3:
        st.subheader("⚠️ Cảnh báo sự kiện cực đoan")
        st.caption(
            f"Ngưỡng: T > {ALERT_THRESHOLDS['temp_high']}°C | "
            f"T < {ALERT_THRESHOLDS['temp_low']}°C | "
            f"Mưa 1h > {ALERT_THRESHOLDS['rain_heavy_1h']} mm | "
            f"Mưa 24h > {ALERT_THRESHOLDS['rain_heavy_24h']} mm | "
            f"Xác suất ≥ {ALERT_PROB_THRESHOLD*100:.0f}%"
        )

        all_alerts = []
        for mk in temp_ensembles:
            alerts = detect_extreme_events(
                temp_ensembles[mk], precip_ensembles.get(mk)
            )
            for a in alerts:
                a["model"] = ALL_MODELS[mk]["label"]
            all_alerts.extend(alerts)

        all_alerts = deduplicate_alerts(all_alerts)

        if not all_alerts:
            st.success("✅ Không có cảnh báo cực đoan trong khoảng dự báo.")
        else:
            st.warning(f"⚠️ Phát hiện **{len(all_alerts)}** cảnh báo.")
            for a in all_alerts:
                with st.expander(
                    f"⚠️ {a['label']} – {a['time']} "
                    f"(P = {a['probability']*100:.0f}%)"
                ):
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        st.write(f"**Mô hình:** {a.get('model', 'N/A')}")
                        st.write(f"**Loại:** {a['type']}")
                        st.write(f"**Ngưỡng:** {a['threshold']}")
                    with cc2:
                        st.write(f"**Giá trị TB:** {a['value_mean']:.2f}")
                        st.write(f"**Xác suất:** {a['probability']*100:.1f}%")
                        st.write(f"**Thời gian:** {a['time']}")

            if enable_telegram:
                msg = format_alerts(all_alerts, full_name)
                if send_telegram(msg):
                    st.success("📨 Đã gửi cảnh báo Telegram.")
                else:
                    st.warning("Không gửi được Telegram (kiểm tra config).")

    # ============================================================
    # TAB 4: DANH GIA QCVN
    # ============================================================
    with tab4:
        st.subheader("✅ Đánh giá chất lượng dự báo theo QCVN 84:2024/BTNMT")
        st.caption("Thông tư 46/2024/TT-BTNMT, áp dụng từ 30/6/2025.")

        if not enable_qcvn:
            st.info("Bật tùy chọn 'Đánh giá sai số QCVN' ở sidebar để xem.")
        else:
            st.info(
                "⚠️ **Lưu ý:** Đánh giá QCVN yêu cầu **dữ liệu quan trắc thực đo**. "
                "Tải file CSV với 2 cột `time` và `observed` để đánh giá."
            )

            uploaded = st.file_uploader(
                "Tải lên file quan trắc (CSV):",
                type=["csv"],
                key="obs_upload",
            )

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
                                "temperature_2m", "temperature",
                            )
                            if not eval_df.empty:
                                summ = summarize_qcvn_evaluation(eval_df)
                                summ["model"] = ALL_MODELS[mk]["label"]
                                summ["variable"] = "Nhiệt độ"
                                summ["grade"] = grade_forecast_qcvn(summ)
                                all_eval.append(summ)
                        except Exception as e:
                            print(f"[QCVN] Loi {mk} nhiet do: {e}")

                    if mk in precip_ensembles:
                        try:
                            eval_df = evaluate_forecast_qcvn(
                                precip_ensembles[mk], obs_df,
                                "precipitation", "precipitation",
                            )
                            if not eval_df.empty:
                                summ = summarize_qcvn_evaluation(eval_df)
                                summ["model"] = ALL_MODELS[mk]["label"]
                                summ["variable"] = "Mưa"
                                summ["grade"] = grade_forecast_qcvn(summ)
                                all_eval.append(summ)
                        except Exception as e:
                            print(f"[QCVN] Loi {mk} mua: {e}")

                if all_eval:
                    result_df = pd.DataFrame(all_eval)
                    display_cols = [
                        "model", "variable", "ME", "MAE", "RMSE",
                        "Bias", "PC", "pct_within_qcvn", "grade",
                    ]
                    available = [c for c in display_cols if c in result_df.columns]
                    st.dataframe(
                        result_df[available].rename(columns={
                            "model": "Mô hình",
                            "variable": "Biến",
                            "pct_within_qcvn": "% đạt QCVN",
                            "grade": "Xếp hạng",
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )

                    for row in all_eval:
                        try:
                            save_evaluation(
                                full_name, lat, lon,
                                row["model"], row["variable"], row,
                            )
                        except Exception as e:
                            print(f"[DB] Loi luu eval: {e}")
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
                st.code(
                    "time,observed\n"
                    "2026-09-10 00:00:00,28.5\n"
                    "2026-09-10 01:00:00,27.8\n"
                    "2026-09-10 02:00:00,27.2",
                    language="csv",
                )

    # ============================================================
    # TAB 5: LICH SU
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
                        mode="lines+markers", name=var,
                    ))
                fig_hist.update_layout(
                    title="Xu hướng RMSE theo thời gian",
                    xaxis_title="Thời gian", yaxis_title="RMSE",
                    height=400,
                    margin=dict(l=40, r=20, t=50, b=40),
                )
                st.plotly_chart(fig_hist, use_container_width=True)

            csv_buf = io.StringIO()
            hist.to_csv(csv_buf, index=False)
            st.download_button(
                "📥 Tải lịch sử (CSV)",
                data=csv_buf.getvalue(),
                file_name="history.csv",
                mime="text/csv",
            )

    # ============================================================
    # TAB 6: VI TRI & VUNG
    # ============================================================
    with tab6:
        st.subheader("🗺️ Thông tin vị trí")

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
        map_df = pd.DataFrame({
            "lat": [lat],
            "lon": [lon],
            "name": [full_name],
        })
        try:
            fig_map = px.scatter_mapbox(
                map_df, lat="lat", lon="lon", text="name",
                zoom=10, height=420,
            )
            fig_map.update_traces(marker=dict(size=18, color="red"))
            fig_map.update_layout(
                mapbox_style="open-street-map",
                margin=dict(l=0, r=0, t=0, b=0),
            )
            st.plotly_chart(fig_map, use_container_width=True)
        except Exception as e:
            st.warning(f"Không vẽ được bản đồ: {e}")

        with st.expander("📋 Danh sách tỉnh/thành"):
            try:
                from geojson_lookup import list_provinces
                provinces = list_provinces()
                st.write(f"Tổng: **{len(provinces)}** tỉnh/thành")
                st.write(", ".join(provinces))
            except Exception as e:
                st.warning(f"Không load được: {e}")


# ============================================================
# TRANG CHAO MUNG
# ============================================================
else:
    st.info(
        "👈 Nhập địa chỉ hoặc tọa độ ở sidebar, chọn mô hình, "
        "rồi nhấn **Enter** hoặc nút **🚀 Lấy dự báo** để bắt đầu."
    )

    st.markdown("""
### 🌟 Tính năng chính

| Tính năng | Mô tả |
|---|---|
| 🌍 **Đa mô hình** | 5 ensemble (WeatherNext 2, GFS, ECMWF, ICON, GEM) + 3 mô hình tham chiếu |
| 📊 **Dải bất định** | Percentile 10–90 từ ensemble |
| 💧 **Mưa tự động** | ≤ 3 mô hình → cột, > 3 mô hình → đường |
| ⚠️ **Cảnh báo cực đoan** | Xác suất vượt ngưỡng nhiệt độ, mưa lớn |
| ✅ **Đánh giá QCVN 84:2024** | ME, MAE, RMSE, Bias, PC theo quy chuẩn |
| 💾 **Lịch sử** | Lưu SQLite, theo dõi độ chính xác theo thời gian |
| 🗺️ **Định vị 2 cấp** | GeoJSON tỉnh/thành + phường/xã (offline) |
| ⭐ **Ghim vị trí** | Lưu và truy cập nhanh các địa điểm yêu thích |
| 🔔 **Thông báo** | Telegram tùy chọn |

### 📋 Quy trình sử dụng

1. **Nhập vị trí** – gõ địa chỉ rồi nhấn **Enter** (tự động chạy), hoặc nhập tọa độ
2. **Chọn mô hình** – 5 ensemble mặc định, thêm 3 mô hình đơn nếu muốn
3. **Xem kết quả** – biểu đồ, so sánh, cảnh báo, đánh giá QCVN
4. **Ghim vị trí** – nhấn ⭐ để lưu vào góc trên bên phải, click lại để chạy nhanh

### 💧 Hiển thị mưa

- **1–3 mô hình**: dạng **cột** với error bar (P10–P90)
- **4+ mô hình**: dạng **đường** để tránh chồng chéo
""")
