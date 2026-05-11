import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="HCM Traffic Dashboard",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

with open(Path(__file__).parent / "styles" / "custom.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center; padding:1.5rem 0 0.5rem;">
    <h1 style="font-size:2.2rem; margin-bottom:0.3rem; color:#E8EAF0;">
        🚦 HCM Traffic Intelligence Dashboard
    </h1>
    <p style="color:#8892A4; font-size:1rem; margin-top:0;">
        Real-time traffic analytics for Ho Chi Minh City &nbsp;|&nbsp; Powered by Streamlit + Apache Iceberg + Trino
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("")

dashboards = [
    {
        "id": "D1",
        "icon": "🗺️",
        "title": "Bản Đồ Giao Thông",
        "subtitle": "Traffic Map",
        "color": "2E86AB",
        "desc": "Bản đồ nhiệt các điểm kẹt xe trên toàn thành phố Hồ Chí Minh theo thời gian thực.",
        "path": "D1_Traffic_Map",
        "tags": ["Map", "Heatmap", "Real-time"],
    },
    {
        "id": "D2",
        "icon": "🌡️",
        "title": "Bản Đồ Nhiệt",
        "subtitle": "Traffic Heatmap",
        "color": "E94F37",
        "desc": "Heatmap tương tác theo giờ trong ngày và ngày trong tuần — nhận diện giờ cao điểm.",
        "path": "D2_Traffic_Heatmap",
        "tags": ["Heatmap", "Hourly", "Rush Hour"],
    },
    {
        "id": "D3",
        "icon": "📊",
        "title": "Phân Tích Tốc Độ",
        "subtitle": "Speed Analysis",
        "color": "3498DB",
        "desc": "Phân tích phân bổ tốc độ, so sánh Workday vs Weekend, xu hướng tốc độ theo thời gian.",
        "path": "D3_Speed_Analysis",
        "tags": ["Speed", "Distribution", "Trend"],
    },
    {
        "id": "D4",
        "icon": "🌦️",
        "title": "Tác Động Thời Tiết",
        "subtitle": "Weather Impact",
        "color": "4ECDC4",
        "desc": "Tương quan điều kiện thời tiết với lưu lượng giao thông. Phân tích khi mưa, nắng, mây.",
        "path": "D4_Weather_Impact",
        "tags": ["Weather", "Correlation", "Impact"],
    }
    # ,
    # {
    #     "id": "D5",
    #     "icon": "📈",
    #     "title": "Xu Hướng Tuần/Tháng",
    #     "subtitle": "Weekly / Monthly Trend",
    #     "color": "9B59B6",
    #     "desc": "Xu hướng lưu lượng và tốc độ theo ngày trong tuần, giờ trong ngày, phân biệt ngày làm việc và cuối tuần.",
    #     "path": "D5_Weekly_Trend",
    #     "tags": ["Trend", "Weekly", "Volume"],
    # },
]

cols = st.columns(4)
for i, d in enumerate(dashboards):
    with cols[i]:
        st.markdown(f"""
        <div style="
            background: linear-gradient(160deg, #{d['color']}18 0%, #{d['color']}08 100%);
            border: 1px solid #{d['color']}40;
            border-left: 4px solid #{d['color']};
            border-radius: 10px;
            padding: 1.2rem 1rem;
            margin: 0.4rem 0;
            transition: all 0.2s;
            min-height: 180px;
        ">
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
                <span style="font-size:1.6rem;">{d['icon']}</span>
                <div>
                    <div style="font-weight:700; font-size:0.95rem; color:#E8EAF0;">{d['id']} — {d['title']}</div>
                    <div style="font-size:0.75rem; color:#8892A4;">{d['subtitle']}</div>
                </div>
            </div>
            <div style="margin:0.6rem 0 0.4rem;">
                {''.join(f'<span style="background:#1A1F2E;color:{d['color']};padding:2px 8px;border-radius:4px;font-size:0.7rem;margin-right:4px;">{tag}</span>' for tag in d['tags'])}
            </div>
            <div style="color:#8892A4; font-size:0.8rem; line-height:1.5; min-height:3em;">{d['desc']}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(
            f"<div style='text-align:center;'><a href='/{d['path']}' target='_self' style='color:#{d['color']};font-weight:600;font-size:0.85rem;text-decoration:none;'>▶ Mở Dashboard →</a></div>",
            unsafe_allow_html=True,
        )

st.markdown("")

st.markdown(
    '<div style="border-top:1px solid #2A3042; padding:1rem 0 0.5rem; text-align:center; color:#5A6275; font-size:0.8rem;">'
    'TP.HCM Traffic Intelligence Dashboard &nbsp;|&nbsp; 4 dashboards &nbsp;|&nbsp; Auto-refresh every 5–15 min'
    '</div>',
    unsafe_allow_html=True,
)
