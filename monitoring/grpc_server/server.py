import os
import grpc
import json
import time
import threading
from concurrent import futures

try:
    from protobuf import monitoring_pb2, monitoring_pb2_grpc
except ImportError:
    import subprocess, sys
    print("[WARN] protobuf modules not found, attempting to generate...")
    result = subprocess.run(
        ["python", "-m", "grpc_tools.protoc",
         "-I./protobuf", "--python_out=./protobuf", "--grpc_python_out=./protobuf",
         "./protobuf/monitoring.proto"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[ERROR] Failed to generate protobuf: {result.stderr}")
        sys.exit(1)
    sys.path.insert(0, os.path.dirname(__file__))
    from protobuf import monitoring_pb2, monitoring_pb2_grpc

from prometheus_client import start_http_server, Counter, Histogram, Gauge
from google.protobuf.struct_pb2 import Struct
from google.protobuf.json_format import MessageToDict
from confluent_kafka import Producer

# ============================================================
# Prometheus Metrics
# ============================================================
METRICS_PORT = int(os.getenv("GRPC_METRICS_PORT", "50052"))

messages_received_total = Counter(
    "camera_metrics_received_total",
    "Total metrics messages received from agents",
    ["hostname"]
)
messages_produced_total = Counter(
    "camera_metrics_produced_total",
    "Total metrics messages produced to Kafka"
)
messages_failed_total = Counter(
    "camera_metrics_produced_failed_total",
    "Failed metrics messages to Kafka"
)
command_sent_total = Counter(
    "camera_commands_sent_total",
    "Total commands sent to agents",
    ["command_type"]
)
processing_duration_seconds = Histogram(
    "camera_grpc_processing_seconds",
    "Time spent processing each metrics message",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)
active_agents = Gauge("camera_active_agents", "Number of agents currently connected")

# ============================================================
# Kafka Producer (singleton)
# ============================================================
_producer_lock = threading.Lock()
_producer = None

def get_kafka_producer(bootstrap_servers: str) -> Producer:
    global _producer
    if _producer is None:
        with _producer_lock:
            if _producer is None:
                _producer = Producer({"bootstrap.servers": bootstrap_servers})
    return _producer


# ============================================================
# gRPC Servicer
# ============================================================
class MonitoringServicer(monitoring_pb2_grpc.MonitoringServicer):
    def __init__(self, kafka_bootstrap_servers: str, monitoring_topic: str):
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.monitoring_topic = monitoring_topic
        self._active_agents_lock = threading.Lock()
        self._seen_agents = set()

    def StreamMetrics(self, request_iterator, context):
        producer = get_kafka_producer(self.kafka_bootstrap_servers)
        flush_counter = 0

        for request in request_iterator:
            start = time.time()

            hostname = request.hostname
            messages_received_total.labels(hostname=hostname).inc()

            with self._active_agents_lock:
                if hostname not in self._seen_agents:
                    self._seen_agents.add(hostname)
                    active_agents.set(len(self._seen_agents))

            try:
                producer.produce(
                    self.monitoring_topic,
                    key=hostname.encode("utf-8"),
                    value=json.dumps({
                        "hostname": hostname,
                        "timestamp": request.timestamp,
                        "metrics": {
                            "cpu_percent": request.metrics.cpu_percent,
                            "memory_percent": request.metrics.memory_percent,
                            "memory_used_mb": request.metrics.memory_used_mb,
                            "memory_total_mb": request.metrics.memory_total_mb,
                            "disk_read_mb": request.metrics.disk_read_mb,
                            "disk_write_mb": request.metrics.disk_write_mb,
                            "net_in_mb": request.metrics.net_in_mb,
                            "net_out_mb": request.metrics.net_out_mb,
                        },
                        "metadata": MessageToDict(request.metadata),
                    }).encode("utf-8"),
                )
                flush_counter += 1
                if flush_counter % 10 == 0:
                    producer.flush(timeout=1.0)
                messages_produced_total.inc()
            except Exception:
                messages_failed_total.inc()

            cpu = request.metrics.cpu_percent
            cmd_type = monitoring_pb2.CommandType.ACK
            cmd_name = "ACK"
            params = Struct()

            if cpu <= 40.0:
                cmd_type = monitoring_pb2.CommandType.CONFIG
                cmd_name = "CONFIG"
                params.update({"interval": 2})
            elif cpu > 70.0 and cpu < 80.0:
                cmd_type = monitoring_pb2.CommandType.CONFIG
                cmd_name = "CONFIG"
                params.update({"interval": 10})
            elif cpu >= 80.0:
                cmd_type = monitoring_pb2.CommandType.DIAGNOSTIC
                cmd_name = "DIAGNOSTIC"
                params.update({"key": "cpu_percent"})

            command_sent_total.labels(command_type=cmd_name).inc()
            processing_duration_seconds.observe(time.time() - start)
            yield monitoring_pb2.Command(type=cmd_type, params=params)


# ============================================================
# Server bootstrap
# ============================================================
def serve():
    grpc_host = os.getenv("GRPC_SERVER_HOST", "0.0.0.0")
    grpc_port = int(os.getenv("GRPC_SERVER_PORT", "50051"))
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monitoring_topic = os.getenv("MONITORING_TOPIC", "metrics")

    # Start Prometheus metrics HTTP server
    start_http_server(METRICS_PORT)
    print(f"[PROMETHEUS] Metrics server on :{METRICS_PORT}/metrics")

    # Kafka producer
    get_kafka_producer(kafka_servers)
    print(f"[KAFKA] Producer connected to {kafka_servers}, topic={monitoring_topic}")

    # gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    monitoring_pb2_grpc.add_MonitoringServicer_to_server(
        MonitoringServicer(kafka_servers, monitoring_topic), server
    )
    server.add_insecure_port(f"{grpc_host}:{grpc_port}")
    server.start()
    print(f"[GRPC] Server listening on {grpc_host}:{grpc_port}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop(0)


if __name__ == "__main__":
    serve()
