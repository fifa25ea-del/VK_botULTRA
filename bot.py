# =========================
# VK BOT ULTRA (ТОП ВЕРСИЯ)
# =========================

import os
import vk_api
import requests
import csv
import io
import threading
import time
import json
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===== НАСТРОЙКИ =====
TOKEN = "vk1.a.Fmog-6rNUAOTYVwC9-SJBo9dC5a87pMUET1xK_9Raxhk_l5V4Zqx1jCtWJXV7tZLappcJR6fIizfOv9X0OhMLnJbqjzej47aY5evfAj53IvfIgUo2w_vhBpjLGbgiBvaPZ3GrwFTdtR9D0TSGstCQM-L7aFf8_j6oqTxiRV7saahsFCInnvs7u53dtgLJB4lNI_apA5PsIpDqA3IWViAlA"
ADMIN_ID = 888230055

DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"

# ===== ИНИЦИАЛИЗАЦИЯ ФАЙЛОВ =====
def init_files():
    try:
        # Создаем файлы, если их нет
        for file in [FAV_FILE, STATS_FILE]:
            if not os.path.exists(file):
                with open(file, 'w', encoding='utf-8') as f:
                    f.write('{}')  # Создаем пустой JSON файл
            
            # Проверяем права доступа
            if not os.access(file, os.W_OK):
                raise PermissionError(f"Нет прав записи в файл {file}")
                
    except Exception as e:
        print(f"Ошибка при инициализации файлов: {e}")
        exit(1)

# Инициализируем файлы после их определения
init_files()

# ===== ХРАНИЛИЩЕ =====
def load_json(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки {file}: {e}")
        return {}

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения {file}: {e}")

favorites = load_json(FAV_FILE)
stats = load_json(STATS_FILE)

# ===== VK ИНИЦИАЛИЗАЦИЯ =====
try:
    vk_session = vk_api.VkApi(token=TOKEN)
    longpoll = VkBotLongPoll(vk_session, 236843733)  
    vk = vk_session.get_api()
except Exception as e:
    logging.error(f"Ошибка инициализации VK API: {e}")
    exit(1)

# ===== КЭШ =====
class DataCache:
    def __init__(self):
        self.parts = []
        self.wheels = []
        self.donors = []

    def load_csv(self, url):
        r = requests.get(url)
        r.encoding = "cp1251"
        return list(csv.DictReader(io.StringIO(r.text), delimiter=";"))

    def update(self):
        print("🔄 Обновление базы...")
        self.parts = self.load_csv(PARTS_CSV)
        self.wheels = self.load_csv(WHEELS_CSV)
        self.donors = self.load_csv(DONORS_CSV)

cache = DataCache()
cache.update()

# Автообновление в отдельном потоке
def auto_update():
    while True:
        cache.update()
        time.sleep(300)

threading.Thread(target=auto_update, daemon=True).start()
# ===== СОСТОЯНИЯ =====
user_state = {}  # Хранит текущее состояние пользователя
user_results = {}  # Хранит результаты поиска для пользователя
user_index = {}  # Хранит текущий индекс в результатах поиска

# ===== СТАТИСТИКА =====
def track(user_id, action):
    user_id = str(user_id)
    if user_id not in stats:
        stats[user_id] = {"search": 0, "views": 0}
    
    stats[user_id][action] += 1
    save_json(STATS_FILE, stats)

# ===== КНОПКИ =====
def keyboard():
    return json.dumps({
        "one_time": False,
        "buttons": [
            [{"action": {"type": "text", "label": "🚗 Запчасти"}},
             {"action": {"type": "text", "label": "🛞 Диски"}}],
            [{"action": {"type": "text", "label": "🚘 Доноры"}},
             {"action": {"type": "text", "label": "❤️ Избранное"}}],
            [{"action": {"type": "text", "label": "⬅️"}},
             {"action": {"type": "text", "label": "➡️"}}]
        ]
    })

# ===== ОТПРАВКА СООБЩЕНИЙ =====
def send(peer_id, text):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=0,
            keyboard=keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")

# ===== ПОИСК ДЕТАЛЕЙ =====
def find_part(q):
    q = q.lower().replace(" ", "")
    return [p for p in cache.parts if q in str(p.get("Артикул", "")).lower()][:20]

def find_wheels(q):
    q = q.lower()
    return [w for w in cache.wheels if q in str(w.get("Производитель диска", "")).lower()][:20]

# ===== ПОКАЗ РЕЗУЛЬТАТОВ =====
def show_part(user_id):
    track(user_id, "views")
    i = user_index[user_id]
    part = user_results[user_id][i]

    text = f"""🔧 {part.get('Наименование', '')}
Артикул: {part.get('Артикул', '')}
💰 {part.get('Цена', '')} ₽
({i+1}/{len(user_results[user_id])})"""
    
    send(user_id, text)

def show_donor(user_id):
    i = user_index[user_id]
    if 0 <= i < len(cache.donors):
        d = cache.donors[i]
        text = f"""🚘 {d.get('Марка', '')} {d.get('Модель', '')}
Год: {d.get('Год', '')}
Пробег: {d.get('Пробег', '')}
({i+1}/{len(cache.donors)})"""
        send(user_id, text)
    else:
        send(user_id, "❌ Нет данных для отображения")

# ===== ГЛАВНЫЙ ЦИКЛ =====
def run_bot():
    print("🔥 VK BOT ULTRA ЗАПУЩЕН")
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                handle(event)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    run_bot()
