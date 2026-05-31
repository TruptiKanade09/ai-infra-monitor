# AI Infrastructure Monitoring Platform

A production-grade observability stack for AI/ML training infrastructure.
Built with Prometheus, Grafana, AlertManager, and Python exporters.

**No GPU required** — GPU metrics are simulated realistically.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Machine                          │
│                                                          │
│  ┌─────────────┐   ┌──────────────┐  ┌───────────────┐  │
│  │ node-exporter│   │ gpu-exporter │  │training-sim   │  │
│  │ :9100        │   │ :8000        │  │ :8001         │  │
│  │ CPU/Mem/Disk │   │ 4x GPU sim   │  │ loss/acc/lr   │  │
│  └──────┬───────┘   └──────┬───────┘  └──────┬────────┘  │
│         │                  │                  │           │
│         └──────────────────┴──────────────────┘           │
│                            │ scrape every 15s             │
│                   ┌────────▼────────┐                     │
│                   │   Prometheus    │ :9090                │
│                   │ (stores metrics)│                      │
│                   └────────┬────────┘                     │
│                            │                              │
│              ┌─────────────┴──────────────┐               │
│              │                            │               │
│     ┌────────▼────────┐        ┌──────────▼──────────┐    │
│     │   AlertManager  │        │      Grafana         │   │
│     │    :9093        │        │      :3000           │   │
│     │ email/webhook   │        │   dashboards         │   │
│     └─────────────────┘        └─────────────────────┘    │
└─────────────────────────────────────────────────────────-─┘
```

---

## Quick Start

### Prerequisites

```bash
# Minimum requirements
Docker >= 20.x
Docker Compose >= 2.x
4GB RAM, 2 CPU cores
```

### 1. Clone / navigate to project

```bash
cd ai-infra-monitor
```

### 2. Start the stack

```bash
docker compose up -d
```

First run builds the Python containers (~2 minutes).

### 3. Open Grafana

```
URL:      http://localhost:3000
Username: admin
Password: admin123
```

The **AI Infrastructure — Cluster Overview** dashboard loads automatically.

### 4. Check Prometheus

```
http://localhost:9090
```

Try these queries in Prometheus UI:
```promql
# GPU utilization across all GPUs
gpu_utilization_percent

# Training loss over time
training_loss

# CPU usage
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

### 5. AlertManager

```
http://localhost:9093
```

---

## What Gets Monitored

| Category | Metrics |
|----------|---------|
| **CPU** | Usage per core, load average, idle time |
| **Memory** | Total, used, available, swap |
| **Disk** | Usage %, read/write throughput per device |
| **Network** | Bytes RX/TX, packet errors per interface |
| **GPU** | Utilization, memory, temperature, power, fan, SM clock |
| **Training** | Loss (train/val), accuracy, LR schedule, gradient norm, throughput |

---

## Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| NodeDown | `up == 0` for 1m | critical |
| HighCPUUsage | CPU > 90% for 5m | warning |
| HighMemoryUsage | Memory > 85% for 3m | warning |
| CriticalMemoryUsage | Memory > 95% for 1m | critical |
| DiskSpaceLow | Disk < 15% free | warning |
| DiskSpaceCritical | Disk < 5% free | critical |
| GPUHighTemperature | Temp > 85°C for 2m | warning |
| GPUCriticalTemperature | Temp > 95°C for 30s | critical |
| GPUMemoryHigh | GPU mem > 90% for 5m | warning |
| TrainingJobPossiblyFailed | GPU was >70%, now <10% for 3m | critical |
| TrainingJobStuck | No training steps for 5m | critical |

---

## Multi-Node Cluster

To simulate a real cluster with multiple machines:

```bash
# Requires Multipass (free): https://multipass.run
chmod +x scripts/setup_multinode.sh
./scripts/setup_multinode.sh
```

This creates 3 Ubuntu VMs and configures node-exporter on each.
Then uncomment the `worker-nodes` section in `prometheus/prometheus.yml`.

---

## Connecting a Real GPU

If you have an NVIDIA GPU:

```bash
pip install pynvml
```

Then in `exporters/gpu_exporter.py`:
1. Uncomment the `pynvml` import block
2. Uncomment the `read_real_gpu_metrics` function body
3. Set `SIMULATION_MODE=false` in `docker-compose.yml`

---

## Project Structure

```
ai-infra-monitor/
├── docker-compose.yml              # Orchestrates all services
├── prometheus/
│   ├── prometheus.yml              # Scrape config + alert rule loading
│   └── alert_rules.yml             # All alert definitions
├── alertmanager/
│   └── alertmanager.yml            # Routing + receiver config
├── grafana/
│   └── provisioning/
│       ├── datasources/            # Auto-wires Prometheus
│       └── dashboards/             # Auto-loads dashboard JSON
├── exporters/
│   ├── gpu_exporter.py             # Simulated GPU metrics (4 GPUs)
│   ├── training_simulator.py       # Training job metrics + CPU load
│   ├── Dockerfile.gpu
│   └── Dockerfile.training
└── scripts/
    └── setup_multinode.sh          # Multipass cluster setup
```

---

## Resume Bullet Points

> **AI Infrastructure Monitoring Platform**
>
> - Designed and deployed a distributed observability platform using Prometheus, Grafana, and AlertManager across a simulated multi-node AI training cluster.
> - Built custom Python exporters that expose GPU utilization, memory, temperature, power draw, and training job metrics (loss, accuracy, gradient norms) in Prometheus format.
> - Implemented 11 alert rules covering node failures, resource exhaustion, thermal emergencies, and training job anomaly detection (utilization drop patterns).
> - Simulated realistic ML training workloads using NumPy matrix multiplication to demonstrate CPU/memory pressure and observability under load.
> - Provisioned Grafana dashboards-as-code with 20+ panels covering the full infrastructure and ML training lifecycle.

---

## Useful Commands

```bash
# View all running containers
docker compose ps

# Stream logs from all services
docker compose logs -f

# Check metrics Prometheus is scraping
curl http://localhost:9090/api/v1/targets | python3 -m json.tool

# Manually trigger reload of Prometheus config
curl -X POST http://localhost:9090/-/reload

# Stop everything (data persists in volumes)
docker compose down

# Wipe all data and start fresh
docker compose down -v
```
