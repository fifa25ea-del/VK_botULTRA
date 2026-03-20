import threading
import time
from services.csv_loader import load_all

def loop():
    while True:
        print("🔄 Обновление базы")
        load_all()
        time.sleep(300)

def start_auto_update():
    threading.Thread(target=loop, daemon=True).start()
