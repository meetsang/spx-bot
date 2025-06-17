. 48# SPX Tra,☆, ding Bot

This is a modular Python trading bot system designed for SPX index analysis and automation. It includes:

- Real-time SPX price collection and storage
- SPX options pricing and Greeks calculation
- GEX (Gamma Exposure) level detection and visualization
- Trade execution framework (planned)
- A Flask-based web UI for running on-demand analysis
- CSV-based architecture to avoid databases

All code is designed to run locally, even on a mobile device (e.g. Termux), and integrates easily with GitHub for syncing across devices.

---

## 🔁 Git Workflow: Keeping Code in Sync

### ✅ From Termux (Phone): Push Local Changes to GitHub

```bash
cd ~/spx-bot
git status               # See what changed
git add .                # Stage all changes
git commit -m "Your message"
git push                 # Upload to GitHub


********USING UV TO SET UP ON A NEW MACHINE: *******
## 1. Install uv on Your New Cloud Machine

```bash
# Install uv (much faster than Poetry's installer)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Reload your shell
source ~/.bashrc
```

## 2. Clone and Set Up Your Project

```bash
# Clone your project
git clone https://github.com/meetsang/spx-bot
cd spx-bot
# This downloads the repo to your current directory.
```

# 3. Initialize with uv (Super Simple)

```bash
# Create virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install all dependencies from requirements.txt
uv pip install -r requirements.txt
```
# 4. Running Manually:
cd myprojects/spx-bot

source .venv/bin/activate

python main.py > /var/log/main.log 2>&1 &

to check logs: nano Data/2025-06-17/spx.csv

to kill: pkill -f main.py

# 5. Running Automated:
Put following in startup section:
#!/bin/bash
cd /home/YOUR_USERNAME/myprojects/spx-bot
source .venv/bin/activate
nohup python main.py > /var/log/main.log 2>&1 &



