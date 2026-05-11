"""
MetricCollector - Thu thập system metrics từ Storage VPS
Chỉ dùng psutil, không có etcd hay plugin.
"""

import time
import psutil
from datetime import datetime
from typing import Dict, Any


class MetricCollector:
    def __init__(self, hostname: str, interval: float = 5.0):
        self.hostname = hostname
        self.interval = interval
        self._last_disk_io = psutil.disk_io_counters()
        self._last_net_io = psutil.net_io_counters()
        self._last_time = time.time()

    def collect(self) -> Dict[str, Any]:
        """Thu thập tất cả metrics."""
        now = time.time()
        delta = now - self._last_time
        self._last_time = now

        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()

        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        disk_read_mb = 0.0
        disk_write_mb = 0.0
        net_in_mb = 0.0
        net_out_mb = 0.0

        if self._last_disk_io and disk_io and delta > 0:
            disk_read_mb = max(0, (disk_io.read_bytes - self._last_disk_io.read_bytes) / (1024 * 1024) / delta)
            disk_write_mb = max(0, (disk_io.write_bytes - self._last_disk_io.write_bytes) / (1024 * 1024) / delta)

        if self._last_net_io and net_io and delta > 0:
            net_in_mb = max(0, (net_io.bytes_recv - self._last_net_io.bytes_recv) / (1024 * 1024) / delta)
            net_out_mb = max(0, (net_io.bytes_sent - self._last_net_io.bytes_sent) / (1024 * 1024) / delta)

        self._last_disk_io = disk_io
        self._last_net_io = net_io

        return {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_mb": mem.used / (1024 * 1024),
            "memory_total_mb": mem.total / (1024 * 1024),
            "disk_read_mb": disk_read_mb,
            "disk_write_mb": disk_write_mb,
            "net_in_mb": net_in_mb,
            "net_out_mb": net_out_mb,
            "timestamp": int(now),
            "hostname": self.hostname,
        }
