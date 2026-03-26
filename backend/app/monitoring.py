from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from time import time
from typing import DefaultDict


@dataclass
class RequestMetric:
    count: int = 0
    errors: int = 0
    total_duration_ms: float = 0.0


@dataclass
class InMemoryMetrics:
    started_at_epoch: float = field(default_factory=time)
    _routes: DefaultDict[str, RequestMetric] = field(default_factory=lambda: defaultdict(RequestMetric))
    _lock: Lock = field(default_factory=Lock)

    def record(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        key = f"{method.upper()} {path}"
        with self._lock:
            bucket = self._routes[key]
            bucket.count += 1
            bucket.total_duration_ms += duration_ms
            if status_code >= 500:
                bucket.errors += 1

    def snapshot(self) -> dict:
        with self._lock:
            routes = {
                route: {
                    "count": metric.count,
                    "errors": metric.errors,
                    "avg_duration_ms": round(metric.total_duration_ms / metric.count, 2) if metric.count else 0.0,
                    "total_duration_ms": round(metric.total_duration_ms, 2),
                }
                for route, metric in sorted(self._routes.items())
            }
        return {
            "uptime_seconds": round(time() - self.started_at_epoch, 2),
            "started_at_epoch": self.started_at_epoch,
            "routes": routes,
        }

    def render_prometheus(self) -> str:
        lines = [
            "# HELP invest_uptime_seconds Process uptime in seconds",
            "# TYPE invest_uptime_seconds gauge",
            f"invest_uptime_seconds {round(time() - self.started_at_epoch, 2)}",
            "# HELP invest_http_requests_total HTTP requests handled by route",
            "# TYPE invest_http_requests_total counter",
            "# HELP invest_http_request_errors_total HTTP 5xx responses by route",
            "# TYPE invest_http_request_errors_total counter",
            "# HELP invest_http_request_avg_duration_ms Average request duration in milliseconds by route",
            "# TYPE invest_http_request_avg_duration_ms gauge",
        ]
        with self._lock:
            for route, metric in sorted(self._routes.items()):
                method, path = route.split(" ", 1)
                labels = f'method="{method}",path="{path}"'
                avg_duration = round(metric.total_duration_ms / metric.count, 2) if metric.count else 0.0
                lines.append(f"invest_http_requests_total{{{labels}}} {metric.count}")
                lines.append(f"invest_http_request_errors_total{{{labels}}} {metric.errors}")
                lines.append(f"invest_http_request_avg_duration_ms{{{labels}}} {avg_duration}")
        return "\n".join(lines) + "\n"


metrics = InMemoryMetrics()
