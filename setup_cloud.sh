#!/bin/bash
# ============================================================
# VKS Legal AI - Vast.ai / Cloud GPU Setup Script
# GPU: RTX 4090/5090 (24-32GB VRAM)
# ============================================================

set -e

echo ""
echo "============================================"
echo "  VKS Legal AI - Auto Setup"
echo "  Chatbot Phap Luat + RAG + Qwen3"
echo "============================================"
echo ""

# 1. System packages
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq curl wget git python3 python3-pip python3-venv python-is-python3 > /dev/null 2>&1
echo "[OK] System packages installed"

# 2. MongoDB
echo "[2/7] Installing MongoDB..."
if command -v mongod &> /dev/null; then
    echo "[OK] MongoDB already installed"
else
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | apt-key add - > /dev/null 2>&1
    echo "deb [ arch=amd64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq mongodb-org > /dev/null 2>&1
    echo "[OK] MongoDB installed"
fi
mkdir -p /data/db
mongod --fork --logpath /var/log/mongod.log --dbpath /data/db 2>/dev/null || true
echo "[OK] MongoDB started"

# 3. Ollama
echo "[3/7] Installing Ollama..."
if command -v ollama &> /dev/null; then
    echo "[OK] Ollama already installed"
else
    curl -fsSL https://ollama.com/install.sh | sh
    echo "[OK] Ollama installed"
fi

# Start Ollama
OLLAMA_HOST=0.0.0.0 ollama serve &>/var/log/ollama.log &
sleep 5
echo "[OK] Ollama started"

# 4. Pull Qwen3 model
echo "[4/7] Pulling Qwen3-30B-A3B model..."
echo "      (This may take 10-20 minutes depending on network speed)"
ollama pull qwen3:30b-a3b
echo "[OK] Model downloaded"

# 5. Clone project (if not already)
echo "[5/7] Setting up project..."
PROJECT_DIR="/root/vks-legal-ai"
if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    git pull origin main 2>/dev/null || true
else
    git clone https://github.com/phamkhoa18/Qwen_model_local.git "$PROJECT_DIR" 2>/dev/null || true
    if [ ! -d "$PROJECT_DIR" ]; then
        echo "[WARN] Could not clone from GitHub. Using local copy."
        PROJECT_DIR="/root/vks-legal-ai"
        mkdir -p "$PROJECT_DIR"
    fi
fi
cd "$PROJECT_DIR"

# 6. Python environment
echo "[6/7] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt
echo "[OK] Python dependencies installed"

# 7. Create data directories
echo "[7/7] Creating data directories..."
mkdir -p data/vector_store data/datasets

# Create start script
cat > start.sh << 'STARTSCRIPT'
#!/bin/bash
echo "Starting VKS Legal AI Platform..."

# Start MongoDB
mongod --fork --logpath /var/log/mongod.log --dbpath /data/db 2>/dev/null || true

# Start Ollama
OLLAMA_HOST=0.0.0.0 ollama serve &>/var/log/ollama.log &
sleep 3

# Start API
cd /root/vks-legal-ai
source venv/bin/activate
nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &>/var/log/vks-api.log &

echo ""
echo "[OK] All services started!"
echo "  API: http://$(hostname -I | awk '{print $1}'):8000"
echo "  Login: admin / vks@2024"
echo ""
echo "Next steps:"
echo "  1. Login to the web interface"
echo "  2. Go to 'Co so du lieu phap luat' (sidebar)"
echo "  3. Click 'Bat dau Index' to download & index legal documents"
echo "  4. Start chatting!"
STARTSCRIPT
chmod +x start.sh

echo ""
echo "============================================"
echo "  SETUP COMPLETE!"
echo "============================================"
echo ""
echo "  Run: ./start.sh"
echo ""
