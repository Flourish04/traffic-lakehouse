import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.database import run_query, get_traffic_events
from utils.chart_utils import apply_dark_template
from utils.config import COLOR_PALETTE as C
from utils.cache_utils import ttl_for_dashboard

st.set_page_config(page_title="D5 - Weekly/Monthly Trend", page_icon="📊", layout="wide")

DASHBOARD = {
    "id": "D5",
    "title": "Weekly/Monthly Trend",
    "icon": "📊",
    "description": "Xu hướng giao thông dài hạn: lưu lượng theo ngày, phân bố theo ngày trong tuần, xu hướng trung bình, và tăng trưởng tháng.",
    "refresh": "30 phút",
    "color": "#6BCB77",
}
TTL = ttl_for_dashboard("D5")

with open(Path(__file__).parent.parent / "styles" / "custom.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────
def sidebar_nav():
    with st.sidebar:
        st.markdown("### 📊 Xu hướng Dài hạn")
        st.markdown("---")
        days = st.selectbox("Thời gian", [28, 60, 90], index=0,
                            format_func=lambda x: f"{x} ngày")
        st.markdown("---")
        st.markdown(f"**Cache TTL:** {TTL}s")
        return days


# ─── KPI Row ──────────────────────────────────────────────────────────────────
def kpi_row(df, days):
    import pandas as pd

    total_vehicles = df["vehicles_count"].sum()
    total_days = df["slot"].dt.date.nunique()
    expected_days = days

    daily_totals = df.groupby(df["slot"].dt.date)["vehicles_count"].sum()
    avg_daily = daily_totals.mean()
    peak_day = daily_totals.idxmax()
    peak_volume = daily_totals.max()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Tổng phương tiện", f"{total_vehicles:,.0f}")
    with c2:
        st.metric("Số ngày", f"{total_days}/{expected_days}")
    with c3:
        st.metric("Ngày đông nhất", str(peak_day))
    with c4:
        st.metric("TB/ngày", f"{avg_daily:,.0f}")


# ─── Fix 2: Daily Traffic Volume — Đánh dấu khoảng trống dữ liệu ───────────
def daily_traffic_volume(df):
    import pandas as pd
    import plotly.graph_objects as go

    df = df.copy()
    df["slot"] = pd.to_datetime(df["slot"])
    df["day"] = df["slot"].dt.date

    daily = (
        df.groupby(["day", "district"])["vehicles_count"]
        .sum()
        .reset_index()
        .rename(columns={"vehicles_count": "total_vehicles"})
    )

    all_days = pd.DataFrame({"day": pd.date_range(df["day"].min(), df["day"].max()).date})
    daily_pivot = daily.pivot(index="day", columns="district", values="total_vehicles").fillna(0)
    daily_pivot = daily_pivot.reindex(all_days["day"]).fillna(0)

    fig = go.Figure()
    districts = daily_pivot.columns.tolist()
    palette = C["chart_colors"]

    for i, district in enumerate(districts):
        fig.add_trace(go.Bar(
            x=daily_pivot.index,
            y=daily_pivot[district],
            name=district,
            marker_color=palette[i % len(palette)],
            hovertemplate=f"<b>{district}</b><br>Ngày: %{{x}}<br>Xe: %{{y:,.0f}}<extra></extra>",
        ))

    # Đánh dấu ngày không có dữ liệu (total = 0)
    zero_days = daily_pivot[daily_pivot.sum(axis=1) == 0].index.tolist()
    if zero_days:
        for zday in zero_days:
            fig.add_vline(
                x=pd.Timestamp(zday),
                line=dict(color="rgba(255,255,255,0.25)", width=1, dash="dot"),
            )

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(
            text="Daily Traffic Volume (Stacked Bar) — Vạch chấm = ngày thiếu dữ liệu",
            font=dict(size=13, color=C["text"]),
            x=0, xanchor="left",
        ),
        barmode="stack",
        xaxis_title="Ngày",
        yaxis_title="Tổng phương tiện",
        height=420,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=9),
            bgcolor="rgba(0,0,0,0)",
            yanchor="top", y=0.99,
            xanchor="left", x=1.01,
        ),
        margin=dict(l=40, r=150, b=60, t=60),
        xaxis=dict(
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(gridcolor="#2A3042"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 3: Day-of-Week Distribution — Đổi sang BOX PLOT + Y-axis đúng ──────
def dow_distribution(df):
    import pandas as pd
    import plotly.graph_objects as go

    df = df.copy()
    df["slot"] = pd.to_datetime(df["slot"])
    df["dow_num"] = df["slot"].dt.dayofweek
    df["dow"] = df["slot"].dt.day_name()

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_labels = {"Monday": "T2", "Tuesday": "T3", "Wednesday": "T4",
                  "Thursday": "T5", "Friday": "T6", "Saturday": "T7", "Sunday": "CN"}

    palette = C["chart_colors"]

    fig = go.Figure()
    for i, day in enumerate(day_order):
        sub = df[df["dow"] == day]["vehicles_count"]
        if len(sub) == 0:
            continue
        fig.add_trace(go.Box(
            y=sub,
            name=dow_labels.get(day, day),
            marker_color=palette[i % len(palette)],
            boxmean="sd",
            jitter=0.3,
            boxpoints="outliers",
            hovertemplate=f"<b>{dow_labels.get(day, day)}</b>"
                          f"<br>Median: %{{median:.1f}}<br>"
                          f"Mean: %{{mean:.1f}}<br>"
                          f"Std: %{{sd:.1f}}<br>"
                          f"Q1: %{{q1:.1f}} | Q3: %{{q3:.1f}}<br>"
                          f"N: %{{n}}<extra></extra>",
        ))

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(
            text="Day-of-Week Distribution (Box Plot) — Mỗi ngày trong tuần",
            font=dict(size=13, color=C["text"]),
            x=0, xanchor="left",
        ),
        xaxis_title="Ngày trong tuần",
        yaxis_title="Số xe / slot 5 phút",
        height=420,
        showlegend=False,
        margin=dict(l=40, r=30, b=60, t=60),
        xaxis=dict(tickfont=dict(size=11, color=C["text"])),
        yaxis=dict(gridcolor="#2A3042"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 4: Rolling Average Trend — Sửa công thức, xử lý missing data ──────
def rolling_average(df):
    import pandas as pd
    import plotly.graph_objects as go

    df = df.copy()
    df["slot"] = pd.to_datetime(df["slot"])
    df["day"] = df["slot"].dt.date

    rolling = (
        df.groupby("day")["vehicles_count"]
        .agg(["sum", "mean"])
        .reset_index()
        .rename(columns={"sum": "Daily Total", "mean": "Daily Avg", "day": "Date"})
        .sort_values("Date")
    )

    # Xử lý missing days — thêm các ngày không có dữ liệu với giá trị NaN
    all_dates = pd.date_range(rolling["Date"].min(), rolling["Date"].max()).date
    full_idx = pd.DataFrame({"Date": all_dates})
    rolling = full_idx.merge(rolling, on="Date", how="left")

    # Vẽ Daily Total (chỉ vẽ những điểm có dữ liệu)
    visible_total = rolling[rolling["Daily Total"].notna()]

    fig = go.Figure()

    # Đường Daily Total — vẽ đầy đủ nhưng ngắt quãng tại missing
    fig.add_trace(go.Scatter(
        x=rolling["Date"],
        y=rolling["Daily Total"],
        mode="lines",
        name="Daily Total",
        line=dict(color=C["chart_colors"][0], width=2.5),
        connectgaps=False,
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Daily Total: %{y:,.0f} xe<extra></extra>",
    ))

    # Đường Rolling 7-day MA — dùng rolling trung bình để thấy xu hướng
    rolling["MA7"] = rolling["Daily Total"].rolling(7, min_periods=1, center=True).mean()
    fig.add_trace(go.Scatter(
        x=rolling["Date"],
        y=rolling["MA7"],
        mode="lines",
        name="MA7 (Trung bình 7 ngày)",
        line=dict(color=C["warning"], width=2, dash="dash"),
        connectgaps=False,
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>MA7: %{y:,.0f}<extra></extra>",
    ))

    # Đánh dấu vùng missing
    missing_mask = rolling["Daily Total"].isna()
    for _, row in rolling[missing_mask].iterrows():
        fig.add_vrect(
            x0=row["Date"], x1=row["Date"],
            fillcolor="rgba(255,100,100,0.1)",
            line_width=0,
        )

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(
            text="Xu hướng Lưu lượng — Đường đứt quãng tại ngày thiếu dữ liệu",
            font=dict(size=13, color=C["text"]),
            x=0, xanchor="left",
        ),
        xaxis_title="Ngày",
        yaxis_title="Số phương tiện",
        height=420,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=40, r=30, b=60, t=60),
        xaxis=dict(
            tickfont=dict(size=10, color=C["text"]),
            gridcolor="#2A3042",
        ),
        yaxis=dict(gridcolor="#2A3042"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Fix 5: Month-over-Month Growth — Conditional display ────────────────────
def mom_growth(df):
    import pandas as pd
    import plotly.graph_objects as go

    df = df.copy()
    df["slot"] = pd.to_datetime(df["slot"])
    df["month"] = df["slot"].dt.to_period("M").astype(str)

    monthly = (
        df.groupby("month")["vehicles_count"]
        .sum()
        .reset_index()
        .rename(columns={"vehicles_count": "Total Vehicles"})
        .sort_values("month")
    )

    if len(monthly) < 2:
        st.info(
            "📅 **Month-over-Month Growth** — Cần ít nhất **2 tháng dữ liệu** để tính tăng trưởng. "
            "Hiện chỉ có dữ liệu **1 tháng**. "
            "Biểu đồ sẽ tự động hiển thị khi có đủ dữ liệu nhiều tháng."
        )
        return

    growth = monthly.copy()
    growth["Growth %"] = growth["Total Vehicles"].pct_change() * 100
    growth = growth.dropna()

    # Bar chart cho Total Vehicles
    bar_colors = []
    for v in growth["Total Vehicles"]:
        bar_colors.append(C["primary"])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=growth["month"],
        y=growth["Total Vehicles"],
        name="Tổng phương tiện",
        marker_color=bar_colors,
        text=[f"{v:,.0f}" for v in growth["Total Vehicles"]],
        textposition="outside",
        textfont=dict(color=C["text"], size=11, family="Arial"),
        yaxis="y",
        hovertemplate="<b>%{x}</b><br>Tổng: %{y:,.0f} xe<extra></extra>",
    ))

    # Line chart cho Growth %
    growth_colors = []
    for g in growth["Growth %"]:
        growth_colors.append(C["success"] if g >= 0 else C["danger"])

    fig.add_trace(go.Scatter(
        x=growth["month"],
        y=growth["Growth %"],
        name="Tăng trưởng %",
        mode="lines+markers+text",
        line=dict(
            color=C["warning"],
            width=2.5,
            shape="spline",
            smoothing=0.3,
        ),
        marker=dict(size=8, color=C["warning"]),
        text=[f"{g:+.1f}%" for g in growth["Growth %"]],
        textposition="top center",
        textfont=dict(color=C["warning"], size=11),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>Tăng trưởng: %{y:+.1f}%<extra></extra>",
    ))

    apply_dark_template(fig)
    fig.update_layout(
        title=dict(
            text="Month-over-Month Growth",
            font=dict(size=14, color=C["text"]),
            x=0, xanchor="left",
        ),
        xaxis_title="Tháng",
        height=420,
        showlegend=True,
        legend=dict(
            font=dict(color=C["text"], size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=40, r=60, b=60, t=60),
        xaxis=dict(tickfont=dict(size=11, color=C["text"])),
        yaxis=dict(
            title=dict(text="Tổng phương tiện", font=dict(color=C["text"], size=11)),
            gridcolor="#2A3042",
            side="left",
        ),
        yaxis2=dict(
            title=dict(text="Tăng trưởng %", font=dict(color=C["warning"], size=11)),
            anchor="free",
            overlaying="y",
            side="right",
            position=0.97,
            showgrid=False,
            tickfont=dict(color=C["warning"]),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Bonus: Data Quality Summary Table ─────────────────────────────────────
def data_quality_summary(df, days):
    import pandas as pd

    df = df.copy()
    df["slot"] = pd.to_datetime(df["slot"])
    df["day"] = df["slot"].dt.date

    all_days = pd.date_range(df["day"].min(), df["day"].max()).date
    daily_stats = df.groupby("day").agg(
        total_vehicles=("vehicles_count", "sum"),
        avg_speed=("speed_avg_kmh", "mean"),
        event_count=("vehicles_count", "count"),
    ).reset_index()

    quality_df = pd.DataFrame({"day": all_days}).merge(daily_stats, on="day", how="left")
    quality_df["has_data"] = quality_df["total_vehicles"].notna()
    quality_df.loc[~quality_df["has_data"], "total_vehicles"] = 0

    total_expected = len(all_days)
    total_with_data = quality_df["has_data"].sum()
    total_missing = total_expected - total_with_data

    data = {
        "KPI": ["Ngày kỳ vọng", "Ngày có dữ liệu", "Ngày thiếu dữ liệu", "Tỷ lệ đầy đủ"],
        "Giá trị": [
            f"{total_expected}",
            f"{total_with_data}",
            f"{total_missing}",
            f"{total_with_data / total_expected * 100:.1f}%",
        ],
    }
    qdf = pd.DataFrame(data)
    qdf.index = qdf["KPI"]
    qdf = qdf[["Giá trị"]]

    st.markdown("##### 📋 Tóm tắt Chất lượng Dữ liệu")
    st.dataframe(qdf, use_container_width=True, hide_index=False)


# ─── Entry Point ───────────────────────────────────────────────────────────
days = sidebar_nav()

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

with st.spinner("Đang tải dữ liệu xu hướng..."):
    @st.cache_data(ttl=TTL)
    def load_trend(days):
        return run_query(get_traffic_events(days=days), ttl=TTL)

    df = load_trend(days)

if df is not None and not df.empty:
    import pandas as pd
    df["slot"] = pd.to_datetime(df["slot"])

    # KPI row + data quality alert
    st.markdown("##### 📊 Chỉ số Tổng quan")
    kpi_row(df, days)

    st.markdown("---")

    # Row 1: Daily Volume (full width)
    st.markdown("##### 📅 Lưu lượng theo Ngày")
    daily_traffic_volume(df)

    st.markdown("---")

    # Row 2: DOW Box Plot + Rolling Average
    st.markdown("##### 📆 Phân bố theo Ngày trong Tuần & Xu hướng Trung bình")
    c2_1, c2_2 = st.columns(2, gap="medium")
    with c2_1:
        dow_distribution(df)
    with c2_2:
        rolling_average(df)

    st.markdown("---")

    # Row 3: MoM Growth (conditional) + Data Quality Table
    st.markdown("##### 📈 Tăng trưởng Month-over-Month")
    mom_growth(df)

    st.markdown("---")

    data_quality_summary(df, days)
else:
    st.warning("Không có dữ liệu xu hướng.")
