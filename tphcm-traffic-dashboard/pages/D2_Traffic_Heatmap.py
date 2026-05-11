import streamlit as st
import pandas as pd
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.database import run_query, get_heatmap_hourly_query
from utils.chart_utils import apply_dark_template
from utils.config import COLOR_PALETTE as C
from utils.cache_utils import ttl_for_dashboard

st.set_page_config(page_title="D2 - Traffic Heatmap", page_icon="🔥", layout="wide")

DASHBOARD = {
    "id": "D2",
    "title": "Traffic Heatmap",
    "icon": "🔥",
    "description": "Phân tích chu kỳ giao thông: heatmap giờ × quận/camera, xu hướng theo ngày trong tuần.",
    "refresh": "15 phút",
    "color": "#E94F37",
}
TTL = ttl_for_dashboard("D2")

with open(Path(__file__).parent.parent / "styles" / "custom.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────
def _load_district_opts(days, end_date=None):
    return run_query(get_heatmap_hourly_query(days=days, end_date=end_date), ttl=TTL)

def sidebar_nav():
    with st.sidebar:
        st.markdown("### 🔥 Traffic Heatmap")
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

        days = st.selectbox("Số ngày", [7, 14, 30], index=0,
                            format_func=lambda x: f"{x} ngày")
        day_type = st.selectbox("Loại ngày", ["Tất cả", "Workday", "Weekend"])

        if specific_date is not None:
            end_date = datetime.combine(specific_date, datetime.max.time())
            end_date = end_date + timedelta(days=1)
        else:
            end_date = None

        raw = _load_district_opts(days, end_date)
        if raw is not None and not raw.empty:
            all_d = sorted(raw["district"].dropna().unique().tolist())
            top5 = (
                raw.groupby("district")["avg_vehicles"]
                .mean()
                .sort_values(ascending=False)
                .head(5)
                .index.tolist()
            )
        else:
            all_d, top5 = [], []

        selected = st.multiselect(
            "Quận (xu hướng theo ngày)",
            options=all_d,
            default=top5,
        )
        st.markdown("---")
        st.markdown(f"**Cache TTL:** {TTL}s")
        end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S") if end_date else None
        return days, day_type, selected, end_date_str


# ─── Fix 1: Heatmap District × Hour ─────────────────────────────────────────
# - Y-axis sort: tổng lưu lượng giảm dần (quận đông nhất trên)
# - Hiển thị nhãn giờ rõ ràng
def heatmap_district_hour(df):
    import plotly.graph_objects as go

    workday_df = df[df["day_type"] == "Workday"]
    pivot = (
        workday_df.groupby(["district", "hour"])["avg_vehicles"]
        .mean()
        .reset_index()
    )
    pivot_table = pivot.pivot(index="district", columns="hour", values="avg_vehicles")

    # Sort Y-axis by total traffic (highest on top)
    pivot_table = pivot_table.loc[pivot_table.sum(axis=1).sort_values(ascending=False).index]

    # Nhãn giờ: chỉ hiển thị giờ chẵn
    even_hours = [h for h in range(24) if h % 2 == 0]
    ticktext = [str(h) for h in range(24)]

    fig = go.Figure(data=go.Heatmap(
        x=pivot_table.columns.tolist(),
        y=pivot_table.index.tolist(),
        z=pivot_table.values.tolist(),
        colorscale="YlOrRd",
        reversescale=True,
        colorbar=dict(
            title=dict(text="Xe TB/slot", font=dict(color=C["text"])),
            tickfont=dict(color=C["text"]),
        ),
        hovertemplate="<b>%{y}</b><br>Giờ: %{x}:00<br>Xe TB: %{z:.1f}<extra></extra>",
    ))
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Heatmap Quận × Giờ (Workday)", font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Giờ trong ngày",
        yaxis_title="Quận",
        height=420,
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(24)),
            ticktext=ticktext,
            tickfont=dict(size=9, color=C["muted"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        margin=dict(l=10, r=10, b=60, t=50),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 2: Heatmap Camera × Hour ───────────────────────────────────────────
# - X-axis labels horizontal (every 3h: 0,3,6,9,12,15,18,21)
# - Y-axis sort: avg vehicles desc (hottest camera on top)
# - Hover format rõ ràng
def heatmap_camera_hour(df, districts):
    import plotly.graph_objects as go

    if districts:
        df = df[df["district"].isin(districts)]

    camera_df = (
        df.groupby(["display_name", "hour"])["avg_vehicles"]
        .mean()
        .reset_index()
    )
    pivot = camera_df.pivot(index="display_name", columns="hour", values="avg_vehicles")

    # Sort by average traffic (hottest camera top)
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]
    pivot = pivot.head(20)

    # Giờ chẵn mỗi 3 tiếng
    hour_labels = {h: str(h) if h % 3 == 0 else "" for h in range(24)}

    fig = go.Figure(data=go.Heatmap(
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        z=pivot.values.tolist(),
        colorscale="blues",
        reversescale=True,
        colorbar=dict(
            title=dict(text="Xe TB", font=dict(color=C["text"])),
            tickfont=dict(color=C["text"]),
        ),
        hovertemplate="<b>%{y}</b><br>Giờ: %{x}:00<br>Xe TB: %{z:.1f}<extra></extra>",
    ))
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Heatmap Camera × Giờ (Top 20)", font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Giờ trong ngày",
        yaxis_title="Camera",
        height=500,
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(24)),
            ticktext=[str(h) if h % 3 == 0 else "" for h in range(24)],
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(
            tickfont=dict(size=9, color=C["text"]),
            gridcolor="#2A3042",
        ),
        margin=dict(l=10, r=10, b=60, t=50),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 3: Rush Hour Volume by Day of Week ─────────────────────────────────
# - Metric: SUM (tổng phương tiện), không phải AVG
# - Biểu đồ cột chồng có ý nghĩa thống kê khi dùng SUM
# - Hiển thị đủ 7 ngày (Mon-Sun), thêm cột Total
# - Quận nhỏ gom vào "Khác" để giảm quá tải màu sắc
def rush_hour_by_dow(df):
    import plotly.graph_objects as go

    rush_df = df[df["day_type"] == "Workday"]

    # SUM thay vì AVG — tổng phương tiện có ý nghĩa khi dùng stacked bar
    stacked = (
        rush_df.groupby(["day_name", "district"])["avg_vehicles"]
        .sum()
        .reset_index()
    )

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_labels = {"Monday": "T2", "Tuesday": "T3", "Wednesday": "T4",
                  "Thursday": "T5", "Friday": "T6", "Saturday": "T7", "Sunday": "CN"}

    # Gom quận nhỏ vào "Khác" (giữ top 6, phần còn lại = Khác)
    top_districts = (
        stacked.groupby("district")["avg_vehicles"]
        .sum()
        .sort_values(ascending=False)
        .head(6)
        .index.tolist()
    )
    stacked["district"] = stacked["district"].apply(
        lambda d: d if d in top_districts else "Khác"
    )
    stacked = (
        stacked.groupby(["day_name", "district"])["avg_vehicles"]
        .sum()
        .reset_index()
    )

    stacked["day_name"] = pd.Categorical(stacked["day_name"], categories=day_order, ordered=True)
    stacked = stacked.sort_values("day_name")

    # Bảng màu cho top districts
    district_colors = {
        top_districts[0] if len(top_districts) > 0 else "Khác": "#E94F37",
        top_districts[1] if len(top_districts) > 1 else "Khác": "#F39C12",
        top_districts[2] if len(top_districts) > 2 else "Khác": "#4ECDC4",
        top_districts[3] if len(top_districts) > 3 else "Khác": "#3498DB",
        top_districts[4] if len(top_districts) > 4 else "Khác": "#9B59B6",
        top_districts[5] if len(top_districts) > 5 else "Khác": "#1ABC9C",
        "Khác": "#555555",
    }
    bar_colors = [district_colors.get(d, "#555555") for d in stacked["district"]]

    fig = go.Figure()
    for district in stacked["district"].unique():
        sub = stacked[stacked["district"] == district]
        district_color = district_colors.get(district, "#555555")
        hovertemplate_str = (
            f"<b>{district}</b><br>%{{x}}<br>Tổng xe: %{{y:,.0f}}<extra></extra>"
        )
        fig.add_trace(go.Bar(
            name=district,
            x=[day_labels.get(d, d) for d in sub["day_name"]],
            y=sub["avg_vehicles"],
            marker_color=district_color,
            hovertemplate=hovertemplate_str,
        ))

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Lưu lượng Rush Hour theo Ngày (Tổng phương tiện)", font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Ngày trong tuần",
        yaxis_title="Tổng phương tiện",
        barmode="stack",
        height=450,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=10),
            bgcolor="rgba(0,0,0,0)",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.02,
        ),
        margin=dict(l=40, r=140, b=60, t=50),
        xaxis=dict(
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(gridcolor="#2A3042"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 4: Day-of-Week Pattern ──────────────────────────────────────────────
# - Chỉ hiển thị các quận được chọn trong sidebar multiselect (default: Top 5)
# - Mỗi quận 1 màu riêng từ palette, line rõ ràng
def dow_pattern(df, selected_districts):
    import plotly.graph_objects as go

    if selected_districts:
        df = df[df["district"].isin(selected_districts)]

    dow_df = (
        df.groupby(["day_name", "district"])["avg_vehicles"]
        .mean()
        .reset_index()
    )
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_labels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]

    dow_df["day_name"] = pd.Categorical(dow_df["day_name"], categories=day_order, ordered=True)

    palette = C["chart_colors"]

    fig = go.Figure()
    for i, district in enumerate(sorted(dow_df["district"].unique())):
        sub = dow_df[dow_df["district"] == district].sort_values("day_name")
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatter(
            x=[day_labels[day_order.index(d)] for d in sub["day_name"]],
            y=sub["avg_vehicles"],
            name=district,
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=6, color=color),
            hovertemplate=f"<b>{district}</b><br>%{{x}}<br>Xe TB: %{{y:.1f}}<extra></extra>",
        ))

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Xu hướng theo Ngày trong Tuần", font=dict(size=13, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Ngày",
        yaxis_title="Xe trung bình / slot",
        height=420,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=10),
            bgcolor="rgba(0,0,0,0)",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.02,
        ),
        margin=dict(l=40, r=150, b=60, t=60),
        xaxis=dict(tickfont=dict(size=10, color=C["text"]), gridcolor="#2A3042"),
        yaxis=dict(gridcolor="#2A3042"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 5: Weekday vs Weekend ───────────────────────────────────────────────
# - Combo chart: Cột (Lưu lượng) trên trục Y trái + Đường (Tốc độ) trên trục Y phải
# - Y trái: số tuyệt đối (xe/slot), auto-scale 0–tozero
# - Y phải: tốc độ km/h, fixed range 0–40
# - Nhãn cột: inside top (white text), nhãn line: above (amber)
def weekday_vs_weekend(df):
    import plotly.graph_objects as go

    ww_summary = (
        df.groupby(["day_type"])[["avg_vehicles", "avg_speed"]]
        .mean()
        .reset_index()
    )

    workday_row = ww_summary[ww_summary["day_type"] == "Workday"]
    weekend_row = ww_summary[ww_summary["day_type"] == "Weekend"]

    vol_workday  = float(workday_row["avg_vehicles"].values[0]) if len(workday_row) else 0
    vol_weekend  = float(weekend_row["avg_vehicles"].values[0]) if len(weekend_row) else 0
    spd_workday  = float(workday_row["avg_speed"].values[0])    if len(workday_row) else 0
    spd_weekend  = float(weekend_row["avg_speed"].values[0])   if len(weekend_row) else 0

    x_vals = ["Ngày thường\n(T2–T6)", "Cuối tuần\n(T7–CN)"]

    fig = go.Figure()

    # Bar: Lưu lượng — Y trái, nhãn inside top (white text trên cột)
    fig.add_trace(go.Bar(
        name="Lưu lượng (xe TB/slot)",
        x=x_vals,
        y=[vol_workday, vol_weekend],
        marker_color="#3498DB",
        text=[f"{vol_workday:.0f}", f"{vol_weekend:.0f}"],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="#FFFFFF", size=13, family="Arial"),
        hovertemplate="<b>%{x}</b><br>Lưu lượng: %{y:.1f} xe/slot<extra></extra>",
        yaxis="y",
    ))

    # Line: Tốc độ — Y phải, nhãn above
    fig.add_trace(go.Scatter(
        name="Tốc độ TB (km/h)",
        x=x_vals,
        y=[spd_workday, spd_weekend],
        mode="lines+markers+text",
        line=dict(color="#F39C12", width=3),
        marker=dict(size=12, color="#F39C12", symbol="circle"),
        text=[f"{spd_workday:.1f}", f"{spd_weekend:.1f}"],
        textposition="top center",
        textfont=dict(color="#F39C12", size=13, family="Arial"),
        hovertemplate="<b>%{x}</b><br>Tốc độ: %{y:.1f} km/h<extra></extra>",
        yaxis="y2",
    ))

    apply_dark_template(fig)
    fig.update_layout(
        height=420,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=40, r=70, b=80, t=50),
        xaxis=dict(
            tickfont=dict(size=12, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(
            title=dict(text="Xe trung bình / slot", font=dict(color="#3498DB", size=11)),
            gridcolor="#2A3042",
            tickfont=dict(color="#3498DB"),
            rangemode="tozero",
        ),
        yaxis2=dict(
            title=dict(text="Tốc độ (km/h)", font=dict(color="#F39C12", size=11)),
            anchor="free",
            overlaying="y",
            side="right",
            position=0.96,
            range=[0, 40],
            gridcolor="rgba(0,0,0,0)",
            showgrid=False,
            tickfont=dict(color="#F39C12"),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Entry Point ────────────────────────────────────────────────────────────
days, day_type, selected_districts, end_date_str = sidebar_nav()

st.markdown(
    f"""
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
    """,
    unsafe_allow_html=True,
)

with st.spinner("Đang tải dữ liệu heatmap..."):
    @st.cache_data(ttl=TTL)
    def load_heatmap(days, end_date_str):
        end = datetime.fromisoformat(end_date_str) if end_date_str else None
        return run_query(get_heatmap_hourly_query(days=days, end_date=end), ttl=TTL)

    df = load_heatmap(days, end_date_str)

if df is not None and not df.empty:
    if day_type != "Tất cả":
        df = df[df["day_type"] == day_type]

    st.markdown("---")

    # Tầng 1 — Big Picture: Xu hướng Tuần + So sánh Ngày thường / Cuối tuần
    st.markdown("##### 📊 Bức tranh toàn tuần")
    c1_1, c1_2 = st.columns([1.5, 1], gap="medium")
    with c1_1:
        st.markdown("###### Xu hướng theo Ngày")
        dow_pattern(df, selected_districts)
    with c1_2:
        st.markdown("###### Ngày thường vs Cuối tuần")
        weekday_vs_weekend(df)

    st.markdown("---")

    # Tầng 2 — When & Where: Heatmap Quận × Giờ + Heatmap Camera × Giờ
    st.markdown("##### 🔥 Trọng tâm: Giờ cao điểm theo Quận & Camera")
    c2_1, c2_2 = st.columns([1.5, 1], gap="medium")
    with c2_1:
        st.markdown("###### Quận × Giờ (Workday)")
        heatmap_district_hour(df)
    with c2_2:
        st.markdown("###### Camera × Giờ (Top 20)")
        heatmap_camera_hour(df, selected_districts)

    st.markdown("---")

    # Tầng 3 — Deep-dive: Rush Hour breakdown full width
    st.markdown("##### 🚦 Phân tích chi tiết Rush Hour theo Quận")
    rush_hour_by_dow(df)
else:
    st.warning("Không có dữ liệu heatmap.")
