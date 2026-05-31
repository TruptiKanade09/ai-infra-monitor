"""
GPU Metrics Exporter
====================
Simulates NVIDIA DCGM-style GPU metrics for Prometheus.
In production, replace the simulate_* functions with:
    import pynvml; pynvml.nvmlInit()

Exposes: http://localhost:8000/metrics
"""

import os
import time
import math
import random
import threading
from prometheus_client import start_http_server, Gauge, Info, REGISTRY, PROCESS_COLLECTOR, PLATFORM_COLLECTOR

# ── Remove default Python metrics (keep output clean) ────────────────────────
REGISTRY.unregister(PROCESS_COLLECTOR)
REGISTRY.unregister(PLATFORM_COLLECTOR)

# ── Configuration ─────────────────────────────────────────────────────────────
GPU_COUNT = int(os.environ.get("GPU_COUNT", 4))
SIMULATION_MODE = os.environ.get("SIMULATION_MODE", "true").lower() == "true"
UPDATE_INTERVAL = 5  # seconds

# ── Prometheus Metrics ────────────────────────────────────────────────────────
gpu_utilization = Gauge(
    'gpu_utilization_percent',
    'GPU compute utilization (%)',
    ['gpu_id', 'gpu_name']
)

gpu_memory_used = Gauge(
    'gpu_memory_used_bytes',
    'GPU memory used in bytes',
    ['gpu_id', 'gpu_name']
)

gpu_memory_total = Gauge(
    'gpu_memory_total_bytes',
    'GPU total memory in bytes',
    ['gpu_id', 'gpu_name']
)

gpu_memory_used_percent = Gauge(
    'gpu_memory_used_percent',
    'GPU memory utilization (%)',
    ['gpu_id', 'gpu_name']
)

gpu_temperature = Gauge(
    'gpu_temperature_celsius',
    'GPU temperature in Celsius',
    ['gpu_id', 'gpu_name']
)

gpu_power_draw = Gauge(
    'gpu_power_draw_watts',
    'GPU power draw in Watts',
    ['gpu_id', 'gpu_name']
)

gpu_power_limit = Gauge(
    'gpu_power_limit_watts',
    'GPU power limit in Watts',
    ['gpu_id', 'gpu_name']
)

gpu_fan_speed = Gauge(
    'gpu_fan_speed_percent',
    'GPU fan speed (%)',
    ['gpu_id', 'gpu_name']
)

gpu_sm_clock = Gauge(
    'gpu_sm_clock_mhz',
    'GPU SM clock frequency in MHz',
    ['gpu_id', 'gpu_name']
)

gpu_info = Info(
    'gpu_device',
    'GPU device information',
    ['gpu_id']
)


# ── GPU State Machine (realistic behavior simulation) ────────────────────────

class GPUSimulator:
    """Simulates realistic GPU behavior for a training workload."""

    GPU_MODELS = [
        {"name": "NVIDIA A100-SXM4-40GB", "mem_total": 40 * 1024**3, "tdp": 400, "max_clock": 1410},
        {"name": "NVIDIA V100-SXM2-16GB", "mem_total": 16 * 1024**3, "tdp": 300, "max_clock": 1530},
        {"name": "NVIDIA RTX 3090",        "mem_total": 24 * 1024**3, "tdp": 350, "max_clock": 1695},
        {"name": "NVIDIA T4",              "mem_total": 16 * 1024**3, "tdp": 70,  "max_clock": 1590},
    ]

    def __init__(self, gpu_id: int):
        self.gpu_id = gpu_id
        self.model = self.GPU_MODELS[gpu_id % len(self.GPU_MODELS)]
        self.name = self.model["name"]
        self.mem_total = self.model["mem_total"]
        self.tdp = self.model["tdp"]
        self.max_clock = self.model["max_clock"]

        # Internal state
        self._phase = "idle"     # idle | warmup | training | checkpointing
        self._phase_timer = 0
        self._base_util = 0.0
        self._mem_used_ratio = 0.1
        self._temp = 35.0
        self._noise = 0.0

        # Phase config per GPU (staggered starts look realistic)
        self._tick = gpu_id * 30   # offset phases per GPU

    def _next_phase(self):
        """Transition between realistic training phases."""
        phases = {
            "idle":          ("warmup",       random.randint(10, 20)),
            "warmup":        ("training",     random.randint(60, 180)),
            "training":      ("checkpointing", random.randint(5, 15)),
            "checkpointing": ("training",     random.randint(60, 180)),
        }
        next_phase, duration = phases.get(self._phase, ("idle", 30))
        self._phase = next_phase
        self._phase_timer = duration

    def tick(self):
        """Advance simulation by one step."""
        self._tick += 1
        self._phase_timer -= 1
        if self._phase_timer <= 0:
            self._next_phase()

        # Target utilization per phase
        targets = {
            "idle":          (2,  5),
            "warmup":        (30, 60),
            "training":      (85, 98),
            "checkpointing": (10, 25),
        }
        lo, hi = targets[self._phase]
        target_util = random.uniform(lo, hi)

        # Smooth toward target (exponential moving average)
        self._base_util = self._base_util * 0.7 + target_util * 0.3
        util = min(100, max(0, self._base_util + random.gauss(0, 1.5)))

        # Memory usage (proportional to utilization during training)
        if self._phase == "training":
            self._mem_used_ratio = min(0.92, self._mem_used_ratio * 0.95 + 0.85 * 0.05)
        elif self._phase == "idle":
            self._mem_used_ratio = max(0.05, self._mem_used_ratio * 0.99)
        else:
            self._mem_used_ratio = 0.3 + random.uniform(-0.05, 0.05)

        # Temperature (lags behind utilization)
        target_temp = 35 + (util / 100) * 55  # 35°C idle → 90°C full load
        self._temp = self._temp * 0.92 + target_temp * 0.08
        temp = self._temp + random.gauss(0, 0.5)

        # Power draw
        power = (util / 100) * self.tdp * random.uniform(0.95, 1.05)

        # Clock speed
        clock = int((util / 100) * self.max_clock * random.uniform(0.97, 1.0))

        # Fan speed (reacts to temperature)
        fan = min(100, max(20, (temp - 40) * 2.5))

        return {
            "utilization":     round(util, 2),
            "mem_used":        int(self._mem_used_ratio * self.mem_total),
            "mem_total":       self.mem_total,
            "mem_used_pct":    round(self._mem_used_ratio * 100, 2),
            "temperature":     round(temp, 1),
            "power_draw":      round(power, 1),
            "power_limit":     self.tdp,
            "fan_speed":       round(fan, 1),
            "sm_clock":        clock,
        }


# ── Real GPU (pynvml) ─────────────────────────────────────────────────────────

def read_real_gpu_metrics(gpu_id: int):
    """
    Reads real GPU metrics via pynvml (NVIDIA Management Library).
    Uncomment and install: pip install pynvml
    """
    # import pynvml
    # handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
    # name = pynvml.nvmlDeviceGetName(handle).decode()
    # util = pynvml.nvmlDeviceGetUtilizationRates(handle)
    # mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    # temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
    # power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000  # mW → W
    # return {
    #     "utilization":   util.gpu,
    #     "mem_used":      mem_info.used,
    #     "mem_total":     mem_info.total,
    #     "mem_used_pct":  (mem_info.used / mem_info.total) * 100,
    #     "temperature":   temp,
    #     "power_draw":    power,
    # }
    raise NotImplementedError("pynvml not configured")


# ── Main collection loop ──────────────────────────────────────────────────────

simulators = [GPUSimulator(i) for i in range(GPU_COUNT)]

def collect_metrics():
    """Collect and publish GPU metrics to Prometheus."""
    while True:
        for gpu_id, sim in enumerate(simulators):
            if SIMULATION_MODE:
                m = sim.tick()
            else:
                try:
                    m = read_real_gpu_metrics(gpu_id)
                except Exception as e:
                    print(f"[ERROR] GPU {gpu_id}: {e}. Falling back to simulation.")
                    m = sim.tick()

            labels = [str(gpu_id), sim.name]

            gpu_utilization.labels(*labels).set(m["utilization"])
            gpu_memory_used.labels(*labels).set(m["mem_used"])
            gpu_memory_total.labels(*labels).set(m["mem_total"])
            gpu_memory_used_percent.labels(*labels).set(m["mem_used_pct"])
            gpu_temperature.labels(*labels).set(m["temperature"])
            gpu_power_draw.labels(*labels).set(m["power_draw"])
            gpu_power_limit.labels(*labels).set(m["power_limit"])
            gpu_fan_speed.labels(*labels).set(m["fan_speed"])
            gpu_sm_clock.labels(*labels).set(m["sm_clock"])

            gpu_info.labels(str(gpu_id)).info({
                "name":       sim.name,
                "uuid":       f"GPU-{gpu_id:08x}-sim",
                "driver":     "535.86.10",
                "cuda":       "12.2",
                "sim_phase":  sim._phase,
            })

        time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[GPU Exporter] Starting on port {port}")
    print(f"[GPU Exporter] Simulating {GPU_COUNT} GPUs | mode=simulation")
    print(f"[GPU Exporter] Metrics: http://localhost:{port}/metrics")

    start_http_server(port)

    t = threading.Thread(target=collect_metrics, daemon=True)
    t.start()

    # Keep main thread alive
    while True:
        time.sleep(60)
