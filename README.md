# Traffic Data Lakehouse - Ho Chi Minh City

**Intelligent traffic monitoring and congestion prediction system** for Ho Chi Minh City. Integrates multi-modal data (images, speed, weather, news, voice) on a Data Lakehouse platform to analyze and forecast traffic congestion in real time, tested on 23 traffic cameras across Ho Chi Minh City.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      STORAGE VPS                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                        SeaweedFS                             │  │
│  │                    Object Storage (S3 API :8333)              │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                   │
                                   │ S3 (read/write)
                                   │ Kafka stream
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                           COMPUTE VPS                              │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                      Apache NiFi                              │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │   │
│  │  │  Image   │ │  Speed   │ │ Weather  │ │ Batching &   │ │   │
│  │  │Ingestion │ │Ingestion │ │Ingestion │ │ AI/YOLO      │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                   │                               │
│                                   ▼                               │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    Apache Kafka                              │   │
│  │  traffic-images | traffic-speed | traffic-weather | metrics │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                   │                               │
│                                   ▼                               │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │         Apache Iceberg REST Catalog + PostgreSQL             │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                   │                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────────┐  ┌──────────────┐   │
│  │  Trino  │  │  Redis  │  │   gRPC      │  │  Prometheus + │   │
│  │(Queries)│  │ (Slots) │  │   Server    │  │   Grafana    │   │
│  └─────────┘  └─────────┘  └─────────────┘  └──────────────┘   │
│       │                                                │          │
│       ▼                                                ▼          │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │            Streamlit Dashboard (4 dashboards)                │   │
│  │  Traffic Map | Heatmap | Speed Analysis | Weather Impact  │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Data Ingestion** | Apache NiFi | Multi-source data pipelines (images, speed, weather, news, voice) — runs on Compute VPS |
| **Message Broker** | Apache Kafka | Real-time event streaming — runs on Compute VPS |
| **Object Storage** | SeaweedFS (S3 API) | Scalable distributed object store |
| **Table Format** | Apache Iceberg | Open table format with ACID transactions |
| **Query Engine** | Trino | Distributed SQL engine |
| **Catalog** | Iceberg REST + PostgreSQL | Schema and metadata management |
| **Real-time Cache** | Redis | 5-minute slot management |
| **Visualization** | Streamlit | Business dashboards |
| **Infrastructure Monitoring** | Prometheus + Grafana | Metrics collection, alerting |
| **AI Processing** | YOLO + STLinear | Vehicle detection, congestion prediction |
| **Camera Agents** | gRPC | Lightweight metrics streaming from camera nodes |

---

## Project Structure

```
traffic-lakehouse/
│
├── docker-compose.yml                  # Compute node: PostgreSQL, Iceberg REST, Trino,
│                                      #   Zookeeper, Kafka, Redis, Kafka UI, gRPC Server,
│                                      #   Kafka Exporter
│
├── .env.compute.example               # Environment template for compute node
│
├── aggregate_slot.py                  # Standalone Python CLI: aggregates 5-min slot data
│                                      #   from S3 (frames, speed, weather) into JSON
│
├── batch_flow_s3.groovy               # NiFi Groovy script: batch aggregation from S3
│                                      #   (reads manifest/speed/weather, outputs combined JSON)
├── update_time_ingest_s3.groovy       # NiFi Groovy script: ingest pipeline S3 path gen
├── update_time_batch_s3.groovy        # NiFi Groovy script: batch pipeline S3 path gen
│
├── lakehouse/
│   ├── docker-compose.yml             # Storage node: SeaweedFS with S3 API
│   ├── s3.json.example               # SeaweedFS S3 credentials template
│   ├── .env.lakehouse.example        # Lakehouse environment template
│   └── update_time_ingest_s3.groovy  # Duplicate groovy script (ingest pipeline)
│
├── compute-configs/
│   └── trino/
│       ├── config.properties          # Trino coordinator settings (port 8080, spill)
│       ├── jvm.config                 # JVM: 3GB heap, G1GC, jvmkill
│       └── catalog/
│           └── iceberg.properties      # Iceberg REST catalog connector (S3 + PostgreSQL)
│
├── monitoring/
│   ├── docker-compose.monitor.yml     # Monitoring: Prometheus, Grafana, Node Exporter,
│   │                                   #   Kafka Exporter, Redis Exporter
│   ├── .env.monitoring.example        # Environment template for monitoring
│   ├── deploy.sh                      # Automated monitoring deployment script
│   ├── MONITORING.md                  # Full monitoring system documentation
│   ├── Dockerfile.server              # Builds gRPC metrics server container
│   ├── Dockerfile.agent               # Builds camera agent container
│   ├── config_server.env              # gRPC server environment variables
│   ├── requirements.txt              # gRPC server Python dependencies
│   │
│   ├── prometheus/
│   │   ├── prometheus.yml             # Scrape config: NiFi (JWT), Node Exporter,
│   │   │                               #   Kafka Exporter, Redis Exporter
│   │   ├── alert_rules.yml            # 11 alert rules (4 groups: NiFi pipeline,
│   │   │                               #   NiFi JVM, system, Kafka)
│   │   └── README.md                   # Notes on nifi_token generation
│   │
│   ├── grafana/
│   │   └── provisioning/
│   │       ├── datasources/
│   │       │   └── prometheus.yml     # Auto-provisioned Prometheus datasource
│   │       └── dashboards/
│   │           ├── dashboards.yml      # Dashboard provisioning config
│   │           ├── nifi-traffic-pipeline.json   # Main NiFi pipeline dashboard
│   │           ├── nifi-traffic-pipeline-old.txt
│   │           ├── node-exporter-full.json     # Node Exporter system metrics
│   │           ├── redis-monitor.json          # Redis monitoring
│   │           ├── kafka-cluster-monitor.json   # Kafka consumer lag & offsets
│   │           └── camera-monitoring.json.bak   # Backup
│   │
│   ├── scripts/
│   │   └── refresh_nifi_token.sh      # JWT token refresh for NiFi Prometheus endpoint
│   │
│   ├── grpc_server/
│   │   └── server.py                  # gRPC server: receives agent metrics, produces
│   │                                   #   to Kafka, exposes Prometheus metrics on :50052
│   │
│   ├── agent/
│   │   ├── agent.py                   # Camera agent: collects CPU/RAM/disk/net metrics,
│   │   │                               #   streams to gRPC server (bidirectional)
│   │   ├── collect.py                  # MetricCollector: CPU %, RAM %, disk I/O, net I/O
│   │   └── requirements.txt            # Agent Python dependencies
│   │
│   └── protobuf/
│       ├── monitoring.proto            # gRPC service definition
│       ├── monitoring_pb2.py          # Generated protobuf code
│       └── monitoring_pb2_grpc.py      # Generated gRPC stubs
│
├── tphcm-traffic-dashboard/
│   ├── app.py                         # Streamlit main entry (4 dashboard navigation)
│   ├── Dockerfile                      # Builds Streamlit dashboard container
│   ├── docker-compose.yml              # Dashboard compose
│   ├── .env                            # Environment config (TRINO_* vars)
│   ├── .env.example                    # Environment template
│   ├── requirements.txt               # Streamlit + Trino + plotting deps
│   │
│   ├── .streamlit/
│   │   └── config.toml               # Streamlit server config (dark theme)
│   │
│   ├── pages/
│   │   ├── D1_Traffic_Map.py         # KPI overview: active cameras, volume, speed
│   │   ├── D2_Traffic_Heatmap.py    # Hourly/day-of-week heatmap patterns
│   │   ├── D3_Speed_Analysis.py      # Speed distribution, workday vs weekend
│   │   ├── D4_Weather_Impact.py      # Weather condition correlation
│   │   └── D5_Weekly_Monthly_Trend.py # Long-term trend analysis (planned)
│   │
│   ├── utils/
│   │   ├── config.py                  # Env loader, 21 HCMC districts, color palettes
│   │   ├── database.py                # Trino client + demo data generators
│   │   ├── cache_utils.py             # Caching helpers
│   │   └── chart_utils.py             # Chart config and styling
│   │
│   └── styles/
│       ├── custom.css                # Dark theme CSS
│       └── light_mode.css
│
└── schema/
    ├── create_iceberg_table.sql      # Creates traffic.events table (PARQUET, partitioned)
    ├── create_predicts_table.sql      # Creates traffic.predicts table
    ├── insert_predicts_sample.sql     # Sample data for predictions table
    └── batch_to_iceberg_jolt.json     # JOLT transformation spec for batch-to-Iceberg
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose v2
- 2 VPS instances (Storage + Compute)
- Storage VPS: ~2GB RAM, 50GB SSD
- Compute VPS: ~8GB RAM, 100GB SSD

### 1. Clone and Setup

```bash
git clone https://github.com/Flourish04/traffic-lakehouse.git
cd traffic-lakehouse
```

### 2. Configure Environment Variables

```bash
# Compute node
cp .env.compute.example .env.compute
# Edit .env.compute — set STORAGE_HOST, COMPUTE_PUBLIC_HOST, POSTGRES_PASSWORD,
#   S3_ACCESS_KEY, S3_SECRET_KEY, NIFI_USER, NIFI_PASS, GF_SECURITY_ADMIN_PASSWORD

# Lakehouse (Storage VPS)
cp lakehouse/.env.lakehouse.example lakehouse/.env.lakehouse
cp lakehouse/s3.json.example lakehouse/s3.json
# Edit lakehouse/s3.json — set your actual S3 credentials
```

### 3. Deploy Storage Node (Storage VPS)

```bash
cd lakehouse
docker compose up -d
```

### 4. Deploy Compute Node (Compute VPS)

```bash
# Generate NiFi JWT token first
source .env.compute
./monitoring/scripts/refresh_nifi_token.sh

# Start all services
docker compose -f docker-compose.yml --env-file .env.compute up -d
```

### 5. Deploy Monitoring (Compute VPS)

```bash
cp monitoring/.env.monitoring.example .env.monitoring
docker compose -f monitoring/docker-compose.monitor.yml --env-file .env.monitoring up -d
```

### 6. Deploy Dashboard

```bash
cd tphcm-traffic-dashboard
cp .env.example .env
docker compose up -d
# Access at http://localhost:8501
```

---

## Dashboards

| Dashboard | Description | Auto-refresh |
|-----------|-------------|--------------|
| **D1 - Traffic Map** | KPI overview: active cameras, total volume, avg speed, congestion rate | 5 min |
| **D2 - Traffic Heatmap** | Hourly/day-of-week heatmap patterns | 15 min |
| **D3 - Speed Analysis** | Speed distribution, workday vs weekend comparison | 10 min |
| **D4 - Weather Impact** | Weather condition correlation with traffic metrics | 15 min |

---

## Data Schema

### `iceberg.traffic.events`
Primary traffic event table with semi-structured schema: flatten fields plus `speed_series ARRAY(ROW)` and `weather ROW(STRUCT)` from OpenWeatherMap. PARQUET format, partitioned by day and camera_id.

### `iceberg.traffic.cameras`
Camera metadata: ID, display name, district, status.

### `iceberg.traffic.predicts`
ML prediction results per camera/slot: predicted vehicle counts and average speeds.

---

## Monitoring

Prometheus scrape targets:
- **NiFi** — JWT-authenticated via `/nifi-api/flow/metrics/prometheus` (token generated by `refresh_nifi_token.sh`)
- **Node Exporter** — CPU, RAM, disk I/O, network I/O per host
- **Kafka Exporter** — Consumer lag and topic offsets
- **Redis Exporter** — Memory, keys, hits/misses
- **gRPC Server** — Prometheus metrics endpoint on `:50052`

11 alert rules in 4 groups:
1. **NiFi Pipeline** — queue backpressure, stalled pipelines, processor errors
2. **NiFi JVM** — heap usage, thread count
3. **System** — CPU load, RAM usage, disk I/O
4. **Kafka** — consumer lag, no messages received

---

## Security

- **No secrets in source code**: All credentials loaded from environment variables
- **No hardcoded JWT tokens**: NiFi token generated at runtime by `refresh_nifi_token.sh`
- **No private IPs in config**: All host addresses use `${VARIABLE}` syntax
- **Git-excluded**: `.env`, `s3.json`, `nifi_token`, `data/`, `logs/`, `.venv/`, `__pycache__/`, `node_modules/`, build artifacts
- **Template files**: `.env.*.example`, `s3.json.example` show required config without exposing real values

