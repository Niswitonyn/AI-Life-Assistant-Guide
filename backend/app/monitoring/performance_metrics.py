from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


def _now() -> float:
    return time.time()


@dataclass
class _RollingMetric:
    count: int = 0
    last_ms: Optional[float] = None
    avg_ms: Optional[float] = None

    def observe(self, ms: float) -> None:
        self.count += 1
        self.last_ms = ms
        if self.avg_ms is None:
            self.avg_ms = ms
            return
        # Simple EMA-like smoothing (stable + lightweight).
        alpha = 0.12
        self.avg_ms = (alpha * ms) + ((1 - alpha) * self.avg_ms)


class PerformanceMetrics:
    """
    Lightweight metrics aggregator.

    - System metrics: process CPU% (best-effort), RSS memory (best-effort)
    - Task durations: per action
    - API latencies: per path prefix
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = _now()
        self._last_system_update = 0.0
        self._cpu_percent: Optional[float] = None
        self._rss_mb: Optional[float] = None
        self._threads: Optional[int] = None

        self._task: Dict[str, _RollingMetric] = {}
        self._api: Dict[str, _RollingMetric] = {}

        # CPU sampling state (process time vs wall time)
        self._last_wall = None
        self._last_proc_s = None

    def observe_task(self, action: str, duration_s: float) -> None:
        key = (action or "").strip() or "task"
        ms = max(0.0, float(duration_s) * 1000.0)
        with self._lock:
            self._task.setdefault(key, _RollingMetric()).observe(ms)

    def observe_api(self, path: str, duration_s: float) -> None:
        key = self._bucket_path(path)
        ms = max(0.0, float(duration_s) * 1000.0)
        with self._lock:
            self._api.setdefault(key, _RollingMetric()).observe(ms)

    def update_system_metrics(self) -> None:
        """
        Refresh process CPU + memory stats (best-effort).
        Safe to call frequently.
        """
        cpu = None
        rss = None
        threads = None
        try:
            cpu = self._sample_cpu_percent()
        except Exception:
            cpu = None
        try:
            rss = self._get_rss_mb()
        except Exception:
            rss = None
        try:
            threads = self._get_thread_count()
        except Exception:
            threads = None

        with self._lock:
            self._last_system_update = _now()
            self._cpu_percent = cpu
            self._rss_mb = rss
            self._threads = threads

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            task = {k: {"count": v.count, "last_ms": v.last_ms, "avg_ms": v.avg_ms} for k, v in list(self._task.items())[:50]}
            api = {k: {"count": v.count, "last_ms": v.last_ms, "avg_ms": v.avg_ms} for k, v in list(self._api.items())[:50]}
            return {
                "uptime_s": max(0, int(_now() - self._started_at)),
                "process": {
                    "pid": os.getpid(),
                    "cpu_percent": self._cpu_percent,
                    "rss_mb": self._rss_mb,
                    "threads": self._threads,
                    "updated_at": self._last_system_update or None,
                },
                "tasks": task,
                "api": api,
            }

    def is_high_load(self, *, cpu_threshold: float = 85.0, rss_mb_threshold: float = 1500.0) -> bool:
        with self._lock:
            cpu = self._cpu_percent
            rss = self._rss_mb
        if cpu is not None and cpu >= cpu_threshold:
            return True
        if rss is not None and rss >= rss_mb_threshold:
            return True
        return False

    def _bucket_path(self, path: str) -> str:
        p = (path or "").strip() or "/"
        if p.startswith("/api/"):
            parts = p.split("/")
            # /api/<group>/... -> /api/<group>
            if len(parts) >= 3 and parts[2]:
                return f"/api/{parts[2]}"
            return "/api"
        if p.startswith("/memory"):
            return "/memory"
        if p.startswith("/documents") or p.startswith("/system") or p.startswith("/voice"):
            return p.split("?")[0]
        return "/"

    def _get_thread_count(self) -> Optional[int]:
        try:
            import threading as _t

            return _t.active_count()
        except Exception:
            return None

    def _get_rss_mb(self) -> Optional[float]:
        if os.name != "nt":
            return None
        # Windows: GetProcessMemoryInfo
        import ctypes
        from ctypes import wintypes

        psapi = ctypes.WinDLL("psapi")
        kernel32 = ctypes.WinDLL("kernel32")

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        GetCurrentProcess = kernel32.GetCurrentProcess
        GetCurrentProcess.restype = wintypes.HANDLE

        GetProcessMemoryInfo = psapi.GetProcessMemoryInfo
        GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        GetProcessMemoryInfo.restype = wintypes.BOOL

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = GetCurrentProcess()
        ok = GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        return float(counters.WorkingSetSize) / (1024.0 * 1024.0)

    def _sample_cpu_percent(self) -> Optional[float]:
        if os.name != "nt":
            return None
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32")

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        def _filetime_to_seconds(ft: FILETIME) -> float:
            # 100-ns intervals
            t = (int(ft.dwHighDateTime) << 32) + int(ft.dwLowDateTime)
            return float(t) / 10_000_000.0

        GetCurrentProcess = kernel32.GetCurrentProcess
        GetCurrentProcess.restype = wintypes.HANDLE

        GetProcessTimes = kernel32.GetProcessTimes
        GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        GetProcessTimes.restype = wintypes.BOOL

        creation = FILETIME()
        exit_time = FILETIME()
        kernel_time = FILETIME()
        user_time = FILETIME()

        handle = GetCurrentProcess()
        ok = GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel_time), ctypes.byref(user_time))
        if not ok:
            return None

        proc_s = _filetime_to_seconds(kernel_time) + _filetime_to_seconds(user_time)
        wall = time.perf_counter()

        if self._last_wall is None or self._last_proc_s is None:
            self._last_wall = wall
            self._last_proc_s = proc_s
            return None

        d_wall = wall - self._last_wall
        d_proc = proc_s - self._last_proc_s
        self._last_wall = wall
        self._last_proc_s = proc_s

        if d_wall <= 0:
            return None

        cores = os.cpu_count() or 1
        pct = (d_proc / (d_wall * cores)) * 100.0
        if pct < 0:
            pct = 0.0
        return min(100.0, pct)


performance_metrics = PerformanceMetrics()

