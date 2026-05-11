import streamlit as st
import pandas as pd
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.database import run_query, get_traffic_events
from utils.chart_utils import apply_dark_template
from utils.config import COLOR_PALETTE as C
from utils.cache_utils import ttl_for_dashboard

st.set_page_config(page_title="D3 - Speed Analysis", page_icon="⚡", layout="wide")

DASHBOARD = {
    "id": "D3",
    "title": "Speed Analysis",
    "icon": "⚡",
    "description": "Phân tích tốc độ giao thông: phân bố, xu hướng, chỉ số kẹt xe theo quận — có ngưỡng kẹt 15 km/h.",
    "refresh": "10 phút",
    "color": "#F39C12",
}
TTL = ttl_for_dashboard("D3")

with open(Path(__file__).parent.parent / "styles" / "custom.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────
def _load_district_opts(days, end_date=None):
    return run_query(get_traffic_events(days=days, end_date=end_date), ttl=TTL)

def sidebar_nav():
    with st.sidebar:
        st.markdown("### ⚡ Speed Analysis")
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

        if specific_date is not None:
            end_date = datetime.combine(specific_date, datetime.max.time())
            end_date = end_date + timedelta(days=1)
        else:
            end_date = None

        raw = _load_district_opts(days, end_date)
        if raw is not None and not raw.empty:
            all_d = sorted(raw["district"].dropna().unique().tolist())
            top5 = (
                raw.groupby("district")["speed_avg_kmh"]
                .mean()
                .sort_values(ascending=True)
                .head(5)
                .index.tolist()
            )
        else:
            all_d, top5 = [], []
        selected = st.multiselect(
            "Quận (so sánh)",
            options=all_d,
            default=top5,
        )
        st.markdown("---")
        st.markdown(f"**Cache TTL:** {TTL}s")
        end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S") if end_date else None
        return days, selected, end_date_str


# ─── Fix 1: KPI Row ────────────────────────────────────────────────────────
# - Thay MIN() tuyệt đối bằng Percentile-5 (P5): loại bỏ noise từ các
#   camera ghi nhận tốc độ cực thấp bất thường (rẽ xe, dừng đèn).
def kpi_row(df):
    speed_vals = df["speed_avg_kmh"].dropna()

    avg_spd    = speed_vals.mean()
    p5_spd     = speed_vals.quantile(0.05)
    congested  = (speed_vals < 15).sum()
    total      = len(speed_vals)
    rush_mask  = df["hour"].isin([7, 8, 9, 17, 18, 19])
    rush_avg   = df.loc[rush_mask, "speed_avg_kmh"].mean() if rush_mask.any() else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Tốc độ TB", f"{avg_spd:.1f} km/h")
    with c2:
        st.metric("P5 — Tốc độ đáy", f"{p5_spd:.1f} km/h",
                   help="Percentile thứ 5: chỉ 5% quan sát có tốc độ thấp hơn mức này. Ít noise hơn MIN().")
    with c3:
        st.metric("Slots kẹt xe", f"{congested:,} ({congested/total*100:.0f}%)",
                   help="Số slot có tốc độ < 15 km/h")
    with c4:
        st.metric("Tốc độ Rush Hour", f"{rush_avg:.1f} km/h")


# ─── Fix 2: Phân bố Tốc độ (Histogram) ─────────────────────────────────────
# - Bin size = 5 (0, 5, 10, 15, 20...) để vạch chia trùng mốc 15 km/h
# - vline ngưỡng kẹt cắt ranh giới giữa 2 cột, không cắt ngang 1 cột
def speed_distribution(df):
    import plotly.graph_objects as go

    speed_df = df[df["speed_avg_kmh"].notna() & (df["speed_avg_kmh"] > 0)]["speed_avg_kmh"]

    # Custom bins: 0, 5, 10, 15, 20, 25, 30, 40, 50, 60
    x_bins = list(range(0, 61, 5))

    fig = go.Figure(data=[go.Histogram(
        x=speed_df,
        xbins=dict(
            start=0,
            end=60,
            size=5,
        ),
        marker_color=C["primary"],
        hovertemplate="Tốc độ: %{x}–%{xEnd} km/h<br>Đếm: %{y}<extra></extra>",
    )])

    # Vạch đỏ ngưỡng kẹt tại x=15 — trùng ranh giới bin
    fig.add_vline(
        x=15, line_dash="dash", line_color=C["danger"], line_width=2,
        annotation_text="Ngưỡng kẹt (15 km/h)",
        annotation_font_color=C["danger"],
        annotation_font_size=11,
        annotation_xanchor="left",
    )

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Phân bố Tốc độ", font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Tốc độ (km/h)",
        yaxis_title="Số lượng quan sát",
        height=420,
        xaxis=dict(
            tickvals=x_bins,
            ticktext=[str(x) for x in x_bins],
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(gridcolor="#2A3042"),
        margin=dict(l=40, r=30, b=60, t=50),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 3: Tốc độ theo Thời gian → Heatmap ───────────────────────────────
# - Thay line chart 20 đường chồng chéo bằng heatmap: trục X = giờ,
#   trục Y = quận, màu = tốc độ TB. Đọc dễ hơn rất nhiều.
# - Sidebar filter chỉ hiển thị các quận được chọn
def speed_trend_heatmap(df, selected_districts):
    import plotly.graph_objects as go

    if selected_districts:
        df = df[df["district"].isin(selected_districts)]

    heat_df = (
        df.groupby(["hour", "district"])["speed_avg_kmh"]
        .mean()
        .reset_index()
    )
    pivot = heat_df.pivot(index="district", columns="hour", values="speed_avg_kmh")

    # Sort rows by avg speed (slowest on top)
    pivot = pivot.loc[pivot.mean(axis=1).sort_values().index]

    # Nhãn giờ: mỗi 3 tiếng
    hour_labels = {h: str(h) if h % 3 == 0 else "" for h in range(24)}

    fig = go.Figure(data=go.Heatmap(
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        z=pivot.values.tolist(),
        colorscale=[
            [0.0,  C["danger"]],      # < 15 km/h → đỏ
            [0.25, "#FF9F43"],        # 15-20     → cam
            [0.5,  C["warning"]],     # 20-25     → vàng
            [0.75, C["success"]],     # 25-35     → xanh
            [1.0,  "#27AE60"],        # > 35      → xanh đậm
        ],
        zmin=0, zmax=45,
        colorbar=dict(
            title=dict(text="km/h", font=dict(color=C["text"])),
            tickfont=dict(color=C["text"], size=10),
        ),
        hovertemplate="<b>%{y}</b><br>Giờ: %{x}:00<br>Tốc độ: %{z:.1f} km/h<extra></extra>",
    ))

    # Vạch kẹt 15 km/h — chỉ đánh dấu ranh giới
    fig.add_vline(
        x=14.5, line_dash="dash", line_color="rgba(255,255,255,0.5)", line_width=1.5,
    )

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Tốc độ TB theo Giờ × Quận (Heatmap)", font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Giờ trong ngày",
        yaxis_title="Quận",
        height=420,
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(24)),
            ticktext=[str(h) if h % 3 == 0 else "" for h in range(24)],
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        margin=dict(l=10, r=10, b=60, t=50),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 4: Chỉ số Kẹt xe theo Quận (Rush Hour) ───────────────────────────
# - Nhãn dữ liệu làm tròn 1 chữ số thập phân
def congestion_index(df):
    import plotly.graph_objects as go

    rush_df = df[df["hour"].isin([7, 8, 9, 17, 18, 19])]

    congestion = (
        rush_df.groupby("district")["speed_avg_kmh"]
        .mean()
        .reset_index()
        .rename(columns={"speed_avg_kmh": "avg_speed"})
        .sort_values("avg_speed", ascending=True)
    )

    colors = []
    for v in congestion["avg_speed"]:
        if v < 15:   colors.append(C["danger"])
        elif v < 25: colors.append(C["warning"])
        else:         colors.append(C["success"])

    fig = go.Figure(go.Bar(
        x=congestion["district"],
        y=congestion["avg_speed"],
        marker_color=colors,
        text=[f"{v:.1f}" for v in congestion["avg_speed"]],
        textposition="outside",
        textfont=dict(color=C["text"], size=11, family="Arial"),
        hovertemplate="<b>%{x}</b><br>Tốc độ TB: %{y:.1f} km/h<extra></extra>",
    ))

    # Ngưỡng kẹt 15 km/h
    fig.add_shape(
        type="line",
        x0=-0.5, x1=len(congestion) - 0.5,
        y0=15, y1=15,
        line=dict(color=C["danger"], width=2, dash="dash"),
    )
    fig.add_annotation(
        x=len(congestion) - 0.5, y=15,
        text="Ngưỡng kẹt (15 km/h)",
        showarrow=False,
        font=dict(color=C["danger"], size=11),
        xanchor="right",
        yanchor="bottom",
        yshift=5,
    )

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(text="Chỉ số Kẹt xe theo Quận (Rush Hour)", font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Quận",
        yaxis_title="Tốc độ TB (km/h)",
        height=420,
        showlegend=False,
        xaxis=dict(tickfont=dict(size=10, color=C["text"]), tickangle=45),
        yaxis=dict(gridcolor="#2A3042"),
        margin=dict(l=40, r=40, b=80, t=50),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 5: Tốc độ TB theo Giờ trong Ngày (Line) ─────────────────────────
# - Hiển thị tất cả quận được chọn với MA(3) để mượt
# - Sidebar filter kiểm soát độ phức tạp
# - Ghi chú: nếu Quận 5 luôn ~30-35 km/h → cảnh báo kiểm tra camera
def speed_by_hour(df, selected_districts):
    import plotly.graph_objects as go

    if selected_districts:
        df = df[df["district"].isin(selected_districts)]

    hourly = (
        df.groupby(["hour", "district"])["speed_avg_kmh"]
        .mean()
        .reset_index()
    )

    # MA(3) — trượt 3 giờ liền kề để mượt đường
    hourly = hourly.sort_values(["district", "hour"])
    hourly["speed_ma3"] = hourly.groupby("district")["speed_avg_kmh"].transform(
        lambda x: x.rolling(3, center=True, min_periods=1).mean()
    )

    palette = C["chart_colors"]

    fig = go.Figure()
    for i, district in enumerate(sorted(hourly["district"].unique())):
        sub = hourly[hourly["district"] == district].sort_values("hour")
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatter(
            x=sub["hour"],
            y=sub["speed_ma3"],
            name=district,
            mode="lines",
            line=dict(color=color, width=2.5),
            hovertemplate=f"<b>{district}</b><br>Giờ: %{{x}}:00<br>Tốc độ: %{{y:.1f}} km/h<extra></extra>",
        ))

    # Ngưỡng kẹt
    fig.add_hline(
        y=15, line_dash="dash", line_color=C["danger"], line_width=1.5,
        annotation_text="Ngưỡng kẹt (15 km/h)",
        annotation_font_color=C["danger"],
        annotation_font_size=10,
    )

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(
            text="Tốc độ TB theo Giờ (MA3 — trượt 3 giờ) · Quận × Giờ cao điểm nổi bật trên heatmap tầng 2",
            font=dict(size=13, color=C["text"]),
            x=0, xanchor="left",
        ),
        xaxis_title="Giờ (0–23)",
        yaxis_title="Tốc độ TB (km/h)",
        height=420,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=10),
            bgcolor="rgba(0,0,0,0)",
            yanchor="top", y=0.99,
            xanchor="left", x=1.02,
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(0, 24, 2)),
            ticktext=[str(h) for h in range(0, 24, 2)],
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(gridcolor="#2A3042"),
        margin=dict(l=40, r=150, b=60, t=60),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Bonus: Cảnh báo chất lượng dữ liệu ───────────────────────────────────
def data_quality_alert(df, selected_districts):
    """Nếu một quận có tốc độ TB luôn > 35 km/h mọi giờ → cảnh báo camera."""
    if selected_districts:
        df = df[df["district"].isin(selected_districts)]

    hourly = df.groupby(["hour", "district"])["speed_avg_kmh"].mean().reset_index()
    suspicious = (
        hourly.groupby("district")["speed_avg_kmh"]
        .agg(["mean", "std"])
        .reset_index()
    )
    suspicious["is_suspicious"] = (suspicious["mean"] > 35) & (suspicious["std"] < 3)
    flags = suspicious[suspicious["is_suspicious"]]["district"].tolist()

    if flags:
        st.warning(
            f"**Cảnh báo dữ liệu:** Quận {', '.join(flags)} có tốc độ trung bình "
            f"> 35 km/h với độ lệch chuẩn rất thấp qua mọi khung giờ. "
            f"Cân nhắc kiểm tra camera thuộc khu vực này."
        )


# ─── Entry Point ───────────────────────────────────────────────────────────
days, selected_districts, end_date_str = sidebar_nav()

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

with st.spinner("Đang tải dữ liệu tốc độ..."):
    @st.cache_data(ttl=TTL)
    def load_speed(days, end_date_str):
        end = datetime.fromisoformat(end_date_str) if end_date_str else None
        return run_query(get_traffic_events(days=days, end_date=end), ttl=TTL)

    df = load_speed(days, end_date_str)

if df is not None and not df.empty:
    df["slot"] = pd.to_datetime(df["slot"])
    df["hour"] = df["slot"].dt.hour

    # KPI row
    st.markdown("##### 📊 Chỉ số Tốc độ")
    kpi_row(df)

    st.markdown("---")

    # Tầng 1: Phân bố + Xu hướng theo giờ (Heatmap)
    st.markdown("##### 🔥 Phân bố & Xu hướng Tốc độ")
    c1_1, c1_2 = st.columns(2, gap="medium")
    with c1_1:
        st.markdown("###### Phân bố Tốc độ (Bin 5 km/h)")
        speed_distribution(df)
    with c1_2:
        st.markdown("###### Tốc độ theo Giờ × Quận (Heatmap)")
        speed_trend_heatmap(df, selected_districts)

    st.markdown("---")

    # Tầng 2: Chỉ số Kẹt xe theo Quận
    st.markdown("##### 🚦 Chỉ số Kẹt xe theo Quận (Rush Hour)")
    congestion_index(df)

    st.markdown("---")

    # Tầng 3: Tốc độ MA theo giờ + Cảnh báo dữ liệu
    st.markdown("##### 📈 Tốc độ trung bình theo Giờ (MA3)")
    speed_by_hour(df, selected_districts)
    data_quality_alert(df, selected_districts)
else:
    st.warning("Không có dữ liệu tốc độ.")
