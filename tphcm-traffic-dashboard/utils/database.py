import streamlit as st
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

from utils.config import TRINO_HOST, TRINO_PORT, TRINO_USER, TRINO_CATALOG, TRINO_SCHEMA, TRINO_PASSWORD

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

try:
    import trino
    from trino.dbapi import connect as trino_connect
    from trino.exceptions import TrinoQueryError
    TRINO_AVAILABLE = True
except ImportError:
    TRINO_AVAILABLE = False

if DEMO_MODE:
    TRINO_AVAILABLE = False


# ── Demo Data Generation ───────────────────────────────────────────
def _gen_demo_events(days: int = 7, end_date=None) -> "pd.DataFrame":
    """Generate realistic mock traffic events for demo mode."""
    import numpy as np
    import pandas as pd

    districts = [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
        "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
        "Quận Tân Bình", "Quận Tân Phú", "Thành phố Thủ Đức",
    ]
    cameras = []
    for d in districts:
        for i in range(5):
            cameras.append({
                "camera_id": f"cam_{d}_{i}",
                "display_name": f"{d} - Camera {i+1}",
                "district": d,
                "lat": 10.76 + np.random.uniform(-0.05, 0.05),
                "lon": 106.65 + np.random.uniform(-0.05, 0.05),
                "status": np.random.choice(["UP", "UP", "UP", "UP", "DOWN", "NOT_IMAGE"],
                                          p=[0.40, 0.10, 0.10, 0.10, 0.15, 0.15]),
                "ptz": np.random.choice(["YES", "NO"]),
                "cam_type": np.random.choice(["FIXED", "PTZ", "DOME"]),
            })

    weather_conditions = ["Clear", "Clear", "Clouds", "Clouds", "Rain", "Drizzle", "Mist"]
    weather_weights = [0.25, 0.25, 0.20, 0.20, 0.05, 0.03, 0.02]

    end = end_date or datetime.now()
    start_time = end - timedelta(days=days)
    slot_interval = timedelta(minutes=5)

    rows = []
    current = start_time
    while current <= end:
        hour = current.hour
        is_rush = hour in [7, 8, 9, 17, 18, 19, 20]
        is_weekend = current.weekday() >= 5

        base_vehicles = 120 if is_rush else 60
        base_vehicles = base_vehicles * 0.85 if is_weekend else base_vehicles
        base_vehicles *= np.random.uniform(0.8, 1.2)

        base_speed = 18 if is_rush else 35
        base_speed *= np.random.uniform(0.85, 1.15)

        weather = np.random.choice(weather_conditions, p=weather_weights)

        for cam in cameras:
            if cam["status"] == "DOWN":
                continue
            vehicles = int(max(0, base_vehicles * np.random.uniform(0.5, 1.8)))
            speed = max(5, base_speed * np.random.uniform(0.6, 1.4))
            rows.append({
                "camera_id": cam["camera_id"],
                "display_name": cam["display_name"],
                "district": cam["district"],
                "slot": current,
                "generated_at": current + timedelta(seconds=np.random.randint(1, 30)),
                "duration_sec": 300,
                "vehicles_count": vehicles,
                "speed_count": np.random.randint(5, 50),
                "speed_avg_kmh": round(speed, 1),
                "speed_min_kmh": round(max(3, speed * 0.5), 1),
                "speed_max_kmh": round(speed * 1.5, 1),
                "weather_main": weather,
                "weather_temp": round(np.random.uniform(25, 36), 1),
                "weather_humidity": int(np.random.uniform(50, 95)),
                "weather_wind_speed": round(np.random.uniform(1, 10), 1),
                "weather_clouds": int(np.random.uniform(0, 100)),
                "location_lat": cam["lat"],
                "location_lon": cam["lon"],
                "camera_status": cam["status"],
                "ptz": cam["ptz"],
                "cam_type": cam["cam_type"],
                "count_preds": [vehicles + int(np.random.uniform(-20, 20))],
                "avg_kmh_preds": [speed + np.random.uniform(-5, 5)],
            })
        current += slot_interval

    df = pd.DataFrame(rows)
    return df


def _gen_demo_rush(days: int = 1, end_date=None) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    districts = [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
        "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
        "Quận Tân Bình", "Quận Tân Phú",
    ]
    data = []
    for d in districts:
        for period in ["Rush Hour", "Off-Peak"]:
            base = 150 if period == "Rush Hour" else 70
            base *= np.random.uniform(0.7, 1.3)
            data.append({"district": d, "time_period": period, "avg_vehicles": round(base, 1)})
    return pd.DataFrame(data)


def _gen_demo_heatmap(days: int = 7, end_date=None) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd

    end = end_date or datetime.now()
    districts = ["Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
                 "Quận Bình Tân", "Quận Bình Thạnh", "Quận Tân Bình"]
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    rows = []
    for d in districts:
        for day_offset in range(days):
            day_date = end - timedelta(days=days - 1 - day_offset)
            day_num = day_date.weekday() + 1
            day_name = day_order[day_num - 1]
            is_weekend = day_num >= 6
            for hour in range(24):
                is_rush = hour in [7, 8, 9, 17, 18, 19]
                base = 150 if is_rush else 55
                base = base * 0.85 if is_weekend else base
                base *= np.random.uniform(0.7, 1.3)
                rows.append({
                    "slot": day_date,
                    "day": day_date.strftime("%Y-%m-%d"),
                    "dow_num": day_num,
                    "day_name": day_name,
                    "day_type": "Weekend" if is_weekend else "Workday",
                    "hour": hour,
                    "district": d,
                    "camera_id": f"cam_{d}_0",
                    "display_name": f"{d} - Camera 1",
                    "avg_vehicles": round(base, 1),
                    "avg_speed": round(np.random.uniform(15, 45), 1),
                    "sample_count": np.random.randint(50, 200),
                })
    return pd.DataFrame(rows)


def _gen_demo_anomalies() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd

    districts = ["Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
                 "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp"]
    alert_types = ["Congestion", "Sudden Drop", "Sudden Spike", "Normal"]
    alert_probs = [0.40, 0.10, 0.05, 0.45]
    data = []
    now = datetime.now()
    for i in range(30):
        d = np.random.choice(districts)
        alert = np.random.choice(alert_types, p=alert_probs)
        vehicles = np.random.randint(10, 200)
        speed = np.random.uniform(5, 20) if alert == "Congestion" else np.random.uniform(20, 50)
        z = np.random.uniform(3.1, 5.0) if "Sudden" in alert else np.random.uniform(-2, 2)
        data.append({
            "camera_id": f"cam_{d}_0",
            "display_name": f"{d} - Camera 1",
            "district": d,
            "slot": now - timedelta(minutes=i * 5),
            "vehicles": vehicles,
            "speed_kmh": round(speed, 1),
            "baseline_avg": round(vehicles * np.random.uniform(0.8, 1.2), 1),
            "z_score": round(z, 2),
            "is_congested": alert == "Congestion",
            "alert_type": alert,
        })
    return pd.DataFrame(data)


def _gen_demo_cam_quality() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd

    districts = ["Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
                 "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
                 "Quận Tân Bình", "Quận Tân Phú"]
    data = []
    now = datetime.now()
    for d in districts:
        for i in range(5):
            status = np.random.choice(["UP", "UP", "UP", "DOWN", "NOT_IMAGE"],
                                      p=[0.60, 0.10, 0.10, 0.10, 0.10])
            data.append({
                "camera_id": f"cam_{d}_{i}",
                "display_name": f"{d} - Camera {i+1}",
                "district": d,
                "cam_type": np.random.choice(["FIXED", "PTZ", "DOME"]),
                "camera_status": status,
                "ptz": np.random.choice(["YES", "NO"]),
                "slots_today": np.random.randint(0, 300) if status == "UP" else 0,
                "last_event": now - timedelta(minutes=np.random.randint(5, 120)),
                "avg_vehicles": round(np.random.uniform(30, 180), 1) if status == "UP" else 0,
            })
    return pd.DataFrame(data)


@st.cache_resource(ttl=300)
def get_trino_connection():
    if not TRINO_AVAILABLE:
        return None
    try:
        if TRINO_PASSWORD:
            auth = trino.auth.BasicAuthentication(TRINO_USER, TRINO_PASSWORD)
        else:
            auth = None
        conn = trino_connect(
            host=TRINO_HOST,
            port=TRINO_PORT,
            user=TRINO_USER,
            catalog=TRINO_CATALOG,
            schema=TRINO_SCHEMA,
            auth=auth,
            http_scheme="http",
            request_timeout=600.0,
        )
        return conn
    except Exception as e:
        st.error(f"Trino connection failed: {e}")
        return None


def get_time_range_filter(
    time_col: str,
    days: int,
    custom_start: Optional[datetime] = None,
    custom_end: Optional[datetime] = None,
) -> str:
    if custom_start and custom_end:
        start_ts = custom_start.strftime("%Y-%m-%d %H:%M:%S")
        end_ts = custom_end.strftime("%Y-%m-%d %H:%M:%S")
    else:
        end_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start = datetime.now() - timedelta(days=days)
        start_ts = start.strftime("%Y-%m-%d %H:%M:%S")
    return f"AND {time_col} >= TIMESTAMP '{start_ts}' AND {time_col} < TIMESTAMP '{end_ts}'"


@st.cache_data(ttl=300)
def run_query(query: str, ttl: int = 300, days: int = None, end_date=None):
    if DEMO_MODE:
        import pandas as pd
        q = query.lower()
        if "camera_baseline" in q or "z_score" in q:
            return _gen_demo_anomalies()
        elif "slots_today" in q or ("slots" in q and "today" in q):
            return _gen_demo_cam_quality()
        elif "day_of_week" in q or ("heatmap" in q and "hour" in q and "day_name" in q):
            return _gen_demo_heatmap(days or 7, end_date)
        elif "time_period" in q:
            return _gen_demo_rush(days or 7, end_date)
        elif "predicts" in q or "count_preds" in q or "avg_kmh_preds" in q:
            df = _gen_demo_events(days or 7, end_date)
            df = df.copy()
            df["actual_count"] = df["vehicles_count"]
            df["actual_speed"] = df["speed_avg_kmh"]
            df["pred_count_t1"] = df["count_preds"].apply(lambda x: x[0] if isinstance(x, list) else x)
            df["pred_speed_t1"] = df["avg_kmh_preds"].apply(lambda x: x[0] if isinstance(x, list) else x)
            df["count_error_abs"] = (df["actual_count"] - df["pred_count_t1"]).abs()
            return df
        elif "mae_count" in q or "mae_speed" in q or ("ml" in q and "performance" in q):
            return _gen_demo_ml_perf(days or 7)
        elif "mape_count" in q or ("ml" in q and "accuracy" in q) or "district" in q and "mae_count" in q:
            return _gen_demo_ml_accuracy()
        elif "stale_pct" in q or ("freshness" in q and "c.camera_id" in q) or "last_event" in q and "c.cam_type" in q:
            return _gen_demo_freshness()
        elif "weather" in q and "avg_temp" in q and "avg_humidity" in q:
            return _gen_demo_weather(days or 7)
        elif "congested_cams" in q or "congestion_rate" in q or ("incidents" in q and "district" in q and "city_avg_speed" in q):
            return _gen_demo_incidents(1)
        elif "congestion_pct" in q and "event_count" in q and "display_name" in q:
            return _gen_demo_top_congestion()
        elif "operations_kpi" in q or ("total_events" in q and "avg_speed" in q and "congestion_pct" in q):
            return _gen_demo_operations(1)
        elif ("congestion_by_district" in q or "congestion_slots" in q) and "district" in q:
            return _gen_demo_congestion_district()
        elif "speed_distribution_query" in q or "speed_category" in q:
            return _gen_demo_speed_dist()
        elif "traffic_scatter" in q or ("avg_vehicles" in q and "avg_speed" in q and "district" in q and "event_count" in q):
            return _gen_demo_traffic_scatter()
        elif "weather_summary" in q or "weather" in q and "avg_temp" in q and "avg_humidity" in q:
            return _gen_demo_weather_summary()
        elif "weather_scatter" in q or ("humidity" in q and "temp" in q and "weather" in q and "sample_count" in q):
            return _gen_demo_weather_scatter()
        elif "prediction_trend" in q or ("actual_speed" in q and "pred_speed_t" in q):
            return _gen_demo_prediction_trend()
        elif "prediction_risk" in q or ("risk_level" in q and "camera_count" in q):
            return _gen_demo_prediction_risk()
        elif "prediction_congestion" in q or ("congestion_predictions" in q and "display_name" in q):
            return _gen_demo_prediction_congestion()
        elif "active_cameras" in q and "total_volume" in q and "day" in q:
            return _gen_demo_city_kpi(days or 7)
        elif "city_kpi" in q or ("active_cams" in q and "total_cams" in q and "congestion_pct" in q):
            return _gen_demo_city_status()
        elif "dow_num" in q and "avg_volume" in q:
            return _gen_demo_dow_profile()
        elif "day_type" in q and "avg_volume" in q and "avg_speed" in q:
            return _gen_demo_flow_trend(days or 7)
        elif "speed_bin" in q and "event_count" in q:
            return _gen_demo_speed_dist(days or 7)
        else:
            df = _gen_demo_events(days or 7, end_date)
            # Add time_period for D1 rush/offpeak chart compatibility
            # Add hour column for D2/D3/D4 compatibility
            if "slot" in df.columns:
                df = df.copy()
                df["slot"] = pd.to_datetime(df["slot"])
                if "time_period" not in df.columns:
                    df["time_period"] = df["slot"].dt.hour.apply(
                        lambda h: "Rush Hour" if h in [7, 8, 9, 17, 18, 19, 20] else "Off-Peak"
                    )
            return df
    conn = get_trino_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
            import pandas as pd
            from decimal import Decimal
            df = pd.DataFrame(rows, columns=columns)
            # Convert Decimal values to float for arithmetic compatibility
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].apply(
                        lambda x: float(x) if isinstance(x, Decimal) else x
                    )
            return df
    except TrinoQueryError as e:
        st.error(f"Query failed: {e.message}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None


def get_traffic_events(days: int = 1, end_date=None) -> str:
    end = end_date or datetime.now()
    start = end - timedelta(days=days)
    return f"""
SELECT
  e.camera_id,
  e.slot,
  e.generated_at,
  e.duration_sec,
  e.vehicles_count,
  e.speed_count,
  e.speed_avg_kmh,
  e.speed_min_kmh,
  e.speed_max_kmh,
  e.weather.main              AS weather_main,
  e.weather.temp             AS weather_temp,
  e.weather.humidity          AS weather_humidity,
  e.weather.wind_speed        AS weather_wind_speed,
  e.weather.clouds_all        AS weather_clouds,
  c.display_name,
  c.district,
  c.location_lon,
  c.location_lat,
  c.status    AS camera_status,
  c.ptz,
  c.cam_type
FROM traffic.events e
JOIN traffic.cameras c
  ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
"""


def get_rush_offpeak_query(days: int = 1, end_date=None) -> str:
    end = end_date or datetime.now()
    start = end - timedelta(days=days)
    return f"""
SELECT
  c.district,
  CASE WHEN HOUR(e.slot) IN (7,8,9,17,18,19,20) THEN 'Rush Hour'
       ELSE 'Off-Peak' END AS time_period,
  ROUND(AVG(e.vehicles_count), 1) AS avg_vehicles
FROM traffic.events e
JOIN traffic.cameras c ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY 1, 2
"""


def get_heatmap_hourly_query(days: int = 7, end_date=None) -> str:
    end = end_date or datetime.now()
    start = end - timedelta(days=days)
    return f"""
SELECT
  DATE(e.slot)                      AS day,
  DAY_OF_WEEK(e.slot)               AS dow_num,
  CASE DAY_OF_WEEK(e.slot)
    WHEN 1 THEN 'Sunday' WHEN 2 THEN 'Monday' WHEN 3 THEN 'Tuesday'
    WHEN 4 THEN 'Wednesday' WHEN 5 THEN 'Thursday' WHEN 6 THEN 'Friday'
    WHEN 7 THEN 'Saturday'
  END                                AS day_name,
  CASE WHEN DAY_OF_WEEK(e.slot) IN (7, 1)
       THEN 'Weekend' ELSE 'Workday'
  END                                AS day_type,
  HOUR(e.slot)                      AS hour,
  c.district,
  c.camera_id,
  c.display_name,
  ROUND(AVG(e.vehicles_count), 1) AS avg_vehicles,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS avg_speed,
  COUNT(*)                          AS sample_count
FROM traffic.events e
JOIN traffic.cameras c ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY
  DATE(e.slot), DAY_OF_WEEK(e.slot),
  HOUR(e.slot), c.district,
  c.camera_id, c.display_name
"""


def get_anomalies_query() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    baseline_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    return f"""
WITH camera_baseline AS (
  SELECT
    e.camera_id,
    AVG(e.vehicles_count)   AS avg_vehicles,
    STDDEV(e.vehicles_count) AS std_vehicles
  FROM traffic.events e
  WHERE e.slot >= TIMESTAMP '{baseline_start} 00:00:00'
    AND e.slot <  TIMESTAMP '{today} 00:00:00'
  GROUP BY e.camera_id
),
current_state AS (
  SELECT
    e.camera_id,
    c.display_name,
    c.district,
    e.slot,
    e.vehicles_count,
    e.speed_avg_kmh,
    b.avg_vehicles,
    b.std_vehicles,
    CASE
      WHEN b.std_vehicles > 0 AND b.std_vehicles IS NOT NULL
      THEN (e.vehicles_count - b.avg_vehicles) / b.std_vehicles
      ELSE NULL
    END AS z_score,
    CASE WHEN e.speed_avg_kmh < 15 THEN TRUE ELSE FALSE END AS is_congested
  FROM traffic.events e
  JOIN camera_baseline b ON e.camera_id = b.camera_id
  JOIN traffic.cameras c ON e.camera_id = c.camera_id
  WHERE e.slot >= TIMESTAMP '{today} 00:00:00'
)
SELECT
  camera_id,
  display_name,
  district,
  slot,
  ROUND(vehicles_count, 1) AS vehicles,
  ROUND(speed_avg_kmh, 1)  AS speed_kmh,
  ROUND(avg_vehicles, 1)   AS baseline_avg,
  ROUND(z_score, 2)        AS z_score,
  is_congested,
  CASE
    WHEN z_score < -3          THEN 'Sudden Drop'
    WHEN z_score > 3           THEN 'Sudden Spike'
    WHEN is_congested          THEN 'Congestion'
    ELSE                             'Normal'
  END AS alert_type
FROM current_state
WHERE z_score < -3 OR z_score > 3 OR is_congested = TRUE
ORDER BY slot DESC
"""


def get_predictions_query(days: int = 1) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  e.camera_id,
  e.slot,
  e.vehicles_count  AS actual_count,
  e.speed_avg_kmh   AS actual_speed,
  e.weather.main     AS weather_main,
  e.weather.temp     AS weather_temp,
  c.display_name,
  c.district,
  c.location_lon,
  c.location_lat,
  p.count_preds[1]  AS pred_count_t1,
  p.avg_kmh_preds[1] AS pred_speed_t1,
  ABS(e.vehicles_count - p.count_preds[1]) AS count_error_abs
FROM traffic.events e
JOIN traffic.predicts p
  ON e.camera_id = p.camera_id AND e.slot = p.slot
JOIN traffic.cameras c
  ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
"""


def get_camera_quality_query() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
SELECT
  c.camera_id,
  c.display_name,
  c.district,
  c.cam_type,
  c.status     AS camera_status,
  c.ptz,
  COUNT(e.slot) AS slots_today,
  MAX(e.slot)   AS last_event,
  ROUND(AVG(e.vehicles_count), 1) AS avg_vehicles
FROM traffic.cameras c
LEFT JOIN traffic.events e
  ON c.camera_id = e.camera_id
 AND DATE(e.slot) = DATE '{today}'
GROUP BY
  c.camera_id, c.display_name,
  c.district, c.cam_type, c.status, c.ptz
"""


# ── D9: City Overview ────────────────────────────────────────────────
def get_city_kpi_query(days: int = 1) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  DATE(e.slot)                AS day,
  COUNT(DISTINCT e.camera_id)  AS active_cameras,
  COUNT(*)                     AS total_events,
  ROUND(AVG(e.vehicles_count), 1) AS avg_vehicles,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS avg_speed,
  ROUND(SUM(e.vehicles_count), 0) AS total_volume
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY DATE(e.slot)
ORDER BY day
"""


def get_city_status_query() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
SELECT
  c.district,
  COUNT(DISTINCT c.camera_id)                                                    AS total_cams,
  COUNT(DISTINCT CASE WHEN e.slot >= TIMESTAMP '{today} 00:00:00' THEN e.camera_id END) AS active_cams,
  ROUND(AVG(e.vehicles_count), 1)                                               AS avg_volume,
  ROUND(AVG(e.speed_avg_kmh), 1)                                                AS avg_speed,
  ROUND(SUM(CASE WHEN e.speed_avg_kmh < 15 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS congestion_pct
FROM traffic.cameras c
LEFT JOIN traffic.events e ON c.camera_id = e.camera_id
  AND e.slot >= TIMESTAMP '{today} 00:00:00'
GROUP BY c.district
HAVING COUNT(DISTINCT c.camera_id) > 0
ORDER BY avg_volume DESC
"""


def get_top_congestion_query(days: int = 1) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  c.display_name,
  c.district,
  ROUND(AVG(e.vehicles_count), 1)  AS avg_volume,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS avg_speed,
  ROUND(SUM(CASE WHEN e.speed_avg_kmh < 15 THEN 1 ELSE 0 END)
        * 100.0 / NULLIF(COUNT(*), 0), 1) AS congestion_pct,
  COUNT(*)                         AS event_count
FROM traffic.events e
JOIN traffic.cameras c ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY c.display_name, c.district
ORDER BY congestion_pct DESC
LIMIT 15
"""


def get_dow_profile_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  DAY_OF_WEEK(e.slot)  AS dow_num,
  CASE DAY_OF_WEEK(e.slot)
    WHEN 1 THEN 'CN' WHEN 2 THEN 'T2' WHEN 3 THEN 'T3'
    WHEN 4 THEN 'T4' WHEN 5 THEN 'T5' WHEN 6 THEN 'T6'
    WHEN 7 THEN 'T7'
  END                   AS dow,
  ROUND(AVG(e.vehicles_count), 1) AS avg_volume,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS avg_speed,
  COUNT(DISTINCT e.camera_id)     AS active_cams
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY DAY_OF_WEEK(e.slot)
ORDER BY dow_num
"""


def _gen_demo_city_kpi(days: int = 1) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    rows = []
    for i in range(days):
        day = datetime.now() - timedelta(days=days - 1 - i)
        rows.append({
            "day": day.date(),
            "active_cameras": int(np.random.randint(38, 55)),
            "total_events": int(np.random.randint(80000, 140000)),
            "avg_vehicles": round(np.random.uniform(55, 90), 1),
            "avg_speed": round(np.random.uniform(22, 32), 1),
            "total_volume": int(np.random.randint(4_000_000, 8_000_000)),
        })
    return pd.DataFrame(rows)


def _gen_demo_city_status() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    districts = [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
        "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
        "Quận Tân Bình", "Quận Tân Phú", "Thành phố Thủ Đức",
    ]
    rows = []
    for d in districts:
        rows.append({
            "district": d,
            "total_cams": np.random.randint(5, 15),
            "active_cams": np.random.randint(3, 12),
            "avg_volume": round(np.random.uniform(40, 180), 1),
            "avg_speed": round(np.random.uniform(15, 40), 1),
            "congestion_pct": round(np.random.uniform(5, 45), 1),
        })
    return pd.DataFrame(rows)


def _gen_demo_top_congestion() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    roads = [
        "Nguyễn Huệ", "Đồng Khởi", "Lê Lợi", "Hai Bà Trưng",
        "Pasteur", "Đề Thám", "Lê Thánh Tôn", "Nam Kỳ Khởi Nghĩa",
        "Võ Văn Tần", "Trần Hưng Đạo", "Cách Mạng Tháng 8",
        "3 Tháng 2", "Lý Thường Kiệt", "Phạm Ngũ Lão",
    ]
    districts = ["Quận 1", "Quận 3", "Quận 5", "Quận 10"]
    rows = []
    for i, road in enumerate(roads):
        d = districts[i % len(districts)]
        rows.append({
            "display_name": f"{road} - Camera {i+1}",
            "district": d,
            "avg_volume": round(np.random.uniform(60, 220), 1),
            "avg_speed": round(np.random.uniform(8, 35), 1),
            "congestion_pct": round(np.random.uniform(5, 60), 1),
            "event_count": int(np.random.randint(500, 3000)),
        })
    df = pd.DataFrame(rows).sort_values("congestion_pct", ascending=False)
    return df.head(15).reset_index(drop=True)


def _gen_demo_dow_profile() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    dow_map = [
        (1, "CN", 55, 28),
        (2, "T2", 80, 24),
        (3, "T3", 85, 23),
        (4, "T4", 88, 22),
        (5, "T5", 90, 21),
        (6, "T6", 95, 20),
        (7, "T7", 75, 25),
    ]
    rows = []
    for num, name, vol, spd in dow_map:
        rows.append({
            "dow_num": num,
            "dow": name,
            "avg_volume": round(vol + np.random.uniform(-5, 5), 1),
            "avg_speed": round(spd + np.random.uniform(-2, 2), 1),
            "active_cams": int(np.random.randint(40, 55)),
        })
    return pd.DataFrame(rows)


# ── D10: Traffic Flow & Speed ──────────────────────────────────────────
def get_flow_speed_trend_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  DATE(e.slot)                    AS day,
  HOUR(e.slot)                    AS hour,
  CASE WHEN DAY_OF_WEEK(e.slot) IN (7, 1)
       THEN 'Weekend' ELSE 'Workday'
  END                              AS day_type,
  ROUND(AVG(e.vehicles_count), 1) AS avg_volume,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS avg_speed,
  COUNT(*)                         AS event_count
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY DATE(e.slot), HOUR(e.slot),
     CASE WHEN DAY_OF_WEEK(e.slot) IN (7, 1) THEN 'Weekend' ELSE 'Workday' END
ORDER BY day, hour
"""


def get_speed_distribution_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  CASE
    WHEN e.speed_avg_kmh < 10  THEN '0-10'
    WHEN e.speed_avg_kmh < 20  THEN '10-20'
    WHEN e.speed_avg_kmh < 30  THEN '20-30'
    WHEN e.speed_avg_kmh < 40  THEN '30-40'
    WHEN e.speed_avg_kmh < 50  THEN '40-50'
    ELSE                          '50+'
  END AS speed_bin,
  COUNT(*) AS event_count,
  ROUND(AVG(e.vehicles_count), 1) AS avg_volume
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY 1
ORDER BY 1
"""


def get_hourly_pattern_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  HOUR(e.slot)                    AS hour,
  ROUND(AVG(e.vehicles_count), 1) AS avg_volume,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS avg_speed,
  COUNT(DISTINCT e.camera_id)     AS active_cams
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY HOUR(e.slot)
ORDER BY hour
"""


def _gen_demo_flow_trend(days: int = 7) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    rows = []
    end = datetime.now()
    for d in range(days):
        day = end - timedelta(days=days - 1 - d)
        for h in range(24):
            is_weekend = day.weekday() >= 5
            is_rush = h in [7, 8, 9, 17, 18, 19]
            base_vol = 140 if is_rush else 60
            base_vol = base_vol * 0.85 if is_weekend else base_vol
            base_vol *= np.random.uniform(0.8, 1.2)
            base_spd = 16 if is_rush else 35
            base_spd *= np.random.uniform(0.85, 1.15)
            rows.append({
                "day": day.date(),
                "hour": h,
                "day_type": "Weekend" if is_weekend else "Workday",
                "avg_volume": round(base_vol, 1),
                "avg_speed": round(base_spd, 1),
                "event_count": int(np.random.randint(200, 800)),
            })
    return pd.DataFrame(rows)


def _gen_demo_speed_dist(days: int = 7) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    bins = ["0-10", "10-20", "20-30", "30-40", "40-50", "50+"]
    weights = [0.10, 0.25, 0.30, 0.20, 0.10, 0.05]
    rows = []
    for b, w in zip(bins, weights):
        rows.append({
            "speed_bin": b,
            "event_count": int(np.random.randint(2000, 20000) * w * 3),
            "avg_volume": round(np.random.uniform(30, 100), 1),
        })
    return pd.DataFrame(rows)


# ── D11: Weather & Incidents ───────────────────────────────────────────
def get_weather_impact_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  e.weather.main                 AS weather,
  COUNT(DISTINCT e.camera_id)   AS cameras,
  COUNT(*)                       AS total_events,
  ROUND(AVG(e.vehicles_count), 1) AS avg_volume,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS avg_speed,
  ROUND(AVG(e.weather.temp), 1)   AS avg_temp,
  ROUND(AVG(e.weather.humidity), 0) AS avg_humidity
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY e.weather.main
ORDER BY total_events DESC
"""


def get_incidents_summary_query(days: int = 1) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
WITH camera_baseline AS (
  SELECT
    e.camera_id,
    AVG(e.vehicles_count)    AS avg_vehicles,
    STDDEV(e.vehicles_count) AS std_vehicles
  FROM traffic.events e
  WHERE e.slot >= TIMESTAMP '{today}' - INTERVAL '7' DAY
    AND e.slot <  TIMESTAMP '{today}'
  GROUP BY e.camera_id
)
SELECT
  c.district,
  COUNT(DISTINCT CASE WHEN e.speed_avg_kmh < 15 THEN e.camera_id END) AS congested_cams,
  COUNT(DISTINCT CASE WHEN b.std_vehicles > 0
             AND (e.vehicles_count - b.avg_vehicles) / b.std_vehicles < -3
             THEN e.camera_id END)                               AS sudden_drop_cams,
  COUNT(DISTINCT CASE WHEN b.std_vehicles > 0
             AND (e.vehicles_count - b.avg_vehicles) / b.std_vehicles > 3
             THEN e.camera_id END)                               AS sudden_spike_cams,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS city_avg_speed,
  ROUND(COUNT(CASE WHEN e.speed_avg_kmh < 15 THEN 1 END) * 100.0
          / NULLIF(COUNT(*), 0), 1) AS congestion_rate
FROM traffic.events e
JOIN camera_baseline b ON e.camera_id = b.camera_id
JOIN traffic.cameras c ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{today} 00:00:00'
GROUP BY c.district
ORDER BY congestion_rate DESC
"""


def _gen_demo_weather(days: int = 7) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    conditions = [
        ("Clear", 35, 60, 120),
        ("Clouds", 30, 70, 90),
        ("Rain", 26, 88, 40),
        ("Drizzle", 27, 82, 25),
        ("Mist", 28, 78, 15),
    ]
    rows = []
    for cond, temp, hum, vol in conditions:
        rows.append({
            "weather": cond,
            "cameras": int(np.random.randint(5, 20)),
            "total_events": int(np.random.randint(5000, 50000)),
            "avg_volume": round(vol + np.random.uniform(-10, 10), 1),
            "avg_speed": round(temp / 2.5 + np.random.uniform(-5, 5), 1),
            "avg_temp": round(temp + np.random.uniform(-2, 2), 1),
            "avg_humidity": int(hum + np.random.randint(-5, 5)),
        })
    return pd.DataFrame(rows).sort_values("total_events", ascending=False)


def _gen_demo_incidents(days: int = 1) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    districts = [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
        "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
        "Quận Tân Bình", "Quận Tân Phú",
    ]
    rows = []
    for d in districts:
        cong = np.random.randint(1, 8)
        drop = np.random.randint(0, 3)
        spike = np.random.randint(0, 2)
        rows.append({
            "district": d,
            "congested_cams": cong,
            "sudden_drop_cams": drop,
            "sudden_spike_cams": spike,
            "city_avg_speed": round(np.random.uniform(14, 30), 1),
            "congestion_rate": round(np.random.uniform(3, 35), 1),
        })
    return pd.DataFrame(rows).sort_values("congestion_rate", ascending=False)


# ── D12: ML Performance & Data Quality ────────────────────────────────
def get_ml_performance_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  DATE(e.slot)                                        AS day,
  ROUND(AVG(ABS(e.vehicles_count - p.count_preds[1])), 1) AS mae_count,
  ROUND(AVG(ABS(e.speed_avg_kmh - p.avg_kmh_preds[1])), 1) AS mae_speed,
  ROUND(AVG(p.count_preds[1]), 1)                    AS avg_predicted,
  ROUND(AVG(e.vehicles_count), 1)                     AS avg_actual,
  COUNT(*)                                             AS sample_count
FROM traffic.events e
JOIN traffic.predicts p
  ON e.camera_id = p.camera_id AND e.slot = p.slot
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY DATE(e.slot)
ORDER BY day
"""


def get_ml_accuracy_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  c.district,
  ROUND(AVG(ABS(e.vehicles_count - p.count_preds[1])), 1)  AS mae_count,
  ROUND(AVG(ABS(e.speed_avg_kmh - p.avg_kmh_preds[1])), 1) AS mae_speed,
  ROUND(AVG(ABS(e.vehicles_count - p.count_preds[1]) * 100.0
        / NULLIF(e.vehicles_count, 0)), 1)                  AS mape_count,
  COUNT(*)                                                    AS samples
FROM traffic.events e
JOIN traffic.predicts p
  ON e.camera_id = p.camera_id AND e.slot = p.slot
JOIN traffic.cameras c ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY c.district
ORDER BY mae_count DESC
"""


def get_data_freshness_query() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
SELECT
  c.camera_id,
  c.display_name,
  c.district,
  c.cam_type,
  c.status AS camera_status,
  COUNT(e.slot) AS slots_today,
  MAX(e.slot)   AS last_event,
  ROUND(AVG(e.vehicles_count), 1) AS avg_vehicles
FROM traffic.cameras c
LEFT JOIN traffic.events e
  ON c.camera_id = e.camera_id
 AND DATE(e.slot) = DATE '{today}'
GROUP BY c.camera_id, c.display_name, c.district, c.cam_type, c.status
ORDER BY last_event ASC NULLS FIRST
"""


def _gen_demo_ml_perf(days: int = 7) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    rows = []
    end = datetime.now()
    for d in range(days):
        day = end - timedelta(days=days - 1 - d)
        mae_c = np.random.uniform(8, 18)
        mae_s = np.random.uniform(3, 8)
        pred = np.random.uniform(60, 120)
        rows.append({
            "day": day.date(),
            "mae_count": round(mae_c, 1),
            "mae_speed": round(mae_s, 1),
            "avg_predicted": round(pred, 1),
            "avg_actual": round(pred + np.random.uniform(-5, 5), 1),
            "sample_count": int(np.random.randint(5000, 20000)),
        })
    return pd.DataFrame(rows)


def _gen_demo_ml_accuracy() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    districts = [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
        "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
        "Quận Tân Bình", "Quận Tân Phú",
    ]
    rows = []
    for d in districts:
        mae_c = np.random.uniform(5, 20)
        rows.append({
            "district": d,
            "mae_count": round(mae_c, 1),
            "mae_speed": round(mae_c / 2.5, 1),
            "mape_count": round(mae_c * 1.5, 1),
            "samples": int(np.random.randint(500, 5000)),
        })
    return pd.DataFrame(rows).sort_values("mae_count", ascending=False)


def _gen_demo_freshness() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    districts = ["Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
                 "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp"]
    types = ["FIXED", "PTZ", "DOME"]
    statuses = ["UP", "UP", "UP", "DOWN", "NOT_IMAGE"]
    rows = []
    for d in districts:
        for i in range(5):
            status = statuses[i % len(statuses)]
            last = datetime.now() - timedelta(
                minutes=int(np.random.randint(2, 180)) if status == "UP" else np.random.randint(200, 600)
            )
            rows.append({
                "camera_id": f"cam_{d}_{i}",
                "display_name": f"{d} - Camera {i+1}",
                "district": d,
                "cam_type": types[i % len(types)],
                "camera_status": status,
                "slots_today": int(np.random.randint(0, 300)) if status == "UP" else 0,
                "last_event": last,
                "avg_vehicles": round(np.random.uniform(20, 180), 1) if status == "UP" else 0,
                "stale_pct": round(np.random.uniform(0, 30), 1),
            })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────────
# D7: Traffic Operations (Light Mode) queries
# ──────────────────────────────────────────────────────────────────────────────
def get_operations_kpi_query(days: int = 1) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  COUNT(DISTINCT e.camera_id)                                        AS total_events,
  ROUND(AVG(e.speed_avg_kmh), 1)                                    AS avg_speed,
  ROUND(SUM(CASE WHEN e.speed_avg_kmh < 15 THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(*), 0), 1)                                   AS congestion_pct,
  COUNT(DISTINCT CASE WHEN e.slot >= TIMESTAMP '{end.strftime("%Y-%m-%d %H:%M:%S")}' - INTERVAL '1' HOUR
                      THEN e.camera_id END)                         AS active_cams_1h,
  ROUND(SUM(e.vehicles_count), 0)                                    AS total_vehicles
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime("%Y-%m-%d %H:%M:%S")}'
  AND e.slot <  TIMESTAMP '{end.strftime("%Y-%m-%d %H:%M:%S")}'
"""


def get_congestion_by_district_query(days: int = 1) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  c.district,
  COUNT(CASE WHEN e.speed_avg_kmh < 15 THEN 1 END) AS congestion_slots,
  COUNT(*)                                           AS total_slots,
  ROUND(COUNT(CASE WHEN e.speed_avg_kmh < 15 THEN 1 END) * 100.0
        / NULLIF(COUNT(*), 0), 1)                    AS congestion_rate,
  ROUND(AVG(e.speed_avg_kmh), 1)                    AS avg_speed
FROM traffic.events e
JOIN traffic.cameras c ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.speed_avg_kmh IS NOT NULL
GROUP BY c.district
ORDER BY congestion_slots DESC
LIMIT 15
"""


def get_speed_distribution_query(days: int = 1) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  CASE
    WHEN e.speed_avg_kmh < 10 THEN 'Nguy cơ cao (<10)'
    WHEN e.speed_avg_kmh < 20 THEN 'Kẹt nặng (10-20)'
    WHEN e.speed_avg_kmh < 30 THEN 'Đông xe (20-30)'
    WHEN e.speed_avg_kmh < 50 THEN 'Bình thường (30-50)'
    ELSE 'Thông thoáng (>50)'
  END AS speed_category,
  COUNT(*) AS event_count,
  ROUND(AVG(e.vehicles_count), 1) AS avg_vehicles
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY 1
ORDER BY
  CASE speed_category
    WHEN 'Nguy cơ cao (<10)' THEN 1
    WHEN 'Kẹt nặng (10-20)' THEN 2
    WHEN 'Đông xe (20-30)' THEN 3
    WHEN 'Bình thường (30-50)' THEN 4
    WHEN 'Thông thoáng (>50)' THEN 5
  END
"""


def get_traffic_scatter_query(days: int = 1) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  c.district,
  ROUND(AVG(e.vehicles_count), 1) AS avg_vehicles,
  ROUND(AVG(e.speed_avg_kmh), 1)  AS avg_speed,
  COUNT(*)                          AS event_count
FROM traffic.events e
JOIN traffic.cameras c ON e.camera_id = c.camera_id
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
  AND c.district IS NOT NULL
GROUP BY c.district
ORDER BY event_count DESC
"""


def _gen_demo_operations(days: int = 1) -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    districts = [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
        "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
        "Quận Tân Bình", "Quận Tân Phú",
    ]
    rows = {
        "total_events": [np.random.randint(80000, 140000)],
        "avg_speed": [round(np.random.uniform(20, 28), 1)],
        "congestion_pct": [round(np.random.uniform(5, 25), 1)],
        "active_cams_1h": [np.random.randint(30, 60)],
        "total_vehicles": [np.random.randint(4_000_000, 8_000_000)],
    }
    df = pd.DataFrame(rows)
    return df


def _gen_demo_congestion_district() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    districts = [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
        "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
        "Quận Tân Bình", "Quận Tân Phú",
    ]
    rows = []
    for d in districts:
        cong = np.random.randint(100, 3000)
        total = np.random.randint(2000, 10000)
        rows.append({
            "district": d,
            "congestion_slots": cong,
            "total_slots": total,
            "congestion_rate": round(cong * 100.0 / total, 1),
            "avg_speed": round(np.random.uniform(12, 35), 1),
        })
    df = pd.DataFrame(rows).sort_values("congestion_slots", ascending=False)
    return df.head(12)


def _gen_demo_speed_dist() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    cats = [
        ("Nguy cơ cao (<10)", 1500, 25),
        ("Kẹt nặng (10-20)", 5000, 55),
        ("Đông xe (20-30)", 8000, 85),
        ("Bình thường (30-50)", 6000, 95),
        ("Thông thoáng (>50)", 2000, 110),
    ]
    rows = []
    for cat, cnt, vol in cats:
        rows.append({
            "speed_category": cat,
            "event_count": int(cnt * np.random.uniform(0.9, 1.1)),
            "avg_vehicles": round(vol + np.random.uniform(-10, 10), 1),
        })
    return pd.DataFrame(rows)


def _gen_demo_traffic_scatter() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    districts = [
        "Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10",
        "Quận Bình Tân", "Quận Bình Thạnh", "Quận Gò Vấp",
        "Quận Tân Bình", "Quận Tân Phú",
    ]
    rows = []
    for d in districts:
        rows.append({
            "district": d,
            "avg_vehicles": round(np.random.uniform(40, 180), 1),
            "avg_speed": round(np.random.uniform(12, 35), 1),
            "event_count": int(np.random.randint(5000, 30000)),
        })
    return pd.DataFrame(rows).sort_values("event_count", ascending=False)


# ──────────────────────────────────────────────────────────────────────────────
# D8: Weather Impact (Light Mode) queries
# ──────────────────────────────────────────────────────────────────────────────
def get_weather_summary_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  e.weather.main                    AS weather,
  COUNT(*)                          AS event_count,
  ROUND(AVG(e.vehicles_count), 1)  AS avg_vehicles,
  ROUND(AVG(e.speed_avg_kmh), 1)   AS avg_speed,
  ROUND(AVG(e.weather.temp), 1)     AS avg_temp,
  ROUND(AVG(e.weather.humidity), 0) AS avg_humidity
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY e.weather.main
ORDER BY event_count DESC
"""


def get_weather_scatter_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  e.weather.main                    AS weather,
  ROUND(AVG(e.weather.humidity), 0) AS humidity,
  ROUND(AVG(e.weather.temp), 1)      AS temp,
  ROUND(AVG(e.vehicles_count), 1)   AS avg_vehicles,
  ROUND(AVG(e.speed_avg_kmh), 1)    AS avg_speed,
  COUNT(*)                            AS sample_count
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY e.weather.main
ORDER BY sample_count DESC
"""


def get_weather_hourly_query(days: int = 7) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  e.weather.main                     AS weather,
  HOUR(e.slot)                       AS hour,
  FLOOR(HOUR(e.slot) / 2)            AS hour_block,
  CASE WHEN HOUR(e.slot) IN (7,8,9,17,18,19,20) THEN 'Rush Hour' ELSE 'Off-Peak' END AS period,
  COUNT(CASE WHEN e.speed_avg_kmh < 15 THEN 1 END) AS congestion_count,
  ROUND(AVG(e.vehicles_count), 1)    AS avg_vehicles
FROM traffic.events e
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.weather.main = 'Rain'
GROUP BY e.weather.main, HOUR(e.slot), FLOOR(HOUR(e.slot) / 2)
ORDER BY hour
"""


def _gen_demo_weather_summary() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    weather_data = [
        ("Rain", 50000, 50, 22, 88),
        ("Clouds", 40000, 75, 28, 75),
        ("Clear", 35000, 80, 32, 65),
        ("Drizzle", 15000, 55, 26, 85),
        ("Mist", 8000, 60, 27, 80),
    ]
    rows = []
    for w, cnt, vol, tmp, hum in weather_data:
        rows.append({
            "weather": w,
            "event_count": int(cnt * np.random.uniform(0.9, 1.1)),
            "avg_vehicles": round(vol + np.random.uniform(-5, 5), 1),
            "avg_speed": round(tmp / 2.5 + np.random.uniform(-3, 3), 1),
            "avg_temp": round(tmp + np.random.uniform(-2, 2), 1),
            "avg_humidity": int(hum + np.random.randint(-5, 5)),
        })
    return pd.DataFrame(rows).sort_values("event_count", ascending=False)


def _gen_demo_weather_scatter() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    weather_data = [
        ("Rain", 88, 25, 50, 22, 500),
        ("Clouds", 75, 28, 75, 28, 400),
        ("Clear", 65, 32, 80, 32, 350),
        ("Drizzle", 85, 26, 55, 26, 150),
        ("Mist", 80, 27, 60, 27, 80),
    ]
    rows = []
    for w, hum, tmp, vol, spd, cnt in weather_data:
        rows.append({
            "weather": w,
            "humidity": int(hum + np.random.randint(-5, 5)),
            "temp": round(tmp + np.random.uniform(-1, 1), 1),
            "avg_vehicles": round(vol + np.random.uniform(-10, 10), 1),
            "avg_speed": round(spd + np.random.uniform(-3, 3), 1),
            "sample_count": int(cnt * np.random.uniform(0.9, 1.1)),
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────────────
# D9: Predictive Analysis (Light Mode) queries
# ──────────────────────────────────────────────────────────────────────────────
def get_prediction_trend_query(days: int = 1) -> str:
    start = datetime.now() - timedelta(days=days)
    end = datetime.now()
    return f"""
SELECT
  DATE(e.slot)                                        AS day,
  HOUR(e.slot)                                        AS hour,
  FLOOR(HOUR(e.slot) / 4)                            AS time_block,
  ROUND(AVG(e.speed_avg_kmh), 1)                    AS actual_speed,
  ROUND(AVG(p.avg_kmh_preds[1]), 1)                 AS pred_speed_t1,
  ROUND(AVG(p.avg_kmh_preds[7]), 1)                 AS pred_speed_t7,
  ROUND(AVG(p.avg_kmh_preds[12]), 1)                AS pred_speed_t12,
  ROUND(AVG(ABS(e.speed_avg_kmh - p.avg_kmh_preds[1])), 2) AS mae_t1,
  COUNT(*)                                            AS sample_count
FROM traffic.events e
JOIN traffic.predicts p
  ON e.camera_id = p.camera_id AND e.slot = p.slot
WHERE e.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND e.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY DATE(e.slot), HOUR(e.slot), FLOOR(HOUR(e.slot) / 4)
ORDER BY day, time_block
"""


def get_prediction_risk_query(hours: int = 1) -> str:
    end = datetime.now()
    start = end - timedelta(hours=hours)
    return f"""
SELECT
  CASE
    WHEN p.avg_kmh_preds[1] < 10 THEN 'Nguy cơ cao (<10 km/h)'
    WHEN p.avg_kmh_preds[1] < 15 THEN 'Nguy cơ vừa (10-15)'
    WHEN p.avg_kmh_preds[1] < 25 THEN 'Cảnh báo (15-25)'
    ELSE 'Thông thoáng (>25)'
  END AS risk_level,
  COUNT(*) AS camera_count,
  ROUND(AVG(p.avg_kmh_preds[1]), 1) AS avg_predicted_speed
FROM traffic.predicts p
WHERE p.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND p.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY 1
ORDER BY
  CASE risk_level
    WHEN 'Nguy cơ cao (<10 km/h)' THEN 1
    WHEN 'Nguy cơ vừa (10-15)' THEN 2
    WHEN 'Cảnh báo (15-25)' THEN 3
    WHEN 'Thông thoáng (>25)' THEN 4
  END
"""


def get_prediction_congestion_query(hours: int = 1) -> str:
    end = datetime.now()
    start = end - timedelta(hours=hours)
    return f"""
SELECT
  c.display_name,
  c.district,
  COUNT(CASE WHEN p.avg_kmh_preds[1] < 15 THEN 1 END) AS congestion_predictions,
  COUNT(*)                                             AS total_predictions,
  ROUND(MIN(p.avg_kmh_preds[1]), 1)                   AS min_predicted_speed
FROM traffic.predicts p
JOIN traffic.cameras c ON p.camera_id = c.camera_id
WHERE p.slot >= TIMESTAMP '{start.strftime('%Y-%m-%d %H:%M:%S')}'
  AND p.slot <  TIMESTAMP '{end.strftime('%Y-%m-%d %H:%M:%S')}'
GROUP BY c.display_name, c.district
HAVING COUNT(CASE WHEN p.avg_kmh_preds[1] < 15 THEN 1 END) > 0
ORDER BY congestion_predictions DESC
LIMIT 15
"""


def _gen_demo_prediction_trend() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    rows = []
    for h in range(24):
        actual = np.random.uniform(15, 30)
        rows.append({
            "day": pd.Timestamp.now().date(),
            "hour": h,
            "time_block": h // 4,
            "actual_speed": round(actual, 1),
            "pred_speed_t1": round(actual + np.random.uniform(-3, 3), 1),
            "pred_speed_t7": round(actual + np.random.uniform(-5, 5), 1),
            "pred_speed_t12": round(actual + np.random.uniform(-8, 8), 1),
            "mae_t1": round(np.random.uniform(1, 5), 2),
            "sample_count": np.random.randint(500, 2000),
        })
    return pd.DataFrame(rows)


def _gen_demo_prediction_risk() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    levels = [
        ("Nguy cơ cao (<10 km/h)", 5, 8),
        ("Nguy cơ vừa (10-15)", 12, 12),
        ("Cảnh báo (15-25)", 20, 20),
        ("Thông thoáng (>25)", 15, 30),
    ]
    rows = []
    for lv, cnt, spd in levels:
        rows.append({
            "risk_level": lv,
            "camera_count": int(cnt * np.random.uniform(0.8, 1.2)),
            "avg_predicted_speed": round(spd + np.random.uniform(-2, 2), 1),
        })
    return pd.DataFrame(rows)


def _gen_demo_prediction_congestion() -> "pd.DataFrame":
    import numpy as np
    import pandas as pd
    roads = [
        "Nguyễn Huệ", "Đồng Khởi", "Lê Lợi", "Hai Bà Trưng",
        "Pasteur", "Nam Kỳ Khởi Nghĩa", "Võ Văn Tần", "Trần Hưng Đạo",
        "Cách Mạng Tháng 8", "3 Tháng 2", "Phạm Ngũ Lão", "Lý Thường Kiệt",
    ]
    districts = ["Quận 1", "Quận 3", "Quận 5", "Quận 7", "Quận 10"]
    rows = []
    for i, road in enumerate(roads):
        cong = np.random.randint(2, 20)
        total = np.random.randint(10, 40)
        rows.append({
            "display_name": f"{road}",
            "district": districts[i % len(districts)],
            "congestion_predictions": cong,
            "total_predictions": total,
            "min_predicted_speed": round(np.random.uniform(5, 14), 1),
        })
    df = pd.DataFrame(rows).sort_values("congestion_predictions", ascending=False)
    return df.head(12)
