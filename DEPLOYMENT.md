# 🚀 Crypt Lab IDS — Complete Deployment Guide

## 📍 Deployment Options Overview

| Option | Cost | Difficulty | Best For | Network Access |
|--------|------|-----------|----------|---|
| **Local Machine** | FREE | Easy | Dev/Testing/Homelab | ✅ Yes (local) |
| **Raspberry Pi** | FREE* | Easy | 24/7 Home monitoring | ✅ Yes (LAN) |
| **Old Laptop/PC** | FREE* | Easy | Dedicated monitoring box | ✅ Yes (LAN) |
| **Docker locally** | FREE | Medium | Portable setup | ✅ Yes (local) |
| **Hetzner Cloud** | ~€1/mo | Medium | Small VPS | ✅ Yes (cloud) |
| **DigitalOcean** | $5-6/mo | Medium | Popular cloud option | ✅ Yes (cloud) |
| **AWS/GCP/Azure** | FREE tier* | Medium | Enterprise option | ✅ Yes (limited) |

*One-time hardware cost or limited free tier

---

## Option 1: FREE — Local Machine / Homelab Setup (Recommended for Testing)

### ✅ Best For: 
- Development & testing
- Cyber training labs
- Home network monitoring
- Learning the system

### 📋 Requirements:
- Linux machine (Ubuntu, Debian, CentOS, etc.)
- Python 3.10+
- 4GB+ RAM
- 3GB+ disk space
- Active network interface

### 🎯 Step-by-Step Setup

#### Step 1: Clone the Repository
```bash
git clone https://github.com/X-Rachit-X/crypt-lab.git
cd crypt-lab
```

#### Step 2: Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 4: Configure the System
```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

**Key settings to configure:**

```ini
# Generate a new AES key (required)
python3 -c "import os,binascii; print(binascii.hexlify(os.urandom(32)).decode())"
# Copy output to IDS_AES_KEY in .env

# Find your network interface
ip link show
# Set CAPTURE_INTERFACE to your interface (e.g., eth0, wlan0, enp3s0)

# Optional: Add Gemini API key for AI features
# Get free key at https://aistudio.google.com
GEMINI_API_KEY=sk-...
```

#### Step 5: Start the Server
```bash
# Easy way (recommended)
./run.sh

# Or manually
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### Step 6: Access the Dashboard
Open browser: **http://localhost:8000**

#### Step 7: Verify Installation
```bash
# Check server health
curl http://localhost:8000/api/health

# Test simulator
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"PORT_SCAN"}'
```

### 🔧 Making It 24/7 (Persistent Monitoring)

#### Option A: Using systemd (Linux)
```bash
# Create systemd service file
sudo nano /etc/systemd/system/crypt-lab-ids.service
```

Paste this:
```ini
[Unit]
Description=Crypt Lab IDS
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/crypt-lab
ExecStart=/path/to/crypt-lab/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable & start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable crypt-lab-ids
sudo systemctl start crypt-lab-ids

# Check status
sudo systemctl status crypt-lab-ids

# View logs
sudo journalctl -u crypt-lab-ids -f
```

#### Option B: Using tmux (Simple)
```bash
# Install tmux
sudo apt install tmux

# Start IDS in detachable session
tmux new-session -d -s ids './run.sh'

# Access later
tmux attach -t ids

# Detach with Ctrl+B then D
```

#### Option C: Using nohup (Simplest)
```bash
nohup ./run.sh > ids.log 2>&1 &

# View logs
tail -f ids.log

# Stop
pkill -f "uvicorn main:app"
```

### 🌐 Access from Other Machines on LAN

Once running, other machines can access:
```
http://YOUR_MACHINE_IP:8000
```

Example:
```bash
# Find your machine's IP
hostname -I

# Share the URL with others
# http://192.168.1.100:8000
```

---

## Option 2: FREE — Raspberry Pi / Single-Board Computer (24/7 Monitoring)

### ✅ Best For:
- Continuous network monitoring
- Home network security
- Pi-hole integration
- Low power consumption

### 📋 Requirements:
- Raspberry Pi 4/5 (2GB+ RAM minimum, 4GB recommended)
- microSD card (32GB+ recommended)
- Ethernet connection (or WiFi)
- USB power adapter
- Heat sink (optional but recommended)

### 🎯 Step-by-Step Setup

#### Step 1: Prepare Raspberry Pi
```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.10 python3-venv python3-pip git

# Verify Python version
python3 --version  # Should be 3.10+
```

#### Step 2: Clone & Setup
```bash
# Clone repository
git clone https://github.com/X-Rachit-X/crypt-lab.git
cd crypt-lab

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (this takes ~15-20 minutes on Pi)
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 3: Configure
```bash
cp .env.example .env
nano .env

# Set your network interface (usually eth0 or wlan0)
CAPTURE_INTERFACE=eth0

# Generate AES key
python3 -c "import os,binascii; print(binascii.hexlify(os.urandom(32)).decode())"
```

#### Step 4: Create systemd Service
```bash
sudo nano /etc/systemd/system/crypt-lab.service
```

```ini
[Unit]
Description=Crypt Lab IDS on Raspberry Pi
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/crypt-lab
ExecStart=/home/pi/crypt-lab/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Step 5: Enable & Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable crypt-lab
sudo systemctl start crypt-lab

# Check status
sudo systemctl status crypt-lab
```

#### Step 6: Access Dashboard
```bash
# Find Pi's IP
hostname -I

# Open in browser from any device on same network
# http://PI_IP_ADDRESS:8000
```

#### Step 7: Optional — Access from Internet (Port Forwarding)

⚠️ **Security Warning:** Only do this with proper HTTPS and authentication!

```bash
# In your router settings:
# 1. Enable port forwarding
# 2. Forward external port 8000 → Pi internal IP :8000
# 3. Access via: http://YOUR_PUBLIC_IP:8000
#
# ⚠️ Better approach: Use reverse proxy with HTTPS
```

### 🔧 Optimize for Pi Performance
```bash
# Reduce poll frequency in .env
ANALYSIS_DEBOUNCE_MS=5000  # Increase debounce

# Disable debug logging
DEBUG=false

# Monitor resource usage
watch -n 2 'free -h && df -h'
```

---

## Option 3: FREE — Docker Setup (Portable)

### ✅ Best For:
- Reproducible deployments
- Multiple environments
- Easy scaling
- CI/CD pipelines

### 📋 Requirements:
- Docker & Docker Compose installed
- Linux or Docker Desktop
- 4GB+ RAM available

### 🎯 Step-by-Step

#### Step 1: Create Dockerfile
```bash
cd crypt-lab
cat > Dockerfile << 'EOF'
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpcap-dev \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
```

#### Step 2: Create docker-compose.yml
```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  crypt-lab-ids:
    build: .
    container_name: crypt-lab-ids
    ports:
      - "8000:8000"
    volumes:
      - ./ids_alerts.db:/app/ids_alerts.db
      - ./model:/app/model
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_MODEL=gemini-2.0-flash
      - IDS_AES_KEY=${IDS_AES_KEY}
      - CAPTURE_INTERFACE=eth0
      - DEBUG=false
    network_mode: "host"  # Required for packet capture
    cap_add:
      - NET_ADMIN
      - NET_RAW
    restart: unless-stopped
EOF
```

#### Step 3: Prepare Environment
```bash
# Copy .env
cp .env.example .env

# Edit .env
nano .env

# Ensure these are set:
# GEMINI_API_KEY=...
# IDS_AES_KEY=...
```

#### Step 4: Build & Run
```bash
# Build Docker image
docker-compose build

# Start service
docker-compose up -d

# Check logs
docker-compose logs -f crypt-lab-ids

# Stop service
docker-compose down
```

#### Step 5: Access Dashboard
```bash
# http://localhost:8000
```

---

## Option 4: €1/Month — Hetzner Cloud (Minimal Cloud Deployment)

### ✅ Best For:
- Cheap cloud deployment
- Always-on monitoring
- Static public IP
- Full control

### 🎯 Step-by-Step

#### Step 1: Create Account & Server
1. Go to [hetzner.cloud](https://hetzner.cloud)
2. Sign up (requires credit card, but €1/month is very cheap)
3. Create a new project
4. Click "Create Server"
5. Select:
   - Ubuntu 22.04 (free tier)
   - 2 GB RAM, 20 GB SSD
   - Location: Choose nearest
   - SSH key: Create new or upload yours

#### Step 2: SSH into Server
```bash
ssh root@YOUR_SERVER_IP
```

#### Step 3: Run Setup Script
```bash
# Update system
apt update && apt upgrade -y

# Create user
useradd -m -s /bin/bash ids
su - ids

# Clone and setup (same as Option 1)
git clone https://github.com/X-Rachit-X/crypt-lab.git
cd crypt-lab

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env  # Add your API keys
```

#### Step 4: Setup systemd Service
```bash
# Exit to root
exit

# Create service file
nano /etc/systemd/system/crypt-lab.service
```

```ini
[Unit]
Description=Crypt Lab IDS
After=network.target

[Service]
Type=simple
User=ids
WorkingDirectory=/home/ids/crypt-lab
ExecStart=/home/ids/crypt-lab/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
systemctl daemon-reload
systemctl enable crypt-lab
systemctl start crypt-lab
```

#### Step 5: Setup Firewall
```bash
# Allow SSH, HTTP, HTTPS
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 8000/tcp
ufw enable
```

#### Step 6: Setup HTTPS (Free with Let's Encrypt)
```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Get certificate (requires domain)
certbot certonly --standalone -d your-domain.com

# Use in Nginx reverse proxy (optional)
```

#### Step 7: Access Dashboard
```
http://YOUR_SERVER_IP:8000
```

Or with domain:
```
http://your-domain.com:8000
```

---

## Option 5: $5-6/Month — DigitalOcean (Popular Cloud Option)

### ✅ Best For:
- Reliable uptime
- Minimal cost
- Full root access
- Good documentation

### 🎯 Quick Setup

1. **Create Account** → [digitalocean.com](https://www.digitalocean.com)
2. **Create Droplet**:
   - OS: Ubuntu 22.04
   - Size: Basic ($5-6/mo)
   - Region: Nearest to you
3. **SSH in** → `ssh root@DROPLET_IP`
4. **Run same setup as Hetzner** (Options 1 + Step 4 above)

---

## Option 6: AWS/GCP/Azure Free Tier (Limited)

### ⚠️ Pros:
- Free for 12 months (AWS/Azure)
- Always free (GCP)
- Enterprise grade

### ⚠️ Cons:
- Complex setup
- Limited resources
- Easy to exceed free tier quotas

### AWS Setup (t2.micro free tier)
```bash
# 1. Create EC2 instance (Ubuntu 22.04, t2.micro)
# 2. SSH in: ssh -i your-key.pem ubuntu@INSTANCE_IP
# 3. Run Option 1 setup above
```

---

## Comparison: Which Option Should You Choose?

```
┌─────────────────────────────────────────┬──────────┬────────────┬─────────────┐
│ Use Case                                │ Option   │ Cost       │ Difficulty  │
├─────────────────────────────────────────┼──────────┼────────────┼─────────────┤
│ Testing / Learning                      │ Local    │ FREE       │ Easy        │
│ Cyber training lab                      │ Local    │ FREE       │ Easy        │
│ 24/7 home network monitoring            │ Pi       │ FREE*      │ Easy        │
│ Portable / Docker deployment            │ Docker   │ FREE       │ Medium      │
│ Cheap cloud VPS (always-on)             │ Hetzner  │ €1/mo      │ Medium      │
│ Popular cloud (reliable)                │ DO       │ $5/mo      │ Medium      │
│ Enterprise / Want free trial             │ AWS/GCP  │ FREE tier* │ Hard        │
└─────────────────────────────────────────┴──────────┴────────────┴─────────────┘

*One-time hardware cost or limited free tier
```

### 🏆 RECOMMENDED FOR YOU:
- **First time?** → **Option 1: Local Machine** (FREE, learn the system)
- **Always-on monitoring?** → **Option 2: Raspberry Pi** (FREE hardware cost)
- **Small network?** → **Option 4: Hetzner** (€1/mo = ~$1.10/month)
- **Production-grade?** → **Option 5: DigitalOcean** ($5-6/mo)

---

## ⚠️ Important Deployment Considerations

### Network Interface for Packet Capture
```bash
# The system needs raw socket access to capture packets
# This works on:
# ✅ Local machines (you have sudo)
# ✅ Raspberry Pi (on local LAN)
# ✅ VPS with raw socket support (Hetzner, DO, etc.)
# ✅ Docker with --privileged flag

# NOT supported:
# ❌ Most cloud functions (Lambda, Cloud Functions)
# ❌ Kubernetes without DaemonSet
# ❌ Shared hosting
```

### Firewall Rules (If Behind Firewall)
```bash
# Allow outbound to ipinfo.io (geo-location)
# Allow outbound to Google APIs (Gemini)

# Optional: Restrict access by IP
# Only allow your IP to access port 8000
iptables -A INPUT -p tcp --dport 8000 -s YOUR.IP.HERE -j ACCEPT
```

### Database Permissions
```bash
# Ensure SQLite database is writable
chmod 600 ids_alerts.db
chown YOUR_USER:YOUR_USER ids_alerts.db
```

### Monitoring Service Health
```bash
# Check if service is running
curl http://localhost:8000/api/health

# Example response:
# {
#   "status": "ok",
#   "sensor_ip": "192.168.1.5",
#   "model_classes": 11,
#   "uptime_seconds": 3600
# }
```

---

## 🚨 Troubleshooting Deployment

### Problem: "Interface not found"
```bash
# Solution: Find correct interface
ip link show
# Update CAPTURE_INTERFACE in .env
```

### Problem: "Port 8000 already in use"
```bash
# Solution 1: Find and kill process
lsof -i :8000
kill -9 PID

# Solution 2: Use different port
./run.sh --port 9000
```

### Problem: "Permission denied for raw sockets"
```bash
# Solution: Run with sudo or add capabilities
sudo ./run.sh

# OR for Docker:
docker run --cap-add=NET_ADMIN --cap-add=NET_RAW ...
```

### Problem: "Database read-only error"
```bash
# Solution: Fix permissions
sudo chown $USER:$USER ids_alerts.db
chmod 600 ids_alerts.db
```

### Problem: Dashboard loads but no alerts appear
```bash
# Solution: Check detection loop
# Wait 10-15 seconds
# Run simulator: curl -X POST http://localhost:8000/api/simulate ...
# Check server logs for errors
```

---

## 📊 Resource Requirements by Option

| Resource | Local PC | Pi 4 | Docker | Hetzner | DigitalOcean |
|----------|----------|------|--------|---------|---|
| RAM | 4GB+ | 2GB+ | 4GB+ | 2GB | 2GB |
| CPU | Any | ARM64 | Any | 1 vCPU | 1 vCPU |
| Storage | 3GB | 20GB microSD | 3GB+ | 20GB | 55GB |
| Network | LAN | Ethernet | LAN | Gigabit | Gigabit |
| Uptime | Until reboot | 24/7 | Until reboot | 24/7 | 24/7 |
| Cost | FREE | FREE* | FREE | €1/mo | $5/mo |

---

## 🎯 Quick Start Matrix

```
Choose your scenario:

[Are you testing locally?]
├─ Yes → Option 1: Local Machine (5 min setup)
└─ No → [Need always-on?]
    ├─ Yes → [Have Raspberry Pi?]
    │   ├─ Yes → Option 2: Pi (20 min setup)
    │   └─ No → [Budget?]
    │       ├─ Minimal → Option 4: Hetzner €1/mo (15 min)
    │       └─ Small → Option 5: DigitalOcean $5/mo (15 min)
    └─ No → Option 3: Docker (Portable, 10 min setup)
```

---

## ✅ Deployment Checklist

- [ ] Choose deployment option
- [ ] Download/prepare hardware or cloud account
- [ ] Clone repository
- [ ] Create virtual environment
- [ ] Install dependencies
- [ ] Copy & configure .env file
- [ ] Generate AES key
- [ ] Find network interface
- [ ] Start server
- [ ] Verify health endpoint
- [ ] Access dashboard
- [ ] Test simulator scenario
- [ ] Setup persistence (systemd/tmux/etc)
- [ ] Setup firewall rules
- [ ] Bookmark dashboard URL

---

## 🔗 Useful Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Hetzner**: https://hetzner.cloud (€1/mo)
- **DigitalOcean**: https://www.digitalocean.com ($5/mo)
- **Docker Docs**: https://docs.docker.com/
- **Raspberry Pi Setup**: https://www.raspberrypi.com/documentation/

---

## 🎉 Next Steps

1. **Choose your option** from the table above
2. **Follow the step-by-step guide** for that option
3. **Verify it works** using `/api/health` endpoint
4. **Test with simulator** to see alerts
5. **Configure persistence** for 24/7 operation
6. **Optional**: Add HTTPS, authentication, monitoring

**You're now ready to deploy Crypt Lab IDS!** 🚀

---

*Last updated: August 12, 2026*
