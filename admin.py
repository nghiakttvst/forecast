"""
Trang Admin: quản lý users, xem thống kê truy cập.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from auth import (
    list_users, register_user, set_user_active,
    delete_user, change_password,
)
from analytics import (
    get_stats, get_visits_by_day, get_recent_visits, get_top_pages,
)


def render_admin_panel(current_user: dict):
    """Render toàn bộ trang admin."""
    if current_user.get("role") != "admin":
        st.error("🚫 Bạn không có quyền truy cập trang này.")
        return

    st.markdown("## 🛡️ Bảng điều khiển Admin")
    st.caption(
        f"Xin chào **{current_user.get('full_name') or current_user.get('username')}** "
        f"— Vai trò: **{current_user.get('role')}**"
    )

    tab_a, tab_b, tab_c, tab_d = st.tabs([
        "📊 Thống kê truy cập",
        "👥 Quản lý người dùng",
        "➕ Thêm người dùng",
        "🔑 Đổi mật khẩu",
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
        c5.metric("📆 Xem tuần này", f"{stats['views_week']:,}")
        c6.metric("👥 Khách tuần này", f"{stats['unique_week']:,}")
        c7.metric("🗓️ Xem tháng này", f"{stats['views_month']:,}")
        c8.metric("🧑 Tài khoản", f"{stats['active_users']}/{stats['total_users']}")

        st.divider()
        st.subheader("📈 Lượt truy cập 30 ngày qua")
        data = get_visits_by_day(30)

        if data:
            df = pd.DataFrame(data)
            df["day"] = pd.to_datetime(df["day"])

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df["day"], y=df["views"],
                name="Lượt xem", marker_color="#4a9fe0",
            ))
            fig.add_trace(go.Scatter(
                x=df["day"], y=df["unique_sessions"],
                name="Khách duy nhất", mode="lines+markers",
                line=dict(color="#ea4335", width=2),
                yaxis="y2",
            ))
            fig.update_layout(
                height=420, hovermode="x unified",
                yaxis=dict(title="Lượt xem"),
                yaxis2=dict(title="Khách", overlaying="y", side="right"),
                legend=dict(orientation="h", y=1.1),
                margin=dict(l=40, r=40, t=20, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chưa có dữ liệu truy cập.")

        st.subheader("🔥 Trang xem nhiều nhất")
        top = get_top_pages(10)
        if top:
            st.dataframe(
                pd.DataFrame(top).rename(columns={"page": "Trang", "views": "Lượt xem"}),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("Chưa có dữ liệu.")

        st.subheader("🕒 Lượt truy cập gần đây (100 bản ghi)")
        recent = get_recent_visits(100)
        if recent:
            st.dataframe(
                pd.DataFrame(recent)[["created_at", "username", "page", "action"]].rename(
                    columns={
                        "created_at": "Thời gian",
                        "username": "Người dùng",
                        "page": "Trang",
                        "action": "Hành động",
                    }
                ),
                use_container_width=True, hide_index=True, height=400,
            )
        else:
            st.info("Chưa có lượt truy cập nào.")

    with tab_b:
        st.subheader("👥 Danh sách người dùng")
        users = list_users()

        if not users:
            st.info("Chưa có người dùng nào.")
        else:
            df = pd.DataFrame(users)
            df["is_active"] = df["is_active"].apply(
                lambda x: "✅ Hoạt động" if x else "🚫 Đã khóa"
            )
            st.dataframe(
                df[[
                    "id", "username", "full_name", "email", "role",
                    "is_active", "login_count", "last_login", "created_at",
                ]].rename(columns={
                    "id": "ID", "username": "Tên ĐN", "full_name": "Họ tên",
                    "email": "Email", "role": "Vai trò", "is_active": "Trạng thái",
                    "login_count": "Số lần ĐN", "last_login": "ĐN cuối",
                    "created_at": "Ngày tạo",
                }),
                use_container_width=True, hide_index=True,
            )

            st.divider()
            st.subheader("⚙️ Thao tác người dùng")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Khóa / Mở khóa**")
                user_options = {u["id"]: f"{u['username']} ({u['full_name']})" for u in users}
                sel_id = st.selectbox(
                    "Chọn user:", list(user_options.keys()),
                    format_func=lambda x: user_options[x],
                    key="admin_user_toggle",
                )
                u = next((x for x in users if x["id"] == sel_id), None)
                if u:
                    current = bool(u["is_active"])
                    label = "🚫 Khóa tài khoản" if current else "✅ Mở khóa"
                    if st.button(label, key="btn_toggle_active"):
                        set_user_active(sel_id, not current)
                        st.success(f"Đã {'khóa' if current else 'mở khóa'} {u['username']}")
                        st.rerun()

            with col2:
                st.markdown("**Xóa người dùng**")
                del_id = st.selectbox(
                    "Chọn user để xóa:", list(user_options.keys()),
                    format_func=lambda x: user_options[x],
                    key="admin_user_delete",
                )
                u_del = next((x for x in users if x["id"] == del_id), None)
                if u_del and u_del["username"] == "admin":
                    st.warning("Không thể xóa admin.")
                else:
                    if st.button("🗑️ Xóa vĩnh viễn", key="btn_delete_user"):
                        if u_del:
                            delete_user(del_id)
                            st.success(f"Đã xóa {u_del['username']}")
                            st.rerun()

    with tab_c:
        st.subheader("➕ Thêm người dùng mới")
        with st.form("form_add_user"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Tên đăng nhập *", key="nu_username")
                new_password = st.text_input("Mật khẩu *", type="password", key="nu_pwd")
                new_email = st.text_input("Email", key="nu_email")
            with col2:
                new_fullname = st.text_input("Họ và tên", key="nu_fullname")
                new_role = st.selectbox(
                    "Vai trò", ["user", "admin"], key="nu_role"
                )

            submit = st.form_submit_button("✅ Tạo tài khoản")

            if submit:
                if not new_username or not new_password:
                    st.error("Tên đăng nhập và mật khẩu là bắt buộc.")
                else:
                    result = register_user(
                        username=new_username,
                        password=new_password,
                        email=new_email,
                        full_name=new_fullname,
                        role=new_role,
                    )
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

    with tab_d:
        st.subheader("🔑 Đổi mật khẩu")
        st.caption("Đổi mật khẩu của chính bạn (admin đang đăng nhập).")

        with st.form("form_change_pwd"):
            old_pwd = st.text_input("Mật khẩu cũ *", type="password")
            new_pwd = st.text_input("Mật khẩu mới *", type="password")
            confirm_pwd = st.text_input("Nhập lại mật khẩu mới *", type="password")

            submit_pwd = st.form_submit_button("💾 Đổi mật khẩu")

            if submit_pwd:
                if not old_pwd or not new_pwd:
                    st.error("Vui lòng nhập đầy đủ.")
                elif new_pwd != confirm_pwd:
                    st.error("Mật khẩu mới không khớp.")
                else:
                    result = change_password(
                        current_user["id"], old_pwd, new_pwd
                    )
                    if result["success"]:
                        st.success(result["message"])
                    else:
                        st.error(result["message"])
