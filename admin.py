"""
Trang Admin: quản lý users, thống kê truy cập.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from auth import (
    list_users, register_user, set_user_active,
    delete_user, admin_reset_password,
)
from analytics import (
    get_stats, get_visits_by_day, get_recent_visits, get_top_pages,
)


def render_admin_panel(current_user: dict):
    if current_user.get("role") != "admin":
        st.error("🚫 Bạn không có quyền.")
        return

    st.markdown("## 🛡️ Bảng điều khiển Admin")
    st.caption(f"Xin chào **{current_user.get('full_name', 'Admin')}**")

    tab_a, tab_b, tab_c, tab_d = st.tabs([
        "📊 Thống kê",
        "👥 Quản lý user",
        "🔑 Xem mật khẩu",
        "➕ Thêm user",
    ])

    # TAB A
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
        c8.metric("🧑 Tài khoản", f"{stats['active_users']}/{stats['total_users']}")

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
            fig.update_layout(
                height=420, hovermode="x unified",
                yaxis=dict(title="Lượt xem"),
                yaxis2=dict(title="Khách", overlaying="y", side="right"),
                legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chưa có dữ liệu.")

        st.subheader("🔥 Trang xem nhiều nhất")
        top = get_top_pages(10)
        if top:
            st.dataframe(pd.DataFrame(top).rename(
                columns={"page": "Trang", "views": "Lượt xem"}),
                use_container_width=True, hide_index=True)

        st.subheader("🕒 Lượt truy cập gần đây")
        recent = get_recent_visits(100)
        if recent:
            st.dataframe(
                pd.DataFrame(recent)[["created_at", "username", "page", "action"]]
                .rename(columns={"created_at": "Thời gian", "username": "User",
                                 "page": "Trang", "action": "HĐ"}),
                use_container_width=True, hide_index=True, height=400)

    # TAB B
    with tab_b:
        st.subheader("👥 Danh sách người dùng")
        users = list_users()

        if not users:
            st.info("Chưa có user.")
        else:
            df = pd.DataFrame(users)
            df["is_active"] = df["is_active"].apply(
                lambda x: "✅" if x else "🚫")
            st.dataframe(
                df[["id", "username", "full_name", "email", "role",
                    "is_active", "login_count", "last_login", "created_at"]]
                .rename(columns={"id": "ID", "username": "Tên ĐN",
                                 "full_name": "Họ tên", "email": "Email",
                                 "role": "Vai trò", "is_active": "TT",
                                 "login_count": "Lần ĐN", "last_login": "ĐN cuối",
                                 "created_at": "Ngày tạo"}),
                use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("⚙️ Thao tác")
            user_options = {u["id"]: f"{u['username']} ({u.get('full_name','')})"
                            for u in users}

            col1, col2, col3 = st.columns(3)
            with col1:
                sel_id = st.selectbox("Khóa/Mở khóa:",
                                      list(user_options.keys()),
                                      format_func=lambda x: user_options[x],
                                      key="admin_toggle_sel")
                u = next((x for x in users if x["id"] == sel_id), None)
                if u:
                    current = bool(u["is_active"])
                    label = "🚫 Khóa" if current else "✅ Mở"
                    if st.button(label, key="btn_toggle"):
                        set_user_active(sel_id, not current)
                        st.success("Đã đổi trạng thái.")
                        st.rerun()

            with col2:
                del_id = st.selectbox("Xóa user:", list(user_options.keys()),
                                      format_func=lambda x: user_options[x],
                                      key="admin_del_sel")
                u_del = next((x for x in users if x["id"] == del_id), None)
                if u_del and u_del["username"] == "admin":
                    st.warning("Không xóa admin.")
                else:
                    if st.button("🗑️ Xóa", key="btn_del"):
                        delete_user(del_id)
                        st.rerun()

            with col3:
                rst_id = st.selectbox("Reset mật khẩu:",
                                      list(user_options.keys()),
                                      format_func=lambda x: user_options[x],
                                      key="admin_reset_sel")
                new_pwd = st.text_input("Mật khẩu mới:", type="password",
                                        key="admin_new_pwd")
                if st.button("🔑 Đặt lại", key="btn_reset_pwd"):
                    if new_pwd:
                        r = admin_reset_password(rst_id, new_pwd)
                        (st.success if r["success"] else st.error)(r["message"])

    # TAB C
    with tab_c:
        st.subheader("🔑 Danh sách mật khẩu")
        st.warning("⚠️ **Bảo mật:** Chỉ admin xem được. Không chụp màn hình.")

        users = list_users()
        if not users:
            st.info("Chưa có user.")
        else:
            rows = []
            for u in users:
                rows.append({
                    "ID": u["id"],
                    "Tên ĐN": u["username"],
                    "🔑 Mật khẩu": u.get("password_plain") or "(chưa có)",
                    "Họ tên": u.get("full_name", ""),
                    "Email": u.get("email", ""),
                    "Vai trò": u["role"],
                    "TT": "✅" if u["is_active"] else "🚫",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True, height=500)

            csv_buf = df.to_csv(index=False)
            st.download_button("📥 Tải CSV",
                               data=csv_buf.encode("utf-8-sig"),
                               file_name="users_passwords.csv",
                               mime="text/csv")

    # TAB D
    with tab_d:
        st.subheader("➕ Thêm user mới")
        with st.form("form_add_user"):
            col1, col2 = st.columns(2)
            with col1:
                nu = st.text_input("Tên đăng nhập *", key="nu_user")
                np = st.text_input("Mật khẩu *", type="password", key="nu_pwd")
                ne = st.text_input("Email", key="nu_email")
            with col2:
                nf = st.text_input("Họ tên", key="nu_fullname")
                nr = st.selectbox("Vai trò", ["user", "admin"], key="nu_role")

            if st.form_submit_button("✅ Tạo tài khoản"):
                if not nu or not np:
                    st.error("Bắt buộc nhập tên ĐN và mật khẩu.")
                else:
                    r = register_user(nu, np, ne, nf, nr)
                    (st.success if r["success"] else st.error)(r["message"])
                    if r["success"]:
                        st.rerun()