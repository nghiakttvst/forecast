"""
Admin: user + thống kê + bản tin.
"""

import streamlit as st
import pandas as pd

from config import BULLETIN_CATEGORIES, BULLETIN_MAX_SIZE_MB
from auth import (
    list_users, register_user, set_user_active,
    delete_user, admin_reset_password,
)
from analytics import (
    get_stats, get_visits_by_day, get_recent_visits, get_top_pages,
)
from storage import (
    save_bulletin, list_bulletins, delete_bulletin,
)


def render_admin_panel(current_user: dict):
    # Lazy import plotly — chỉ load khi vào tab admin
    import plotly.graph_objects as go

    st.markdown("## 🛡️ Bảng điều khiển Admin")

    tab_a, tab_b, tab_c, tab_d, tab_e = st.tabs([
        "📊 Thống kê", "👥 Quản lý user", "🔑 Mật khẩu",
        "➕ Thêm user", "📰 Quản lý bản tin",
    ])

    with tab_a:
        st.subheader("📊 Thống kê tổng quan")
        stats = get_stats()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👁️ Tổng lượt xem", f"{stats['total_views']:,}")
        c2.metric("👤 Phiên duy nhất", f"{stats['unique_sessions']:,}")
        c3.metric("📅 Xem hôm nay", f"{stats['views_today']:,}")
        c4.metric("👥 Khách hôm nay", f"{stats['unique_today']:,}")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("📆 Xem tuần", f"{stats['views_week']:,}")
        c6.metric("👥 Khách tuần", f"{stats['unique_week']:,}")
        c7.metric("🗓️ Xem tháng", f"{stats['views_month']:,}")
        c8.metric("🧑 Tài khoản",
                  f"{stats['active_users']}/{stats['total_users']}")

        st.divider()
        st.subheader("📈 Lượt truy cập 30 ngày qua")
        data = get_visits_by_day(30)
        if data:
            df = pd.DataFrame(data)
            df["day"] = pd.to_datetime(df["day"])
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df["day"], y=df["views"],
                                 name="Lượt xem", marker_color="#4a9fe0"))
            fig.add_trace(go.Scatter(
                x=df["day"], y=df["unique_sessions"],
                name="Khách duy nhất", mode="lines+markers",
                line=dict(color="#ea4335", width=2), yaxis="y2"))
            fig.update_layout(height=400, hovermode="x unified",
                              yaxis=dict(title="Lượt xem"),
                              yaxis2=dict(title="Khách",
                                          overlaying="y", side="right"),
                              legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, width='stretch')

        st.subheader("🕒 Lượt truy cập gần đây")
        recent = get_recent_visits(50)
        if recent:
            st.dataframe(pd.DataFrame(recent), width='stretch',
                         hide_index=True, height=300)

    with tab_b:
        st.subheader("👥 Danh sách user")
        users = list_users()
        if users:
            df = pd.DataFrame(users)
            df["is_active"] = df["is_active"].apply(
                lambda x: "✅" if x else "🚫")
            st.dataframe(df[["id", "username", "full_name", "email",
                             "role", "is_active", "login_count",
                             "last_login"]],
                         width='stretch', hide_index=True)

            st.divider()
            u_opts = {u["id"]: f"{u['username']} ({u.get('full_name','')})"
                      for u in users}
            c1, c2, c3 = st.columns(3)
            with c1:
                sel = st.selectbox("Khóa/Mở:", list(u_opts.keys()),
                                   format_func=lambda x: u_opts[x],
                                   key="adm_toggle")
                u = next((x for x in users if x["id"] == sel), None)
                if u:
                    cur = bool(u["is_active"])
                    if st.button("🚫 Khóa" if cur else "✅ Mở",
                                 key="adm_btn_t"):
                        set_user_active(sel, not cur)
                        st.rerun()
            with c2:
                del_id = st.selectbox("Xóa:", list(u_opts.keys()),
                                      format_func=lambda x: u_opts[x],
                                      key="adm_del")
                u_del = next((x for x in users if x["id"] == del_id), None)
                if u_del and u_del["username"] != "admin":
                    if st.button("🗑️ Xóa", key="adm_btn_d"):
                        delete_user(del_id)
                        st.rerun()
            with c3:
                rst_id = st.selectbox("Reset MK:", list(u_opts.keys()),
                                      format_func=lambda x: u_opts[x],
                                      key="adm_rst")
                np = st.text_input("MK mới:", type="password", key="adm_np")
                if st.button("🔑 Đặt lại", key="adm_btn_r"):
                    if np:
                        r = admin_reset_password(rst_id, np)
                        (st.success if r["success"]
                         else st.error)(r["message"])

    with tab_c:
        st.subheader("🔑 Mật khẩu người dùng")
        st.warning("⚠️ Chỉ admin xem được.")
        users = list_users()
        if users:
            rows = [{
                "ID": u["id"], "Tên ĐN": u["username"],
                "🔑 Mật khẩu": u.get("password_plain") or "(chưa có)",
                "Họ tên": u.get("full_name", ""),
                "Vai trò": u["role"],
            } for u in users]
            st.dataframe(pd.DataFrame(rows), width='stretch',
                         hide_index=True)

    with tab_d:
        st.subheader("➕ Thêm user")
        with st.form("adm_add_user"):
            c1, c2 = st.columns(2)
            with c1:
                nu = st.text_input("Tên ĐN *", key="a_nu")
                np = st.text_input("Mật khẩu *", type="password", key="a_np")
                ne = st.text_input("Email", key="a_ne")
            with c2:
                nf = st.text_input("Họ tên", key="a_nf")
                nr = st.selectbox("Vai trò", ["user", "admin"], key="a_nr")
            if st.form_submit_button("✅ Tạo"):
                if not nu or not np:
                    st.error("Nhập đủ tên ĐN và MK.")
                else:
                    r = register_user(nu, np, ne, nf, nr)
                    (st.success if r["success"]
                     else st.error)(r["message"])
                    if r["success"]:
                        st.rerun()

    with tab_e:
        st.subheader("📰 Upload & Quản lý bản tin")

        with st.form("adm_upload_bulletin"):
            cat = st.selectbox(
                "Loại bản tin:",
                options=list(BULLETIN_CATEGORIES.keys()),
                format_func=lambda k: f"{BULLETIN_CATEGORIES[k]['icon']} "
                                       f"{BULLETIN_CATEGORIES[k]['label']}",
            )
            title = st.text_input("Tiêu đề *")
            desc = st.text_area("Mô tả ngắn", height=80)
            uploaded = st.file_uploader("Chọn file PDF *", type=["pdf"])

            if st.form_submit_button("📤 Upload bản tin"):
                if not title:
                    st.error("Nhập tiêu đề.")
                elif not uploaded:
                    st.error("Chọn file PDF.")
                else:
                    fb = uploaded.getvalue()
                    size_mb = len(fb) / 1e6
                    if size_mb > BULLETIN_MAX_SIZE_MB:
                        st.error(f"File quá lớn ({size_mb:.1f}MB)")
                    else:
                        try:
                            bid = save_bulletin(
                                category=cat, title=title, description=desc,
                                filename=uploaded.name, file_bytes=fb)
                            st.success(f"✅ Đã upload ID={bid}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi: {e}")

        st.divider()
        st.subheader("📚 Danh sách bản tin")
        cat_filter = st.selectbox(
            "Lọc:",
            options=["all"] + list(BULLETIN_CATEGORIES.keys()),
            format_func=lambda k: "Tất cả" if k == "all"
            else BULLETIN_CATEGORIES[k]["label"],
            key="adm_cat_filter",
        )

        bulletins = list_bulletins(
            category=None if cat_filter == "all" else cat_filter, limit=50)

        if not bulletins:
            st.info("Chưa có bản tin nào.")
        else:
            for b in bulletins:
                ci = BULLETIN_CATEGORIES.get(b["category"], {})
                icon = ci.get("icon", "📄")
                lbl = ci.get("label", b["category"])
                size_kb = (b.get("file_size") or 0) / 1024
                with st.expander(
                    f"{icon} **{b['title']}** — {lbl} — "
                    f"{b['created_at'][:16]}"
                ):
                    st.write(f"**ID:** {b['id']}")
                    st.write(f"**Mô tả:** {b.get('description') or '(không)'}")
                    st.write(f"**File:** {b['filename']} ({size_kb:.0f} KB)")
                    if st.button("🗑️ Xóa", key=f"del_bul_{b['id']}"):
                        delete_bulletin(b["id"])
                        st.rerun()