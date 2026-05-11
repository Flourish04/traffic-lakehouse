import streamlit as st
import pandas as pd
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from utils.database import run_query, get_traffic_events, get_rush_offpeak_query
from utils.chart_utils import apply_dark_template
from utils.config import COLOR_PALETTE as C, DISTRICTS
from utils.cache_utils import ttl_for_dashboard

st.set_page_config(page_title="D1 - Traffic Map", page_icon="🗺️", layout="wide")

DASHBOARD = {
    "id": "D1",
    "title": "Traffic Map",
    "icon": "🗺️",
    "description": "Bản đồ giám sát giao thông TP.HCM — KPI tổng quan, bản đồ nhiệt, top camera đông nhất / chậm nhất.",
    "refresh": "5 phút",
    "color": "#2E86AB",
}
TTL = ttl_for_dashboard("D1")

with open(Path(__file__).parent.parent / "styles" / "custom.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────
def sidebar_nav():
    with st.sidebar:
        st.markdown("### 🗺️ Traffic Map")
        st.markdown("---")

        date_filter_mode = st.radio(
            "Khoảng thời gian",
            ["Tất cả ngày", "Ngày cụ thể"],
            index=0,
            horizontal=True,
        )

        specific_date = None
        if date_filter_mode == "Ngày cụ thể":
            specific_date = st.date_input(
                "Chọn ngày kết thúc",
                value=None,
                label_visibility="collapsed",
            )

        days = st.selectbox("Số ngày", [1, 7, 14, 30], index=1,
                            format_func=lambda x: f"{x} ngày")

        # Compute end_date for query: if specific_date is chosen,
        # end = that date + 1 day (exclusive), else end = now
        if specific_date is not None:
            end_date = datetime.combine(specific_date, datetime.max.time())
            end_date = end_date + timedelta(days=1)
        else:
            end_date = None

        selected_districts = st.multiselect("Quận", DISTRICTS, [])
        st.markdown("---")
        st.markdown(f"**Cache TTL:** {TTL}s")
        return days, selected_districts, end_date


# ─── KPI Row with trend ────────────────────────────────────────────────────
def render_kpi_row(df, df_prev=None):
    """Renders a 5-column KPI row: total cams, events, avg speed, avg vehicles, camera health.
    Each KPI shows the current value + optional delta vs previous period."""
    total_cams = int(df["camera_id"].nunique())
    total_events = len(df)
    avg_speed = df["speed_avg_kmh"].mean()
    avg_vehicles = df["vehicles_count"].mean()

    # Camera health
    up_cams = int(df[df["camera_status"] == "UP"]["camera_id"].nunique())
    health_pct = up_cams / total_cams * 100 if total_cams > 0 else 0

    # Compute deltas vs previous period if data available
    delta_speed = None
    delta_vehicles = None
    if df_prev is not None and not df_prev.empty:
        prev_speed = df_prev["speed_avg_kmh"].mean()
        prev_vehicles = df_prev["vehicles_count"].mean()
        if prev_speed > 0:
            delta_speed = avg_speed - prev_speed
        if prev_vehicles > 0:
            delta_vehicles = avg_vehicles - prev_vehicles

    k1, k2, k3, k4, k5 = st.columns(5, gap="medium")

    with k1:
        st.metric(
            "Tổng Cameras",
            f"{total_cams:,}",
            help="Số camera đang hoạt động và không hoạt động",
        )
    with k2:
        st.metric(
            "Sự kiện (24h)",
            f"{total_events:,}",
            help="Tổng số batch sự kiện giao thông trong kỳ",
        )
    with k3:
        st.metric(
            "Tốc độ TB",
            f"{avg_speed:.1f} km/h",
            delta=f"{delta_speed:.1f} km/h" if delta_speed is not None else None,
            delta_color="normal" if (delta_speed or 0) >= 0 else "inverse",
            help="Tốc độ trung bình toàn thành phố (km/h)",
        )
    with k4:
        st.metric(
            "Phương tiện TB / slot",
            f"{avg_vehicles:.1f}",
            delta=f"{delta_vehicles:.1f}" if delta_vehicles is not None else None,
            delta_color="normal" if (delta_vehicles or 0) >= 0 else "inverse",
            help="Số phương tiện trung bình mỗi batch 5 phút",
        )
    with k5:
        st.metric(
            "Camera Health",
            f"{health_pct:.0f}%",
            f"{up_cams}/{total_cams} UP",
            delta_color="normal" if health_pct >= 95 else "inverse",
            help="Tỷ lệ camera đang hoạt động (UP) / tổng số camera",
        )


# ─── Scatter Map ────────────────────────────────────────────────────────────
def render_scatter_map(df):
    """Interactive scatter map showing cameras as dots colored by congestion level."""
    if df is None or df.empty:
        st.info("Không có dữ liệu bản đồ.")
        return

    map_df = df.groupby(["camera_id", "display_name", "district",
                          "location_lat", "location_lon"]).agg(
        avg_speed=("speed_avg_kmh", "mean"),
        avg_vehicles=("vehicles_count", "mean"),
        slots=("vehicles_count", "count"),
    ).reset_index()

    if map_df[["location_lat", "location_lon"]].isnull().all().all():
        st.info("Dữ liệu tọa độ không có sẵn cho bản đồ.")
        return

    map_df = map_df.dropna(subset=["location_lat", "location_lon"])

    def speed_color(s):
        if s < 15: return "#FF6B6B"      # đỏ: kẹt nặng
        elif s < 25: return "#FFD93D"      # vàng: đông xe
        elif s < 35: return "#96CEB4"      # xanh nhạt: bình thường
        else: return "#4ECDC4"             # xanh: thông thoáng

    map_df["color"] = map_df["avg_speed"].apply(speed_color)
    map_df["size"] = map_df["avg_vehicles"].clip(lower=5) / 5 + 8

    fig = go.Figure(go.Scattermapbox(
        lat=map_df["location_lat"],
        lon=map_df["location_lon"],
        mode="markers",
        marker=dict(
            size=map_df["size"],
            color=map_df["color"],
            opacity=0.85,
        ),
        text=[
            f"<b>{row['display_name']}</b><br>"
            f"Quận: {row['district']}<br>"
            f"Tốc độ TB: {row['avg_speed']:.1f} km/h<br>"
            f"Phương tiện TB: {row['avg_vehicles']:.1f} / slot<br>"
            f"Samples: {row['slots']}"
            for _, row in map_df.iterrows()
        ],
        hovertemplate="%{text}<extra></extra>",
    ))

    fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=10.78, lon=106.70),
            zoom=12,
        ),
        height=420,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="#1A1A2E",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Top 10 Camera Đông Nhất (Horizontal Bar) ───────────────────────────────
def render_top_busiest(df):
    busiest = (
        df.groupby(["display_name", "district"])
        .agg(Avg_Vehicles=("vehicles_count", "mean"))
        .reset_index()
        .round(1)
        .sort_values("Avg_Vehicles", ascending=False)
        .head(10)
    )
    if busiest.empty:
        return

    max_v = busiest["Avg_Vehicles"].max()
    colors = [
        f"rgba(231,76,60,{0.4 + 0.6 * v / max_v})"
        for v in busiest["Avg_Vehicles"]
    ]

    fig = go.Figure(go.Bar(
        x=busiest["Avg_Vehicles"],
        y=busiest["display_name"],
        orientation="h",
        marker_color=colors,
        text=busiest["Avg_Vehicles"].round(1),
        textposition="outside",
        textfont=dict(color="#EAEAEA", size=10),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Xe TB: %{x:.1f} / slot<extra></extra>"
        ),
    ))
    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Top 10 Camera Đông Nhất", font=dict(size=14, color="#EAEAEA"), x=0, xanchor="left"),
        xaxis_title="Xe trung bình / slot 5 phút",
        yaxis_title="",
        height=420,
        showlegend=False,
        margin=dict(l=240, r=40, t=40, b=40),
        xaxis=dict(showgrid=True, gridcolor="#2A3042"),
        yaxis=dict(tickfont=dict(size=10, color="#EAEAEA")),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── District Summary Table with conditional formatting ───────────────────────
def render_district_summary(df):
    summary = (
        df.groupby("district")
        .agg(
            Cameras=("camera_id", "nunique"),
            Avg_Vehicles=("vehicles_count", "mean"),
            Avg_Speed=("speed_avg_kmh", "mean"),
            Congestion_Rate=("speed_avg_kmh", lambda x: (x < 15).sum() / len(x) * 100),
        )
        .reset_index()
        .round(1)
        .sort_values("Avg_Speed", ascending=True)
        .head(20)
    )

    def status_emoji(speed):
        if speed < 15: return "🔴 Kẹt nặng"
        elif speed < 25: return "🟡 Đông xe"
        elif speed < 35: return "🟢 Bình thường"
        else: return "💨 Thông thoáng"

    summary["Tình trạng"] = summary["Avg_Speed"].apply(status_emoji)

    col_order = ["district", "Cameras", "Avg_Vehicles", "Avg_Speed", "Congestion_Rate", "Tình trạng"]
    summary = summary[col_order]
    summary.columns = ["Quận", "Cameras", "Xe TB/slot", "Tốc độ TB (km/h)", "Tỷ lệ kẹt (%)", "Tình trạng"]

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        height=420,
        column_config={
            "Quận": st.column_config.TextColumn("Quận", width="medium"),
            "Cameras": st.column_config.NumberColumn("Cameras", format="%d"),
            "Xe TB/slot": st.column_config.NumberColumn("Xe TB/slot", format="%.1f"),
            "Tốc độ TB (km/h)": st.column_config.NumberColumn("Tốc độ TB (km/h)", format="%.1f"),
            "Tỷ lệ kẹt (%)": st.column_config.NumberColumn("Tỷ lệ kẹt (%)", format="%.1f%%"),
            "Tình trạng": st.column_config.TextColumn("Tình trạng"),
        },
    )


# ─── Rush Hour vs Off-Peak (Grouped Bar, scrollable) ──────────────────────────
def render_rush_vs_offpeak(rush_df):
    if rush_df is None or rush_df.empty:
        st.info("Không có dữ liệu Rush Hour.")
        return

    districts = sorted(rush_df["district"].dropna().unique().tolist())
    rush_colors = {"Rush Hour": "#E94F37", "Off-Peak": "#4ECDC4"}

    fig = go.Figure()
    for period, color in rush_colors.items():
        sub = rush_df[rush_df["time_period"] == period].set_index("district").reindex(districts).reset_index()
        sub = sub.dropna(subset=["district", "avg_vehicles"])
        fig.add_trace(go.Bar(
            name=period,
            x=sub["district"],
            y=sub["avg_vehicles"],
            marker_color=color,
            text=sub["avg_vehicles"].round(1),
            textposition="outside",
            textfont=dict(color="#EAEAEA", size=9),
        ))

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Rush Hour vs Off-Peak theo Quận", font=dict(size=14, color="#EAEAEA"), x=0, xanchor="left"),
        xaxis_title="",
        yaxis_title="Xe trung bình",
        barmode="group",
        height=420,
        showlegend=True,
        legend=dict(font=dict(color="#EAEAEA"), bgcolor="#1A1A2E"),
        margin=dict(b=60, l=40, r=40, t=40),
        xaxis=dict(
            tickangle=-30,
            tickfont=dict(size=10, color="#EAEAEA"),
            gridcolor="#2A3042",
            rangeslider=dict(visible=True, thickness=0.05),
        ),
        yaxis=dict(gridcolor="#2A3042"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Top 10 Camera Chậm Nhất (Horizontal Bar — same UX as busiest) ──────────
def render_top_slowest(df):
    slowest = (
        df.groupby(["display_name", "district"])
        .agg(
            Avg_Speed=("speed_avg_kmh", "mean"),
            Avg_Vehicles=("vehicles_count", "mean"),
        )
        .reset_index()
        .round(1)
        .sort_values("Avg_Speed", ascending=True)
        .head(10)
    )
    if slowest.empty:
        return

    colors = [
        "#FF6B6B" if v < 15 else "#FFD93D" if v < 25 else "#96CEB4"
        for v in slowest["Avg_Speed"]
    ]

    fig = go.Figure(go.Bar(
        x=slowest["Avg_Speed"],
        y=slowest["display_name"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}" for v in slowest["Avg_Speed"]],
        textposition="outside",
        textfont=dict(color="#EAEAEA", size=10),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Tốc độ TB: %{x:.1f} km/h<extra></extra>"
        ),
    ))
    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Top 10 Camera Chậm Nhất", font=dict(size=14, color="#EAEAEA"), x=0, xanchor="left"),
        xaxis_title="Tốc độ trung bình (km/h)",
        yaxis_title="",
        height=420,
        showlegend=False,
        margin=dict(l=240, r=40, t=40, b=40),
        xaxis=dict(showgrid=True, gridcolor="#2A3042", range=[0, max(slowest["Avg_Speed"].max() * 1.3, 50)]),
        yaxis=dict(tickfont=dict(size=10, color="#EAEAEA")),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Speed Distribution Gauge Row ───────────────────────────────────────────
def render_speed_distribution(df):
    """Mini bar chart showing speed category distribution."""
    bins = [
        ("< 10 km/h", df["speed_avg_kmh"] < 10),
        ("10-20 km/h", (df["speed_avg_kmh"] >= 10) & (df["speed_avg_kmh"] < 20)),
        ("20-30 km/h", (df["speed_avg_kmh"] >= 20) & (df["speed_avg_kmh"] < 30)),
        ("30-40 km/h", (df["speed_avg_kmh"] >= 30) & (df["speed_avg_kmh"] < 40)),
        ("> 40 km/h", df["speed_avg_kmh"] >= 40),
    ]
    labels = [l for l, _ in bins]
    counts = [int(c.sum()) for _, c in bins]
    total = sum(counts)
    pcts = [f"{c/total*100:.1f}%" if total > 0 else "0%" for c in counts]
    bar_colors = ["#FF6B6B", "#FF9F43", "#FFD93D", "#96CEB4", "#4ECDC4"]

    fig = go.Figure(go.Bar(
        x=counts,
        y=labels,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{c:,}  ({p})" for c, p in zip(counts, pcts)],
        textposition="outside",
        textfont=dict(color="#EAEAEA", size=10),
        hovertemplate="<b>%{y}</b><br>%{x:,} sự kiện (%{text})<extra></extra>",
    ))
    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Phân bổ Tốc độ Giao thông", font=dict(size=14, color="#EAEAEA"), x=0, xanchor="left"),
        xaxis_title="Số sự kiện",
        yaxis_title="",
        height=460,
        showlegend=False,
        margin=dict(l=80, r=80, t=40, b=40),
        xaxis=dict(showgrid=True, gridcolor="#2A3042"),
        yaxis=dict(tickfont=dict(size=10, color="#EAEAEA")),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Main Layout ─────────────────────────────────────────────────────────────
def render_layout(df, rush_df, df_prev=None):
    # ── Tầng 1: Executive Summary ──────────────────────────────────────────
    st.markdown("---")
    render_kpi_row(df, df_prev)
    st.markdown("")

    # ── Tầng 2: Spatial & Macro View ───────────────────────────────────────
    # Bản đồ trả lời "Kẹt ở đâu?" + Phân bổ tốc độ trả lời "Tình hình chung thế nào?"
    c2_left, c2_right = st.columns([5, 5], gap="medium")
    with c2_left:
        st.markdown("##### 🗺️ Bản đồ Giao thông")
        st.caption("🔴 <15 · 🟡 15–25 · 🟢 25–35 · 💨 >35 km/h")
        render_scatter_map(df)
    with c2_right:
        st.markdown("##### 📊 Phân bổ Tốc độ")
        render_speed_distribution(df)

    # ── Tầng 3: Actionable Insights ────────────────────────────────────────
    # Top 10 Chậm vs Đông — đặt cạnh nhau để đối chiếu vi mô
    c3_left, c3_right = st.columns(2, gap="medium")
    with c3_left:
        st.markdown("##### 🔴 Top 10 Camera Chậm Nhất")
        render_top_slowest(df)
    with c3_right:
        st.markdown("##### 🚗 Top 10 Camera Đông Nhất")
        render_top_busiest(df)

    # ── Tầng 4: Analytical Drill-down ─────────────────────────────────────
    # Tóm tắt theo Quận + Rush vs Off-Peak — cùng chiều phân tích "Quận"
    c4_left, c4_right = st.columns([5, 5], gap="medium")
    with c4_left:
        st.markdown("##### 📋 Tóm tắt theo Quận")
        render_district_summary(df)
    with c4_right:
        st.markdown("##### ⏰ Rush Hour vs Off-Peak")
        render_rush_vs_offpeak(rush_df)


# ─── Entry Point ────────────────────────────────────────────────────────────
days, selected_districts, end_date = sidebar_nav()

st.markdown(f"""
<div style="margin-bottom:1.5rem;">
    <div class="dashboard-title">
        <span style="font-size:1.8rem;margin-right:0.5rem;">{DASHBOARD['icon']}</span>
        {DASHBOARD['id']} — {DASHBOARD['title']}
    </div>
    <div class="dashboard-subtitle">{DASHBOARD['description']}</div>
    <div class="refresh-indicator">
        <span class="refresh-dot"></span>
        Auto-refresh: {DASHBOARD['refresh']} | Cache TTL: {TTL}s
    </div>
</div>
""", unsafe_allow_html=True)

with st.spinner("Đang tải dữ liệu..."):
    @st.cache_data(ttl=TTL)
    def load_data(days, end_date_str):
        end = datetime.fromisoformat(end_date_str) if end_date_str else None
        return run_query(get_traffic_events(days=days, end_date=end), ttl=TTL)

    @st.cache_data(ttl=TTL)
    def load_rush(days, end_date_str):
        end = datetime.fromisoformat(end_date_str) if end_date_str else None
        return run_query(get_rush_offpeak_query(days=days, end_date=end), ttl=TTL)

    @st.cache_data(ttl=TTL)
    def load_prev(days, end_date_str):
        end = datetime.fromisoformat(end_date_str) if end_date_str else None
        return run_query(get_traffic_events(days=days * 2, end_date=end), ttl=TTL)

    end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S") if end_date else None

    df = load_data(days, end_date_str)
    rush_df = load_rush(days, end_date_str)

    df_prev = None
    if df is not None and not df.empty:
        df_prev = load_prev(days, end_date_str)
        if df_prev is not None and not df_prev.empty:
            df_prev["slot"] = pd.to_datetime(df_prev["slot"])
            cutoff = pd.to_datetime(df["slot"]).max()
            df_prev = df_prev[df_prev["slot"] < cutoff]

if df is not None and not df.empty:
    render_layout(df, rush_df if rush_df is not None else None, df_prev)
else:
    st.warning("Không có dữ liệu. Vui lòng kiểm tra kết nối Trino và đảm bảo có data trong bảng `traffic.events`.")
    st.info("Chạy thử: `docker exec -it trino trino --server http://trino:8080 --catalog iceberg --schema traffic` để kiểm tra.")
