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

#pull changes:

#install git: 
sudo apt update
sudo apt install git
#configure git:
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
#clone git repository:
git clone https://github.com/meetsang/spx-bot
This downloads the repo to your current directory.

********USING UV TO SET UP A NEW ENV: *******
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
git clone <your-repo-url>
cd your-project-name
```

## 3. Initialize with uv (Super Simple)

```bash
# Create virtual environment and install from requirements.txt in one command
uv venv

# Activate the virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install all dependencies from requirements.txt
uv pip install -r requirements.txt
```

## Even Simpler - One Command Setup

```bash
# This creates venv AND installs requirements in one go
uv pip install -r requirements.txt
```

