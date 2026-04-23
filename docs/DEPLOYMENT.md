# 🚀 VKS Legal AI — Deployment Guide

> Hướng dẫn triển khai hệ thống VKS Legal AI trên các môi trường khác nhau.

---

## Mục Lục

- [Yêu Cầu Hệ Thống](#-yêu-cầu-hệ-thống)
- [Deploy trên Vast.ai (GPU Cloud)](#1-deploy-trên-vastai-gpu-cloud)
- [Deploy bằng Docker Compose](#2-deploy-bằng-docker-compose)
- [Deploy thủ công trên VPS](#3-deploy-thủ-công-trên-vps)
- [Cấu hình Reverse Proxy (Nginx)](#4-cấu-hình-reverse-proxy-nginx)
- [SSL/HTTPS với Let's Encrypt](#5-sslhttps-với-lets-encrypt)
- [Cloudflare Tunnel (Quick Public Access)](#6-cloudflare-tunnel)
- [Production Checklist](#-production-checklist)
- [Monitoring & Logging](#-monitoring--logging)
- [Troubleshooting](#-troubleshooting)

---

## 📋 Yêu Cầu Hệ Thống

### Phần cứng tối thiểu

| Thành phần | Tối thiểu | Khuyến nghị |
|---|---|---|
| **GPU** | RTX 3090 (24GB VRAM) | RTX 4090/5090 (24-32GB VRAM) |
| **RAM** | 32GB | 64GB |
| **Storage** | 50GB SSD | 100GB NVMe SSD |
| **CPU** | 8 cores | 16+ cores |

### Phần mềm

| Software | Version |
|---|---|
| **OS** | Ubuntu 22.04 LTS+ |
| **Python** | 3.11+ |
| **Docker** | 24.0+ |
| **Docker Compose** | v2.0+ |
| **Ollama** | Latest |
| **MongoDB** | 7.0 |
| **NVIDIA Driver** | 535+ |
| **CUDA** | 12.0+ |

---

## 1. Deploy trên Vast.ai (GPU Cloud)

> Phương pháp nhanh nhất để có hệ thống chạy với GPU mạnh.

### Bước 1: Thuê máy trên Vast.ai

1. Đăng ký tài khoản tại [vast.ai](https://vast.ai)
2. Tìm instance với:
   - **GPU**: RTX 4090 hoặc RTX 5090
   - **VRAM**: ≥ 24GB
   - **RAM**: ≥ 32GB
   - **Storage**: ≥ 50GB
   - **Image**: `pytorch/pytorch:latest` hoặc bất kỳ Ubuntu image
3. Launch instance và SSH vào

### Bước 2: Setup tự động

```bash
# Clone repo
git clone https://github.com/phamkhoa18/Qwen_model_local.git /root/vks-legal-ai
cd /root/vks-legal-ai

# Chạy script setup (cài tất cả: MongoDB, Ollama, Python, Qwen3)
chmod +x setup_cloud.sh
./setup_cloud.sh
```

Script sẽ tự động:
- ✅ Cài đặt system packages
- ✅ Cài đặt MongoDB 7.0
- ✅ Cài đặt Ollama + pull model Qwen3-30B-A3B
- ✅ Tạo Python venv + cài dependencies
- ✅ Tạo script `start.sh` để khởi động nhanh

### Bước 3: Nạp dữ liệu pháp luật (GPU-accelerated)

```bash
cd /root/vks-legal-ai
source venv/bin/activate

# Nạp toàn bộ 178K+ văn bản (15-30 phút tùy GPU)
python build_index.py
```

### Bước 4: Khởi động

```bash
./start.sh
```

### Bước 5: Mở Public Link

```bash
# Cài Cloudflare Tunnel
curl -fsSL https://pkg.cloudflare.com/cloudflared-linux-amd64.deb -o cloudflared.deb
dpkg -i cloudflared.deb

# Mở tunnel
nohup cloudflared tunnel --url http://localhost:8000 > /var/log/cloudflared.log 2>&1 &

# Lấy public URL
sleep 3
grep -o 'https://.*\.trycloudflare.com' /var/log/cloudflared.log
```

---

## 2. Deploy bằng Docker Compose

### Cấu trúc services

```
┌─────────────────────────────────────────┐
│              Docker Compose              │
├──────────┬──────────┬───────────────────┤
│ MongoDB  │ VKS API  │ Cloudflare Tunnel │
│ :27017   │ :8000    │ (auto-public URL) │
└──────────┴──────────┴───────────────────┘
```

### Khởi động

```bash
# Clone repo
git clone https://github.com/phamkhoa18/Qwen_model_local.git
cd Qwen_model_local

# Cấu hình (QUAN TRỌNG — đổi mật khẩu!)
cp .env.example .env
nano .env

# Build và khởi động
docker compose up -d

# Xem logs
docker compose logs -f vks-api
```

### docker-compose.yml giải thích

```yaml
version: '3.8'

services:
  # MongoDB — Lưu trữ API keys, usage logs, conversations
  mongodb:
    image: mongo:7.0
    container_name: vks-mongodb
    restart: always
    volumes:
      - mongodb_data:/data/db       # Persistent data
    ports:
      - "27017:27017"

  # VKS API — FastAPI backend + RAG
  vks-api:
    build: .                          # Build từ Dockerfile
    container_name: vks-api
    restart: always
    network_mode: "host"             # Dùng host network để kết nối Ollama
    environment:
      - SECRET_KEY=THAY-DOI-KEY-NAY  # ⚠️ BẮT BUỘC đổi!
      - ADMIN_PASSWORD=THAY-DOI      # ⚠️ BẮT BUỘC đổi!
      - OLLAMA_BASE_URL=http://localhost:11434
      - AUTO_INDEX=false             # Tắt auto-index, chạy build_index.py riêng
    volumes:
      - ./data:/app/data             # Mount vector store data
      - ~/.cache/huggingface:/root/.cache/huggingface  # Cache model

  # Cloudflare Tunnel — Public access không cần domain
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: vks-tunnel
    restart: always
    network_mode: "host"
    command: tunnel --no-autoupdate --url http://localhost:8000

volumes:
  mongodb_data:                      # Named volume cho MongoDB
```

### Hybrid Mode (Khuyến nghị cho GPU cloud)

Trên các cloud GPU (Vast.ai, RunPod), Docker thường không truy cập được GPU. Dùng Hybrid mode:

```bash
# MongoDB: Docker
docker compose up -d mongodb

# API: Native (để dùng GPU)
source venv/bin/activate
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Hoặc chạy nền:
nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &>/var/log/vks-api.log &
```

---

## 3. Deploy thủ công trên VPS

### Ubuntu 22.04

```bash
# === 1. System ===
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip git curl

# === 2. MongoDB ===
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update && sudo apt install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod

# === 3. Ollama ===
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:30b-a3b

# === 4. Project ===
git clone https://github.com/phamkhoa18/Qwen_model_local.git /opt/vks-legal-ai
cd /opt/vks-legal-ai
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# === 5. Configure ===
cp .env.example .env
nano .env  # Đổi SECRET_KEY và ADMIN_PASSWORD

# === 6. Index data ===
python build_index.py

# === 7. Run ===
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Systemd Service (Auto-start on boot)

```bash
sudo tee /etc/systemd/system/vks-api.service << 'EOF'
[Unit]
Description=VKS Legal AI Platform
After=network.target mongod.service ollama.service
Wants=mongod.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/vks-legal-ai
Environment="PATH=/opt/vks-legal-ai/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/opt/vks-legal-ai/venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vks-api
sudo systemctl start vks-api

# Kiểm tra trạng thái
sudo systemctl status vks-api
```

---

## 4. Cấu hình Reverse Proxy (Nginx)

```bash
sudo apt install -y nginx
```

### `/etc/nginx/sites-available/vks-legal-ai`

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE / Streaming support (QUAN TRỌNG)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Giới hạn upload size
    client_max_body_size 10M;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/vks-legal-ai /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

> ⚠️ **QUAN TRỌNG:** Phải tắt `proxy_buffering` để streaming (SSE) hoạt động đúng!

---

## 5. SSL/HTTPS với Let's Encrypt

```bash
# Cài Certbot
sudo apt install -y certbot python3-certbot-nginx

# Cấp SSL tự động
sudo certbot --nginx -d your-domain.com --non-interactive --agree-tos -m your@email.com

# Tự động renew
sudo certbot renew --dry-run
```

Sau khi cấp SSL, API sẽ truy cập qua:
```
https://your-domain.com/v1/chat/completions
```

---

## 6. Cloudflare Tunnel

Cách nhanh nhất để có public URL mà **không cần domain hay cấu hình DNS**.

```bash
# Cài đặt
curl -fsSL https://pkg.cloudflare.com/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Chạy tunnel (public URL tạm thời, thay đổi mỗi lần restart)
cloudflared tunnel --url http://localhost:8000

# Hoặc chạy nền
nohup cloudflared tunnel --url http://localhost:8000 > /var/log/cloudflared.log 2>&1 &

# Lấy URL
grep -o 'https://.*\.trycloudflare.com' /var/log/cloudflared.log
```

Output ví dụ:
```
https://random-words-here.trycloudflare.com
```

> 💡 **Mẹo:** Dùng Cloudflare tunnel với Docker:
> ```yaml
> cloudflared:
>   image: cloudflare/cloudflared:latest
>   network_mode: "host"
>   command: tunnel --no-autoupdate --url http://localhost:8000
> ```

---

## ✅ Production Checklist

### Bảo mật

- [ ] Đổi `SECRET_KEY` thành chuỗi ngẫu nhiên mạnh (≥ 32 ký tự)
- [ ] Đổi `ADMIN_PASSWORD` (không dùng mặc định `vks@2024`)
- [ ] Set `DEBUG=false` trong `.env`
- [ ] Cấu hình CORS origins cụ thể (không dùng `*` trong production)
- [ ] Bật HTTPS (SSL/TLS)
- [ ] Giới hạn truy cập MongoDB (bind IP, authentication)
- [ ] Đặt rate limit phù hợp cho từng API key

### Performance

- [ ] Chạy `build_index.py` bằng GPU native (không qua Docker)
- [ ] Set `AUTO_INDEX=false` sau khi đã index xong
- [ ] Set `HF_HUB_OFFLINE=1` để tránh tải model lại
- [ ] Dùng NVMe SSD cho vector store
- [ ] Cấu hình Nginx `proxy_buffering off` cho SSE

### Monitoring

- [ ] Cấu hình log rotation (`logrotate`)
- [ ] Giám sát endpoint `/admin/health`
- [ ] Theo dõi disk usage (vector store + MongoDB)
- [ ] Setup alerting cho `status: "degraded"`

### Backup

- [ ] Backup MongoDB định kỳ (`mongodump`)
- [ ] Backup thư mục `data/vector_store/`
- [ ] Backup file `.env`

---

## 📊 Monitoring & Logging

### Health Check Endpoint

```bash
# Kiểm tra nhanh
curl -s http://localhost:8000/admin/health | python3 -m json.tool

# Kiểm tra tự động (cron job mỗi 5 phút)
*/5 * * * * curl -sf http://localhost:8000/admin/health > /dev/null || echo "VKS AI DOWN" | mail -s "Alert" admin@your-domain.com
```

### Log Files

| Log | Đường dẫn | Nội dung |
|-----|-----------|----------|
| API Server | `/var/log/vks-api.log` | FastAPI server logs |
| MongoDB | `/var/log/mongod.log` | Database logs |
| Ollama | `/var/log/ollama.log` | LLM engine logs |
| Cloudflare | `/var/log/cloudflared.log` | Tunnel logs |

### Log Rotation

```bash
sudo tee /etc/logrotate.d/vks-legal-ai << 'EOF'
/var/log/vks-api.log
/var/log/ollama.log
/var/log/cloudflared.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
```

---

## 🔧 Troubleshooting

### Ollama không kết nối được

```bash
# Kiểm tra Ollama đang chạy
curl http://localhost:11434/api/tags

# Nếu lỗi, restart Ollama
OLLAMA_HOST=0.0.0.0 ollama serve &

# Kiểm tra model đã pull chưa
ollama list
```

### MongoDB không kết nối

```bash
# Kiểm tra MongoDB status
sudo systemctl status mongod

# Nếu lỗi, restart
sudo systemctl restart mongod

# Kiểm tra port
netstat -tlnp | grep 27017
```

### Vector store không load được

```bash
# Kiểm tra file tồn tại
ls -la data/vector_store/

# Nếu thiếu, chạy lại index
source venv/bin/activate
python build_index.py
```

### GPU không được sử dụng

```bash
# Kiểm tra NVIDIA driver
nvidia-smi

# Kiểm tra PyTorch nhận GPU
python -c "import torch; print(torch.cuda.is_available())"

# Nếu dùng Docker, cần nvidia-container-toolkit:
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Rate limit bị chặn

```bash
# Kiểm tra rate limit hiện tại của key
curl http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer <admin_jwt>"

# Tạo key mới với limit cao hơn
curl -X POST http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer <admin_jwt>" \
  -d '{"name": "High Limit", "rate_limit": 120}'
```

### Streaming không hoạt động qua Nginx

Kiểm tra config Nginx đã có:
```nginx
proxy_buffering off;
proxy_cache off;
```

---

<p align="center">
  <em>VKS Legal AI Platform · Deployment Guide v2.0.0</em>
</p>
