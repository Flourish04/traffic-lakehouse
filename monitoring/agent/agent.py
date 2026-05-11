"""
Camera Agent - Nhẹ, chạy trên Storage VPS
Gửi system metrics lên gRPC Server trên Compute VPS.
Không có etcd, không plugin.
"""

import os
import sys
import time
import socket
import grpc
import signal

sys.path.insert(0, os.path.dirname(__file__))

from protobuf import monitoring_pb2, monitoring_pb2_grpc
from google.protobuf.struct_pb2 import Struct
from collect import MetricCollector


def build_metrics_request(hostname: str, metrics: dict) -> monitoring_pb2.MetricsRequest:
    meta = Struct()
    meta.update({"source": "storage-vps", "agent_version": "1.0.0"})
    return monitoring_pb2.MetricsRequest(
        hostname=hostname,
        timestamp=metrics["timestamp"],
        metrics=monitoring_pb2.SystemMetrics(
            cpu_percent=metrics["cpu_percent"],
            memory_percent=metrics["memory_percent"],
            memory_used_mb=metrics["memory_used_mb"],
            memory_total_mb=metrics["memory_total_mb"],
            disk_read_mb=metrics["disk_read_mb"],
            disk_write_mb=metrics["disk_write_mb"],
            net_in_mb=metrics["net_in_mb"],
            net_out_mb=metrics["net_out_mb"],
        ),
        metadata=meta,
    )


def run():
    # --- Config từ env ---
    grpc_host = os.getenv("GRPC_SERVER_HOST", os.getenv("COMPUTE_HOST", "localhost"))
    grpc_port = int(os.getenv("GRPC_SERVER_PORT", "50051"))
    interval = float(os.getenv("COLLECTION_INTERVAL", "5"))
    hostname = os.getenv("AGENT_HOSTNAME", socket.gethostname())

    print(f"[AGENT] Starting agent: hostname={hostname}")
    print(f"[AGENT] gRPC server: {grpc_host}:{grpc_port}")
    print(f"[AGENT] Collection interval: {interval}s")

    # --- Collector ---
    collector = MetricCollector(hostname, interval)

    # --- gRPC channel ---
    channel = grpc.insecure_channel(f"{grpc_host}:{grpc_port}")
    stub = monitoring_pb2_grpc.MonitoringStub(channel)

    # --- Graceful shutdown ---
    def shutdown(signum, frame):
        print("\n[AGENT] Shutting down...")
        channel.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # --- Metrics generator ---
    def metrics_generator():
        while True:
            metrics = collector.collect()
            yield build_metrics_request(hostname, metrics)
            time.sleep(interval)

    # --- Stream metrics, nhận commands ---
    print("[AGENT] Connected. Streaming metrics...")
    try:
        for cmd in stub.StreamMetrics(metrics_generator()):
            if cmd.type == monitoring_pb2.CommandType.CONFIG:
                new_interval = cmd.params.get("interval", interval)
                if new_interval != interval:
                    interval = new_interval
                    collector.interval = interval
                    print(f"[AGENT] Server adjusted interval → {interval}s")
            elif cmd.type == monitoring_pb2.CommandType.DIAGNOSTIC:
                print(f"[AGENT] DIAGNOSTIC command received: {dict(cmd.params)}")
            # ACK: không cần xử lý
    except grpc.RpcError as e:
        print(f"[AGENT] gRPC error: {e.code()} - {e.details()}")
        print("[AGENT] Reconnecting in 5s...")
        time.sleep(5)


if __name__ == "__main__":
    run()
