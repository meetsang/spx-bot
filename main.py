# main.py
import asyncio
import threading
from collect_data import collect_data
from oclh import oclh
from shared_queues import data_queue, subscription_queue
from flask_app import app  # Import from renamed app.py (see next step)
import os
from datetime import datetime
from SPX_9IF_0DTE_v2 import main as spx_9if_main

def create_date_folder():
    today = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join("Data", today)
    os.makedirs(path, exist_ok=True)
    return path + os.sep

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

async def main():
    folder_path = create_date_folder()

    # Start Flask in a background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Start async tasks for data streaming and OHLC
    await asyncio.gather(
        collect_data(folder_path),
        oclh(folder_path),
        spx_9if_main(strategy_name="SPX_9IF_0DTE", data_base_dir="Data")
    )


if __name__ == "__main__":
    asyncio.run(main())