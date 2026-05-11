# TPHCM Traffic Monitoring — Streamlit Dashboard

Dashboard giám sát giao thông TPHCM với 8 dashboard, real-time data từ Trino Iceberg.

## Features

- **8 Dashboards**: KPI tổng quan, Heatmap, Speed Analysis, Weather Impact, ML Predictions, Data Quality, Trend, Incident Detection
- **Auto-refresh**: Cấu hình được theo từng dashboard (1 phút - 30 phút)
- **Trino Iceberg**: Kết nối trực tiếp qua trino-python-client
- **Caching thông minh**: st.cache_data với TTL theo dashboard
- **Filter động**: Date range, District, Camera, Weather
- **Responsive UI**: Dark theme, custom CSS, chart animations

## Quick Start

### 1. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 2. Cấu hình environment

```bash
cp .env.example .env
# Edit .env với thông tin Trino connection
```

### 3. Chạy local

```bash
streamlit run app.py --server.port 8501
```

### 4. Deploy với Docker

```bash
docker compose up -d
```

Truy cập: http://localhost:8501

## Cấu Trúc Project

```
tphcm-traffic-dashboard/
├── app.py                  # Main entry, sidebar nav
├── pages/
│   ├── D1_Traffic_Map.py      # KPI overview
│   ├── D2_Traffic_Heatmap.py  # Heatmap patterns
│   ├── D3_Speed_Analysis.py    # Speed metrics
│   ├── D4_Weather_Impact.py    # Weather correlation
│   ├── D5_Predictions_ML.py    # ML monitoring
│   ├── D6_Data_Quality.py      # Pipeline monitoring
│   ├── D7_Weekly_Trend.py      # Long-term trends
│   └── D8_Incident_Detection.py # Anomaly alerts
├── utils/
│   ├── config.py            # Config & env vars
│   ├── database.py         # Trino connection & queries
│   ├── cache_utils.py      # Caching helpers
│   └── chart_utils.py      # Chart config & styling
├── styles/
│   └── custom.css          # Dark theme, layout
├── .env.example
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

## Dashboard Summary

| Dashboard | Chủ đề | Auto-refresh | Cache TTL |
|-----------|--------|-------------|-----------|
| D1 - Traffic Map | KPI tổng quan | 5 phút | 5 phút |
| D2 - Traffic Heatmap | Heatmap giờ/ngày | 15 phút | 15 phút |
| D3 - Speed Analysis | Phân tích tốc độ | 10 phút | 10 phút |
| D4 - Weather Impact | Thời tiết ảnh hưởng | 15 phút | 15 phút |
| D5 - Predictions & ML | ML model monitoring | 10 phút | 10 phút |
| D6 - Data Quality | Pipeline monitoring | 5 phút | 5 phút |
| D7 - Weekly Trend | Xu hướng dài hạn | 30 phút | 30 phút |
| D8 - Incident Detection | Phát hiện sự cố | **1 phút** | 1 phút |

## Environment Variables

```env
TRINO_HOST=trino
TRINO_PORT=8080
TRINO_USER=admin
TRINO_CATALOG=iceberg
TRINO_SCHEMA=traffic
TRINO_PASSWORD=
DEFAULT_DISTRICT=Quận 1
DEFAULT_TIME_RANGE_DAYS=7
```

## Database Tables

- `iceberg.traffic.events` — Traffic events (camera_id, slot, vehicles_count, speed_avg_kmh, weather)
- `iceberg.traffic.cameras` — Camera metadata (camera_id, display_name, district, status)
- `iceberg.traffic.predicts` — ML predictions (camera_id, slot, count_preds, avg_kmh_preds)

## Troubleshooting

**Query timeout**: Tăng `socket_timeout` trong config hoặc giảm `time_range_days`

**Connection error**: Kiểm tra Trino container đang chạy và network trong docker-compose

**Charts not rendering**: Kiểm tra `pydeck` và `graphviz` đã được cài đặt

## License

MIT
