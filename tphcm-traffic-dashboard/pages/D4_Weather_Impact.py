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

st.set_page_config(page_title="D4 - Weather Impact", page_icon="🌦️", layout="wide")

DASHBOARD = {
    "id": "D4",
    "title": "Weather Impact",
    "icon": "🌦️",
    "description": "Phân tích tương quan thời tiết × giao thông: lưu lượng, tốc độ, tác động theo quận.",
    "refresh": "15 phút",
    "color": "#9B59B6",
}
TTL = ttl_for_dashboard("D4")

with open(Path(__file__).parent.parent / "styles" / "custom.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────
def sidebar_nav():
    with st.sidebar:
        st.markdown("### 🌦️ Weather Impact")
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
        weather_opts = ["Clear", "Clouds", "Rain", "Drizzle", "Mist", "Thunderstorm"]
        weather_filter = st.multiselect(
            "Thời tiết hiển thị",
            options=weather_opts,
            default=weather_opts,
        )
        st.markdown("---")
        st.markdown(f"**Cache TTL:** {TTL}s")

        if specific_date is not None:
            end_date = datetime.combine(specific_date, datetime.max.time())
            end_date = end_date + timedelta(days=1)
        else:
            end_date = None
        end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S") if end_date else None
        return days, weather_filter, end_date_str


# ─── KPI Row ────────────────────────────────────────────────────────────────
def kpi_row(df, weather_filter):
    df_w = df[df["weather_main"].isin(weather_filter)] if weather_filter else df

    most_common = df_w["weather_main"].mode()[0] if not df_w["weather_main"].isna().all() else "N/A"

    rain_df  = df_w[df_w["weather_main"].isin(["Rain", "Thunderstorm", "Drizzle"])]
    clear_df = df_w[df_w["weather_main"].isin(["Clear", "Clouds"])]

    rain_vol   = rain_df["vehicles_count"].mean()  if not rain_df.empty  else 0
    clear_vol  = clear_df["vehicles_count"].mean() if not clear_df.empty else 0
    vol_diff   = rain_vol - clear_vol

    avg_temp = df_w["weather_temp"].mean()

    rain_spd  = rain_df["speed_avg_kmh"].mean()  if not rain_df.empty  else 0
    clear_spd = clear_df["speed_avg_kmh"].mean() if not clear_df.empty else 0
    spd_diff  = rain_spd - clear_spd

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Thời tiết phổ biến", most_common)
    with c2:
        st.metric("Nhiệt độ TB", f"{avg_temp:.1f} °C" if pd.notna(avg_temp) else "N/A")
    with c3:
        st.metric(
            "Lưu lượng khi mưa",
            f"{rain_vol:.1f} xe/slot",
            help="Trung bình số xe mỗi 5 phút khi trời mưa/dông",
        )
    with c4:
        st.metric(
            "Mưa vs Trời trong",
            f"{vol_diff:+.1f} xe",
            help="Chênh lệch lưu lượng: mưa trừ trời trong (số dương = mưa đông hơn)",
        )


# ─── Fix 1: Weather Impact — Tách Volume (Bar) và Speed (Bar) riêng ─────────
# Trước đây ghép volume + speed×2 trên 1 chart → khó đọc, đơn vị lẫn lộn.
# Giờ: 2 chart cạnh nhau, mỗi chart 1 metric rõ ràng.
def weather_impact(df, weather_filter):
    import plotly.graph_objects as go

    df_w = df[df["weather_main"].isin(weather_filter)] if weather_filter else df

    weather_stats = (
        df_w.groupby("weather_main")
        .agg(
            Avg_Vehicles=("vehicles_count", "mean"),
            Avg_Speed=("speed_avg_kmh", "mean"),
            Std_Speed=("speed_avg_kmh", "std"),
        )
        .reset_index()
        .sort_values("Avg_Vehicles", ascending=False)
    )

    # — Chart trái: Lưu lượng —
    vol_colors = []
    for v in weather_stats["Avg_Vehicles"]:
        if v < 60:   vol_colors.append(C["danger"])
        elif v < 80:  vol_colors.append(C["warning"])
        else:          vol_colors.append(C["success"])

    fig_vol = go.Figure(go.Bar(
        x=weather_stats["weather_main"],
        y=weather_stats["Avg_Vehicles"],
        marker_color=vol_colors,
        text=[f"{v:.1f}" for v in weather_stats["Avg_Vehicles"]],
        textposition="outside",
        textfont=dict(color=C["text"], size=12, family="Arial"),
        hovertemplate="<b>%{x}</b><br>Lưu lượng: %{y:.1f} xe/slot<extra></extra>",
    ))
    apply_dark_template(fig_vol)
    fig_vol.update_layout(
        title=dict(text="Lưu lượng TB theo Thời tiết", font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Thời tiết",
        yaxis_title="Xe TB / slot",
        height=380,
        showlegend=False,
        margin=dict(l=40, r=30, b=60, t=50),
        xaxis=dict(tickfont=dict(size=11, color=C["text"])),
        yaxis=dict(gridcolor="#2A3042"),
    )

    # — Chart phải: Tốc độ (với error bar và ngưỡng kẹt) —
    spd_colors = []
    for v in weather_stats["Avg_Speed"]:
        if v < 15:   spd_colors.append(C["danger"])
        elif v < 25: spd_colors.append(C["warning"])
        else:          spd_colors.append(C["success"])

    fig_spd = go.Figure(go.Bar(
        x=weather_stats["weather_main"],
        y=weather_stats["Avg_Speed"],
        marker_color=spd_colors,
        error_y=dict(
            type="data",
            array=weather_stats["Std_Speed"].fillna(0).round(1),
            visible=True,
            color=C["muted"],
            thickness=1.5,
        ),
        text=[f"{v:.1f}" for v in weather_stats["Avg_Speed"]],
        textposition="outside",
        textfont=dict(color=C["text"], size=12, family="Arial"),
        hovertemplate="<b>%{x}</b><br>Tốc độ: %{y:.1f} km/h<br>Std: ±%{error_y.array:.1f}<extra></extra>",
    ))

    # Ngưỡng kẹt
    fig_spd.add_hline(
        y=15, line_dash="dash", line_color=C["danger"], line_width=1.5,
        annotation_text="Ngưỡng kẹt (15 km/h)",
        annotation_font_color=C["danger"],
        annotation_font_size=10,
    )

    apply_dark_template(fig_spd)
    fig_spd.update_layout(
        title=dict(text="Tốc độ TB theo Thời tiết", font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
        xaxis_title="Thời tiết",
        yaxis_title="Tốc độ TB (km/h)",
        height=380,
        showlegend=False,
        margin=dict(l=40, r=30, b=60, t=50),
        xaxis=dict(tickfont=dict(size=11, color=C["text"])),
        yaxis=dict(gridcolor="#2A3042"),
    )

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.plotly_chart(fig_vol, use_container_width=True)
    with c2:
        st.plotly_chart(fig_spd, use_container_width=True)


# ─── Fix 2: Weather × District Heatmap — Đổi sang SPEED + thang màu đúng ─────
# Trước: thang 20-160 không rõ đơn vị, màu đỏ = cao → ngược cảm giác
# Giờ: thang là TỐC ĐỘ (km/h), màu đỏ = CHẬM = nguy hiểm
def weather_district_heatmap(df, weather_filter):
    import plotly.graph_objects as go

    df_w = df[df["weather_main"].isin(weather_filter)] if weather_filter else df

    pivot = (
        df_w.groupby(["district", "weather_main"])["speed_avg_kmh"]
        .mean()
        .reset_index()
    )
    pivot_table = pivot.pivot(index="district", columns="weather_main", values="speed_avg_kmh")

    # Sort rows: slowest districts on top
    pivot_table = pivot_table.loc[pivot_table.mean(axis=1).sort_values().index]

    fig = go.Figure(data=go.Heatmap(
        x=pivot_table.columns.tolist(),
        y=pivot_table.index.tolist(),
        z=pivot_table.values.tolist(),
        # Thang màu: đỏ = chậm, xanh = nhanh
        colorscale=[
            [0.00,  "#B71C1C"],  # < 10 km/h → đỏ sậm
            [0.20,  "#E53935"],  # 10-15     → đỏ
            [0.35,  "#FF8F00"],  # 15-20     → cam
            [0.50,  "#F9A825"],  # 20-25     → vàng
            [0.65,  "#43A047"],  # 25-30     → xanh
            [0.80,  "#2E7D32"],  # 30-35     → xanh đậm
            [1.00,  "#1B5E20"],  # > 35      → xanh rất đậm
        ],
        zmin=0, zmax=40,
        colorbar=dict(
            title=dict(text="km/h", font=dict(color=C["text"])),
            tickfont=dict(color=C["text"], size=10),
            ticks="outside",
        ),
        hovertemplate="<b>%{y}</b><br>%{x}<br>Tốc độ: %{z:.1f} km/h<extra></extra>",
    ))

    # Vạch ranh giới kẹt
    fig.add_vline(
        x=len(pivot_table.columns) - 0.5,
        line_color="rgba(255,255,255,0)",
    )

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(
            text="Tốc độ TB theo Quận × Thời tiết (km/h) — Đỏ: chậm, Xanh: nhanh",
            font=dict(size=13, color=C["text"]),
            x=0, xanchor="left",
        ),
        xaxis_title="Thời tiết",
        yaxis_title="Quận",
        height=420,
        margin=dict(l=10, r=10, b=60, t=60),
        xaxis=dict(
            tickfont=dict(size=11, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 3: Scatter Nhiệt độ → Scatter có confounding label ─────────────────
def temp_vs_traffic(df, weather_filter):
    import plotly.graph_objects as go

    df_w = df[df["weather_main"].isin(weather_filter)] if weather_filter else df
    temp_df = df_w[df_w["weather_temp"].notna()].copy()

    agg = (
        temp_df.groupby(["weather_temp", "weather_main"])["vehicles_count"]
        .mean()
        .reset_index()
        .rename(columns={"vehicles_count": "avg_vehicles"})
    )
    agg["count"] = (
        temp_df.groupby(["weather_temp", "weather_main"])["vehicles_count"]
        .count()
        .reset_index()["vehicles_count"]
    )

    weather_palette = {
        "Clear":       "#F39C12",
        "Clouds":      "#95A5A6",
        "Rain":        "#3498DB",
        "Drizzle":     "#9BC4E2",
        "Mist":        "#B0BEC5",
        "Thunderstorm":"#7F8C8D",
    }

    fig = go.Figure()
    for weather in agg["weather_main"].unique():
        sub = agg[agg["weather_main"] == weather]
        color = weather_palette.get(weather, C["primary"])
        fig.add_trace(go.Scatter(
            x=sub["weather_temp"],
            y=sub["avg_vehicles"],
            name=weather,
            mode="markers",
            marker=dict(
                size=sub["count"] / sub["count"].max() * 30 + 8,
                color=color,
                opacity=0.75,
                line=dict(width=1, color="rgba(255,255,255,0.3)"),
            ),
            hovertemplate=f"<b>{weather}</b><br>Nhiệt: %{{x}}°C<br>Xe TB: %{{y:.1f}}<extra></extra>",
        ))

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(
            text="Nhiệt độ vs Lưu lượng Giao thông",
            font=dict(size=13, color=C["text"]),
            x=0, xanchor="left",
        ),
        xaxis_title="Nhiệt độ (°C)",
        yaxis_title="Xe trung bình / slot",
        height=380,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=40, r=30, b=60, t=50),
        xaxis=dict(gridcolor="#2A3042"),
        yaxis=dict(gridcolor="#2A3042"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 4: Humidity Impact — Tách weather bar ra riêng ────────────────────
# Trước: dùng bar_chart helper với color="weather_main" → mỗi cột 1 màu, không so sánh được
# Giờ: Grouped bar — mỗi weather có 2 cột (volume + humidity) để thấy correlation
def humidity_impact(df, weather_filter):
    import plotly.graph_objects as go

    df_w = df[df["weather_main"].isin(weather_filter)] if weather_filter else df

    weather_stats = (
        df_w.groupby("weather_main")
        .agg(
            Avg_Vehicles=("vehicles_count", "mean"),
            Avg_Humidity=("weather_humidity", "mean"),
        )
        .reset_index()
        .sort_values("Avg_Vehicles", ascending=False)
    )

    # Normalize humidity về cùng scale (0-120) để so sánh
    hum_max = weather_stats["Avg_Humidity"].max()
    hum_min = weather_stats["Avg_Humidity"].min()
    hum_range = hum_max - hum_min if hum_max != hum_min else 1
    hum_scaled = (weather_stats["Avg_Humidity"] - hum_min) / hum_range * weather_stats["Avg_Vehicles"].max()

    weather_palette = {
        "Clear":       "#F39C12",
        "Clouds":      "#95A5A6",
        "Rain":        "#3498DB",
        "Drizzle":     "#9BC4E2",
        "Mist":        "#B0BEC5",
        "Thunderstorm":"#7F8C8D",
    }
    bar_colors = [weather_palette.get(w, C["primary"]) for w in weather_stats["weather_main"]]

    fig = go.Figure()

    # Bar: Lưu lượng
    fig.add_trace(go.Bar(
        name="Lưu lượng (xe/slot)",
        x=weather_stats["weather_main"],
        y=weather_stats["Avg_Vehicles"],
        marker_color=bar_colors,
        text=[f"{v:.0f}" for v in weather_stats["Avg_Vehicles"]],
        textposition="outside",
        textfont=dict(color=C["text"], size=11, family="Arial"),
        hovertemplate="<b>%{x}</b><br>Lưu lượng: %{y:.1f} xe/slot<br>Độ ẩm: %{customdata:.0f}%<extra></extra>",
        customdata=weather_stats["Avg_Humidity"],
    ))

    # Line: Độ ẩm (normalized)
    fig.add_trace(go.Scatter(
        name="Độ ẩm TB (%, scaled)",
        x=weather_stats["weather_main"],
        y=hum_scaled,
        mode="lines+markers",
        line=dict(color="#4ECDC4", width=2.5, dash="dash"),
        marker=dict(size=8, color="#4ECDC4"),
        text=[f"{v:.0f}%" for v in weather_stats["Avg_Humidity"]],
        textposition="top center",
        textfont=dict(color="#4ECDC4", size=11, family="Arial"),
        hovertemplate="<b>%{x}</b><br>Độ ẩm: %{text}<extra></extra>",
        yaxis="y2",
    ))

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(
            text="Lưu lượng và Độ Ẩm TB theo Thời tiết",
            font=dict(size=14, color=C["text"]),
            x=0, xanchor="left",
        ),
        height=380,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=40, r=60, b=60, t=50),
        xaxis=dict(tickfont=dict(size=11, color=C["text"])),
        yaxis=dict(
            title=dict(text="Xe TB / slot", font=dict(color=C["text"], size=11)),
            gridcolor="#2A3042",
        ),
        yaxis2=dict(
            title=dict(text="Độ ẩm TB (%)", font=dict(color="#4ECDC4", size=11)),
            anchor="free",
            overlaying="y",
            side="right",
            position=0.97,
            showgrid=False,
            tickfont=dict(color="#4ECDC4"),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Entry Point ───────────────────────────────────────────────────────────
days, weather_filter, end_date_str = sidebar_nav()

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

with st.spinner("Đang tải dữ liệu thời tiết..."):
    @st.cache_data(ttl=TTL)
    def load_weather(days, end_date_str):
        end = datetime.fromisoformat(end_date_str) if end_date_str else None
        return run_query(get_traffic_events(days=days, end_date=end), ttl=TTL)

    df = load_weather(days, end_date_str)

if df is not None and not df.empty:
    df["slot"] = pd.to_datetime(df["slot"])
    df["hour"] = df["slot"].dt.hour

    # KPI row
    st.markdown("##### 📊 Chỉ số Thời tiết")
    kpi_row(df, weather_filter)

    st.markdown("---")

    # Row 1: Volume + Speed (tách riêng, cùng hàng)
    st.markdown("##### 📦 Lưu lượng & Tốc độ theo Thời tiết")
    weather_impact(df, weather_filter)

    st.markdown("---")

    # Row 2: Heatmap Speed × District (full width)
    st.markdown("##### 🗺️ Tốc độ theo Quận × Thời tiết")
    weather_district_heatmap(df, weather_filter)

    st.markdown("---")

    # Row 3: Scatter Nhiệt độ + Humidity Combo (thay Wind)
    st.markdown("##### 🌡️ Nhiệt độ, Độ Ẩm & Lưu lượng")
    c3_1, c3_2 = st.columns(2, gap="medium")
    with c3_1:
        st.markdown("###### Nhiệt độ vs Lưu lượng")
        temp_vs_traffic(df, weather_filter)
    with c3_2:
        st.markdown("###### Lưu lượng & Độ Ẩm theo Thời tiết")
        humidity_impact(df, weather_filter)
else:
    st.warning("Không có dữ liệu thời tiết.")
