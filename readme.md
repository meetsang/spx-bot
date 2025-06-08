# SPX Trading Bot

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
