#!/bin/bash
# ============================================================
# Multi-Node Cluster Setup using Multipass (completely free)
# Creates 3 VMs: prometheus-server + 2 worker nodes
# ============================================================

set -e

echo "======================================"
echo " AI Cluster Multi-Node Setup"
echo "======================================"

# ── Check Multipass is installed ─────────────────────────────────────────────
if ! command -v multipass &>/dev/null; then
  echo "[ERROR] Multipass not found."
  echo "  Install: https://multipass.run/install"
  echo "  macOS:   brew install multipass"
  echo "  Windows: winget install Canonical.Multipass"
  exit 1
fi

# ── Launch VMs ────────────────────────────────────────────────────────────────
echo "[1/4] Creating VMs..."

multipass launch --name prometheus-server --cpus 2 --memory 2G --disk 10G 22.04 || echo "VM may already exist"
multipass launch --name worker-node-1     --cpus 1 --memory 1G --disk 5G  22.04 || echo "VM may already exist"
multipass launch --name worker-node-2     --cpus 1 --memory 1G --disk 5G  22.04 || echo "VM may already exist"

echo "[2/4] Installing Docker on all nodes..."

for VM in prometheus-server worker-node-1 worker-node-2; do
  echo "  → $VM"
  multipass exec $VM -- bash -c "
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker ubuntu
    sudo systemctl enable docker
  "
done

echo "[3/4] Starting node-exporter on worker nodes..."

NODE_EXPORTER_CMD="docker run -d \
  --name node-exporter \
  --restart unless-stopped \
  --net=host \
  -v /proc:/host/proc:ro \
  -v /sys:/host/sys:ro \
  -v /:/rootfs:ro \
  prom/node-exporter:latest \
  --path.procfs=/host/proc \
  --path.rootfs=/rootfs \
  --path.sysfs=/host/sys"

multipass exec worker-node-1 -- bash -c "$NODE_EXPORTER_CMD"
multipass exec worker-node-2 -- bash -c "$NODE_EXPORTER_CMD"

echo "[4/4] Getting IP addresses..."

IP_SERVER=$(multipass info prometheus-server | grep IPv4 | awk '{print $2}')
IP_NODE1=$(multipass info worker-node-1     | grep IPv4 | awk '{print $2}')
IP_NODE2=$(multipass info worker-node-2     | grep IPv4 | awk '{print $2}')

echo ""
echo "======================================"
echo " ✅ Cluster Ready!"
echo "======================================"
echo ""
echo "  prometheus-server : $IP_SERVER"
echo "  worker-node-1     : $IP_NODE1"
echo "  worker-node-2     : $IP_NODE2"
echo ""
echo "Next: Add these to prometheus/prometheus.yml under worker-nodes:"
echo ""
echo "  - job_name: 'worker-nodes'"
echo "    static_configs:"
echo "      - targets:"
echo "          - '${IP_NODE1}:9100'   # worker-node-1"
echo "          - '${IP_NODE2}:9100'   # worker-node-2"
echo ""
echo "Then copy this project to prometheus-server and run:"
echo "  multipass transfer . prometheus-server:"
echo "  multipass exec prometheus-server -- docker compose up -d"
echo ""
