# Monitoring System - NiFi Traffic Pipeline

Tài liệu mô tả chi tiết hệ thống giám sát (monitoring) cho pipeline thu thập dữ liệu giao thông
sử dụng **Prometheus + Grafana + Node Exporter**, triển khai trên **Compute VPS**.

---

## 1. Tổng quan kiến trúc

```
┌─────────────────────────────── Compute VPS ───────────────────────────────┐
│                                                                           │
│  ┌──────────────────┐         ┌──────────────────┐                        │
│  │  Apache NiFi 2.8 │         │   Node Exporter  │                        │
│  │  (bare metal)    │         │   (Docker)       │                        │
│  │  :8443 (HTTPS)   │         │   :9100          │                        │
│  └────────┬─────────┘         └────────┬─────────┘                        │
│           │ /nifi-api/flow/             │ /metrics                         │
│           │ metrics/prometheus          │                                  │
│           ▼                             ▼                                  │
│  ┌──────────────────────────────────────────────┐                         │
│  │              Prometheus (Docker)              │                         │
│  │              network_mode: host               │                         │
│  │              :9090                             │                         │
│  │  ┌────────────────┐  ┌─────────────────────┐  │                        │
│  │  │ job: nifi       │  │ job: node-compute   │  │                        │
│  │  │ scrape: 30s     │  │ scrape: 15s         │  │                        │
│  │  │ Bearer JWT      │  │                     │  │                        │
│  │  └────────────────┘  └─────────────────────┘  │                        │
│  └────────────────────────┬──────────────────────┘                        │
│                           │                                                │
│                           ▼                                                │
│  ┌──────────────────────────────────────────────┐                         │
│  │              Grafana (Docker)                 │                         │
│  │              bridge network                   │                         │
│  │              :3000                             │                         │
│  │                                               │                         │
│  │  Datasource: http://host.docker.internal:9090 │                        │
│  │  Dashboard:  NiFi Traffic Pipeline Monitor    │                         │
│  └───────────────────────────────────────────────┘                        │
│                                                                           │
│  ┌──────────────────────────────────────────────┐                         │
│  │  Cron Job (host)                              │                         │
│  │  refresh_nifi_token.sh                        │                         │
│  │  Mỗi 2 tiếng + @reboot                       │                         │
│  └───────────────────────────────────────────────┘                        │
└───────────────────────────────────────────────────────────────────────────┘
```

### Tại sao chọn kiến trúc này?

| Quyết định | Lý do |
|:--|:--|
| NiFi chạy bare metal (systemd) | Đã cài sẵn từ .deb package, cần truy cập trực tiếp phần cứng |
| Monitoring stack chạy Docker | Dễ triển khai, cách ly, cập nhật, không ảnh hưởng NiFi |
| Prometheus dùng `network_mode: host` | Cần truy cập NiFi tại `localhost:8443` (HTTPS + SNI yêu cầu hostname) |
| Grafana dùng bridge network | Chỉ cần expose port 3000, kết nối Prometheus qua `host.docker.internal` |
| Token refresh qua cron | JWT token NiFi hết hạn sau 8h, cron mỗi 2h đảm bảo luôn hợp lệ |

---

## 2. Cấu trúc thư mục

```
monitoring/
├── docker-compose.yml                              # Định nghĩa 3 services
├── deploy.sh                                        # Script triển khai tự động
├── MONITORING.md                                    # Tài liệu (file này)
├── prometheus/
│   ├── prometheus.yml                               # Cấu hình scrape targets
│   ├── alert_rules.yml                              # Quy tắc cảnh báo
│   └── nifi_token                                   # JWT token (tự sinh, không commit)
├── scripts/
│   └── refresh_nifi_token.sh                        # Script làm mới JWT token
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── prometheus.yml                       # Auto-provision datasource
        └── dashboards/
            ├── dashboards.yml                       # Config load dashboard
            └── nifi-traffic-pipeline.json           # Dashboard chính (3-tier)
```

---

## 3. Thành phần chi tiết

### 3.1. Prometheus

**Image:** `prom/prometheus:v2.53.3`

**Vai trò:** Thu thập (scrape) metrics từ NiFi và Node Exporter, lưu trữ time-series data,
đánh giá alert rules.

**Cấu hình chính** (`prometheus/prometheus.yml`):

```yaml
global:
  scrape_interval: 15s      # Mặc định scrape mỗi 15 giây
  evaluation_interval: 15s  # Đánh giá alert mỗi 15 giây
```

**Hai scrape targets:**

| Job | Target | Scheme | Auth | Interval | Mô tả |
|:----|:-------|:-------|:-----|:---------|:------|
| `nifi` | `localhost:8443` | HTTPS | Bearer JWT | 30s | Metrics từ NiFi REST API |
| `node-compute` | `127.0.0.1:9100` | HTTP | Không | 15s | Metrics hệ thống (CPU, RAM, Disk) |

**Lưu trữ:**
- Retention: 30 ngày hoặc 5GB (cái nào chạm trước)
- Volume: `monitoring_prometheus_data`

#### Cách Prometheus lấy metrics từ NiFi

NiFi 2.x có endpoint Prometheus tích hợp sẵn (không cần cài thêm ReportingTask):

```
GET https://localhost:8443/nifi-api/flow/metrics/prometheus
Authorization: Bearer <JWT_TOKEN>
```

Endpoint này trả về ~59 metrics ở định dạng Prometheus text, bao gồm:

| Nhóm | Metrics tiêu biểu |
|:-----|:-------------------|
| FlowFile | `nifi_amount_flowfiles_received`, `nifi_amount_flowfiles_sent`, `nifi_amount_items_queued` |
| Bytes | `nifi_amount_bytes_read`, `nifi_amount_bytes_written`, `nifi_size_content_queued_total` |
| Processing | `nifi_amount_threads_active`, `nifi_total_task_duration`, `nifi_average_lineage_duration` |
| Backpressure | `nifi_percent_used_count`, `nifi_percent_used_bytes`, `nifi_backpressure_*_threshold` |
| Repository | `nifi_content_repo_*_space_bytes`, `nifi_flow_file_repo_*_space_bytes`, `nifi_provenance_repo_*` |
| JVM | `nifi_jvm_uptime`, `nifi_jvm_heap_used`, `nifi_jvm_heap_usage`, `nifi_jvm_gc_*` |

Mỗi metric có các labels quan trọng:

| Label | Giá trị | Ý nghĩa |
|:------|:--------|:---------|
| `component_type` | `RootProcessGroup`, `ProcessGroup`, `Processor`, `Connection` | Loại component |
| `component_name` | Tên component (VD: `IMAGE_INGESTION`, `InvokeHTTP`) | Tên hiển thị |
| `component_id` | UUID | ID duy nhất |
| `parent_id` | UUID | ID của Process Group cha |

#### Lưu ý kỹ thuật quan trọng

**SNI (Server Name Indication):** NiFi Jetty chỉ chấp nhận SNI hostname `localhost`.
Không thể dùng IP `127.0.0.1` làm target vì Jetty trả về `400 Invalid SNI`.
Vì vậy Prometheus **phải** dùng `network_mode: host` và target `localhost:8443`.

**IPv4/IPv6:** File `/etc/hosts` trên VPS cần đảm bảo `localhost` resolve sang `127.0.0.1` (IPv4),
không phải `::1` (IPv6). NiFi chỉ listen trên IPv4.

```bash
# Nếu gặp lỗi "connection refused", kiểm tra:
grep localhost /etc/hosts
# Dòng "::1 localhost" cần được comment:
# ::1 localhost
```

---

### 3.2. JWT Token Refresh

**Script:** `scripts/refresh_nifi_token.sh`

NiFi 2.x yêu cầu Bearer JWT token cho mọi API call. Token có TTL = 8 giờ.

**Luồng hoạt động:**

```
1. Kiểm tra NiFi có phản hồi không (health check)
2. Gọi POST /nifi-api/access/token với username/password
3. Validate token format (header.payload.signature)
4. Ghi token vào file (không có newline ở cuối)
5. Retry tối đa 3 lần nếu thất bại
```

**Cron schedule:**

```
0 */2 * * *   refresh_nifi_token.sh    # Mỗi 2 giờ
@reboot       sleep 60 && refresh_...  # 60s sau khi VPS khởi động lại
```

Token được ghi vào `prometheus/nifi_token`, Prometheus mount file này ở `/tmp/nifi_token`
và tự đọc lại mỗi lần scrape.

**Tại sao dùng `printf '%s'` thay vì `echo`?**
`echo` tự thêm ký tự newline `\n` ở cuối. Bearer token chứa newline sẽ bị NiFi reject (400 Bad Request).
`printf '%s'` ghi chính xác nội dung token, không thêm ký tự thừa.

**Log:** `/var/log/nifi_token_refresh.log`

---

### 3.3. Node Exporter

**Image:** `prom/node-exporter:v1.8.2`

**Vai trò:** Thu thập metrics hệ thống của Compute VPS (CPU, RAM, disk, network, I/O).

**Cấu hình đặc biệt:**
- `network_mode: host` + `pid: host`: Truy cập đầy đủ metrics hệ thống
- Mount `/proc`, `/sys`, `/` ở chế độ read-only
- Loại trừ mount points hệ thống (`/sys`, `/proc`, `/dev`, etc.)

**Dashboard riêng:** Import dashboard ID `1860` (Node Exporter Full) từ Grafana.com
để có giao diện chi tiết cho metrics hệ thống.

---

### 3.4. Grafana

**Image:** `grafana/grafana:11.4.0`

**Vai trò:** Trực quan hóa metrics, hiển thị dashboard, cảnh báo.

**Cấu hình:**
- Port: `3000`
- Login: `admin` / `changeme123`
- Timezone: `Asia/Ho_Chi_Minh`
- Datasource: Auto-provisioned, trỏ đến Prometheus qua `http://host.docker.internal:9090`

**Auto-provisioning:** Grafana tự động load datasource và dashboard từ thư mục provisioning
khi khởi động, không cần import thủ công.

Grafana chạy trên **bridge network** (không phải host network) vì chỉ cần expose port 3000.
Kết nối đến Prometheus thông qua `host.docker.internal` (resolve sang host IP nhờ `extra_hosts`).

---

## 4. Dashboard: NiFi Traffic Pipeline Monitor

Dashboard được thiết kế theo nguyên tắc **Top-Down 3-Tier Admin** - từ tổng quan đến chi tiết:

```
┌─────────────────────────────────────────────────────────────────┐
│ TẦNG 1: TỔNG QUAN HỆ THỐNG                                     │
│ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ ┌─────┐ ┌─────┐│
│ │ Active   │ │ FlowFiles│ │  Bytes   │ │Uptime│ │Cont.│ │Flow │││
│ │ Threads  │ │  Queued  │ │  Queued  │ │      │ │Repo │ │Repo │││
│ └─────────┘ └──────────┘ └──────────┘ └──────┘ └─────┘ └─────┘│
├─────────────────────────────────────────────────────────────────┤
│ TẦNG 2: SỨC KHỎE 5 PROCESS GROUP  (so sánh tất cả PG)         │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│ │ Items Queued  │ │ Queue Bytes  │ │ Throughput   │    Bar      │
│ │ (bar gauge)   │ │ (bar gauge)  │ │ (bar gauge)  │   Gauges   │
│ └──────────────┘ └──────────────┘ └──────────────┘             │
│ ┌──────────────────────┐ ┌──────────────────────┐              │
│ │ FlowFiles In vs Out  │ │ Active Threads       │  Timeseries  │
│ │ (per PG)             │ │ (stacked per PG)     │              │
│ └──────────────────────┘ └──────────────────────┘              │
│ ┌──────────────────────────────────────────────────┐           │
│ │ Backpressure % (Connections > 0%)                │           │
│ └──────────────────────────────────────────────────┘           │
├─────────────────────────────────────────────────────────────────┤
│ TẦNG 3: CHẨN ĐOÁN - [$process_group dropdown]                  │
│ ┌───────┐ ┌──────┐ ┌───────┐ ┌─────┐ ┌─────┐ ┌──────┐        │
│ │Thread │ │Queued│ │Q.Size │ │In/s │ │Out/s│ │Write │  Stats  │
│ └───────┘ └──────┘ └───────┘ └─────┘ └─────┘ └──────┘        │
│ ┌──────────────────────┐ ┌──────────────────────┐              │
│ │ Queue Trend          │ │ Throughput In vs Out  │  PG-level   │
│ └──────────────────────┘ └──────────────────────┘              │
│ ┌──────────────────────┐ ┌──────────────────────┐              │
│ │ Processors: Sent/s   │ │ Processors: Queued   │  Processor   │
│ ├──────────────────────┤ ├──────────────────────┤  drill-down  │
│ │ Processors: Write/s  │ │ Processors: Duration │              │
│ └──────────────────────┘ └──────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### Cách sử dụng

| Tầng | Mục đích | Filter |
|:-----|:---------|:-------|
| **Tầng 1** | Nhìn nhanh 5 giây: hệ thống có đang khỏe không? | Không filter - luôn hiện global |
| **Tầng 2** | So sánh 5 PG: cái nào đang tắc, cái nào chạy tốt? | Không filter - luôn hiện cả 5 PG |
| **Tầng 3** | Drill-down: PG bị tắc thì processor nào gây ra? | Dropdown `$process_group` |

### Cách đọc dashboard

**Tầng 1 - 5 giây đầu tiên:**
- Active Threads **xanh** → pipeline đang chạy
- FlowFiles Queued **xanh** → không tắc nghẽn
- Uptime hiển thị thời gian NiFi đã chạy liên tục
- Content/FlowFile Repo cho biết dung lượng repository

**Tầng 2 - Tìm PG có vấn đề:**
- Bar gauge "Items Queued" → thanh dài nhất = PG tắc nhất
- Bar gauge "Throughput" → thanh ngắn nhất hoặc = 0 = PG chết
- FlowFiles In vs Out → IN > OUT kéo dài = bottleneck
- Backpressure > 50% (vàng) hoặc > 80% (đỏ) = connection sắp bị block

**Tầng 3 - Chẩn đoán PG cụ thể:**
1. Chọn PG bị nghi ở dropdown trên cùng
2. 6 stat cards cho overview nhanh của PG đó
3. Queue Trend dốc lên = PG đang chết dần
4. 4 panel Processor: tìm chính xác processor nào gây nghẽn

### Kỹ thuật PromQL đáng chú ý

**Gộp duplicate series** - NiFi có thể export nhiều series cùng tên PG:
```promql
sum by (component_name) (nifi_amount_items_queued{
  component_type="ProcessGroup",
  component_name=~"IMAGE_INGESTION|..."
})
```

**Drill-down Processor** - Lấy processors thuộc PG cụ thể bằng `label_replace` + join:
```promql
rate(nifi_amount_flowfiles_sent{component_type="Processor"}[5m])
  and on(parent_id)
  label_replace(
    nifi_amount_flowfiles_sent{
      component_type="ProcessGroup",
      component_name=~"$process_group"
    },
    "parent_id", "$1", "component_id", "(.*)"
  )
```

Giải thích: Processor có `parent_id` = ID của PG chứa nó. ProcessGroup có `component_id`.
`label_replace` copy `component_id` của PG vào label `parent_id`,
rồi `and on(parent_id)` chỉ giữ lại Processors có `parent_id` khớp → đúng PG đang chọn.

---

## 5. Alert Rules

Hệ thống có 3 nhóm cảnh báo trong `prometheus/alert_rules.yml`:

### 5.1. NiFi Pipeline Alerts

| Alert | Điều kiện | Severity | Ý nghĩa |
|:------|:----------|:---------|:---------|
| `NiFiQueueBackPressure` | FlowFiles queued > 1000 trong 5 phút | Warning | Queue đang tắc nghẽn |
| `NiFiPipelineStalled` | FlowFiles sent/10m = 0 trong 15 phút | Critical | Pipeline ngừng hoạt động hoàn toàn |
| `NiFiProcessorErrors` | FlowFiles gửi đến connection "failure" > 0 trong 5 phút | Warning | Processor đang lỗi |

### 5.2. NiFi JVM Alerts

| Alert | Điều kiện | Severity | Hành động |
|:------|:----------|:---------|:----------|
| `NiFiHighHeapUsage` | Heap > 80% trong 5 phút | Warning | Xem xét tăng `-Xmx` trong `bootstrap.conf` |
| `NiFiCriticalHeapUsage` | Heap > 92% trong 2 phút | Critical | Tăng heap ngay hoặc giảm concurrent tasks |
| `NiFiHighThreadCount` | Active threads > 150 trong 5 phút | Warning | Kiểm tra processor concurrency settings |

### 5.3. System Alerts

| Alert | Điều kiện | Severity |
|:------|:----------|:---------|
| `HighCPUUsage` | CPU > 85% trong 10 phút | Warning |
| `CriticalCPUUsage` | CPU > 95% trong 5 phút | Critical |
| `LowMemory` | RAM used > 85% trong 5 phút | Warning |
| `CriticalMemory` | RAM available < 300MB trong 5 phút | Critical |
| `DiskAlmostFull` | Disk > 80% trong 5 phút | Warning |
| `DiskCritical` | Disk > 90% trong 5 phút | Critical |

---

## 6. Network Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Host Network (VPS)                         │
│                                                               │
│   NiFi (:8443)  ◄──HTTPS+JWT──  Prometheus (:9090)           │
│                                        ▲                      │
│   Node Exporter (:9100)  ──HTTP──────►─┘                      │
│                                                               │
│   ┌────────────── Bridge Network ──────────────┐              │
│   │                                             │              │
│   │  Grafana (:3000)                            │              │
│   │     │                                       │              │
│   │     └── http://host.docker.internal:9090 ──►│──► Prom      │
│   │                                             │              │
│   └─────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

| Service | Network Mode | Lý do |
|:--------|:-------------|:------|
| Prometheus | `host` | Cần gọi `localhost:8443` (NiFi yêu cầu SNI=localhost) |
| Node Exporter | `host` | Cần truy cập `/proc`, `/sys`, PID namespace của host |
| Grafana | `bridge` | Chỉ expose port 3000, dùng `host.docker.internal` để gọi Prometheus |

---

## 7. Triển khai

### 7.1. Triển khai tự động (khuyến nghị)

```bash
# Từ máy local, copy toàn bộ thư mục lên VPS
scp -r ./monitoring/ root@<VPS_IP>:~/infra/nifi/monitoring/

# SSH vào VPS và chạy deploy script
ssh root@<VPS_IP>
cd ~/infra/nifi/monitoring
chmod +x deploy.sh scripts/refresh_nifi_token.sh
bash deploy.sh
```

Deploy script tự động:
1. Kiểm tra Docker, NiFi
2. Refresh JWT token lần đầu
3. Cài cron job
4. Pull images + start Docker Compose
5. Kiểm tra Prometheus targets

### 7.2. Triển khai thủ công

```bash
# 1. Refresh token
bash scripts/refresh_nifi_token.sh

# 2. Start stack
docker compose up -d

# 3. Cài cron
crontab -e
# Thêm:
# 0 */2 * * * /root/infra/nifi/monitoring/scripts/refresh_nifi_token.sh >> /var/log/nifi_token_refresh.log 2>&1
# @reboot sleep 60 && /root/infra/nifi/monitoring/scripts/refresh_nifi_token.sh >> /var/log/nifi_token_refresh.log 2>&1
```

### 7.3. Kiểm tra sau triển khai

```bash
# Prometheus targets
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep health

# NiFi metrics count
curl -s http://localhost:9090/api/v1/label/__name__/values | python3 -m json.tool | grep nifi | wc -l

# Grafana API
curl -s -u admin:changeme123 http://localhost:3000/api/search?query=NiFi

# Token refresh log
tail -5 /var/log/nifi_token_refresh.log
```

---

## 8. Troubleshooting

### Token hết hạn → Prometheus scrape fail

**Triệu chứng:** Target `nifi` status = `down`, error = `401 Unauthorized`

```bash
# Kiểm tra token
cat ~/infra/nifi/monitoring/prometheus/nifi_token | wc -c  # > 0

# Refresh thủ công
bash ~/infra/nifi/monitoring/scripts/refresh_nifi_token.sh

# Kiểm tra cron
crontab -l | grep nifi
```

### NiFi không phản hồi → Connection refused

**Triệu chứng:** Target `nifi` error = `connection refused`

```bash
# NiFi có đang chạy không?
systemctl status nifi

# Kiểm tra port
ss -tlnp | grep 8443

# Kiểm tra IPv4/IPv6
grep localhost /etc/hosts
# Đảm bảo dòng "::1 localhost" đã được comment
```

### Invalid SNI

**Triệu chứng:** Target `nifi` error = `400 Invalid SNI`

Nguyên nhân: Prometheus dùng IP thay vì hostname.
Đảm bảo target trong `prometheus.yml` là `localhost:8443`, KHÔNG phải `127.0.0.1:8443`.

### Dashboard hiển thị "No data"

```bash
# 1. Kiểm tra datasource UID khớp
grep uid grafana/provisioning/datasources/prometheus.yml
# Phải = d5c98e6b-995d-49b0-a229-205b495c7caf

# 2. Kiểm tra Prometheus có data
curl -s 'http://localhost:9090/api/v1/query?query=nifi_amount_items_queued' | python3 -m json.tool | head -20

# 3. Kiểm tra Grafana kết nối được Prometheus
curl -s -u admin:changeme123 http://localhost:3000/api/datasources/proxy/1/api/v1/query?query=up
```

### Duplicate entries trong bar gauge

Nguyên nhân: NiFi export nhiều time series cho cùng 1 PG (khác `component_id`).
Giải pháp: Dùng `sum by (component_name)` trong PromQL (đã áp dụng trong dashboard v6).

---

## 9. Bảo trì

### Cập nhật dashboard

```bash
# Sửa file JSON trên local
vim grafana/provisioning/dashboards/nifi-traffic-pipeline.json

# Copy lên VPS
scp grafana/provisioning/dashboards/nifi-traffic-pipeline.json root@<VPS_IP>:~/infra/nifi/monitoring/grafana/provisioning/dashboards/

# Restart Grafana
ssh root@<VPS_IP> "cd ~/infra/nifi/monitoring && docker compose restart grafana"
```

### Backup dữ liệu Prometheus

```bash
# Snapshot API
curl -XPOST http://localhost:9090/api/v1/admin/tsdb/snapshot

# Hoặc backup volume
docker run --rm -v monitoring_prometheus_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/prometheus_backup.tar.gz /data
```

### Xem log

```bash
# Tất cả services
docker compose logs -f

# Chỉ Prometheus
docker compose logs -f prometheus

# Token refresh
tail -f /var/log/nifi_token_refresh.log
```

---

## 10. Danh sách file và phiên bản

| File | Phiên bản | Mô tả |
|:-----|:----------|:------|
| `docker-compose.yml` | - | 3 services: Prometheus, Grafana, Node Exporter |
| `prometheus/prometheus.yml` | - | 2 jobs: nifi (HTTPS+JWT), node-compute |
| `prometheus/alert_rules.yml` | - | 3 groups, 11 rules |
| `scripts/refresh_nifi_token.sh` | - | JWT refresh, retry 3x, validate format |
| `grafana/.../prometheus.yml` | - | Datasource UID: `d5c98e6b-...` |
| `grafana/.../nifi-traffic-pipeline.json` | v8 | 24 panels, 3-tier, `parent_id` top-level filter, JVM Heap + NiFi Status |
| `deploy.sh` | - | Automated deployment script |

| Docker Image | Version |
|:-------------|:--------|
| Prometheus | `v2.53.3` |
| Grafana | `11.4.0` |
| Node Exporter | `v1.8.2` |

| Phần mềm bên ngoài | Version |
|:--------------------|:--------|
| Apache NiFi | `2.8.0` (bare metal, .deb) |

---

## 11. Process Groups được giám sát

Pipeline xử lý dữ liệu giao thông từ 23 camera tại TP.HCM.

**5 Process Group chính (top-level):**

```
23 Camera API + Weather API + TomTom API
     │
     ▼
┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐
│ IMAGE_INGESTION  │  │ SPEED_INGESTION  │  │ WEATHER_INGESTION  │
│ Thu thập ảnh     │  │ Thu thập vận tốc │  │ Thu thập thời tiết │
└────────┬─────────┘  └────────┬─────────┘  └─────────┬──────────┘
         │                     │                       │
         └─────────────────────┼───────────────────────┘
                               ▼
                     ┌──────────────────┐    ┌──────┐
                     │     BATCHING     │───►│  AI  │
                     │    Gom batch     │    │      │
                     └──────────────────┘    └──────┘
```

**Lưu ý:** Mỗi top-level PG chứa các sub-PG bên trong (VD: DISPATCHER, RAW_INGESTION,
BATCH_INGESTION...). Dashboard giám sát 5 top-level PG theo tên chính xác.
