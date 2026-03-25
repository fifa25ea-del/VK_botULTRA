# VK BOT ULTRA (ТОП ВЕРСИЯ)
# =========================

import vk_api
import requests
import csv
import io
import threading
import time
import json
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import logging
import re

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
LOG_FILE = "logs.txt"

# ===== ИНИЦИАЛИЗАЦИЯ VK =====
vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkBotLongPoll(vk_session, 236843733)  
vk = vk_session.get_api()

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С ТЕКСТОМ =====
def split_words(text):
    return re.findall(r'\w+', text.lower())

def fix_a(text):
    return text.lower().replace("а", "a")

# ===== ИНИЦИАЛИЗАЦИЯ ХРАНИЛИЩА =====
def load_json(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

favorites = load_json(FAV_FILE)
stats = load_json(STATS_FILE)

# ===== СТАТИСТИКА =====
def track(user_id, action):
    user_id = str(user_id)
    if user_id not in stats:
        stats[user_id] = {
            "searches": 0,
            "views": 0,
            "favorites": 0
        }
    stats[user_id][action] += 1
    save_json(STATS_FILE, stats)

# ===== КЭШ =====
class DataCache:
    def __init__(self):
        self.parts = []
        self.wheels = []
        self.donors = []
        self.number_key = None
        self.name_key = None
        self.photo_key = None

    def load_csv(self, url):
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=30)
        r.encoding = "cp1251"
        csv_file = io.StringIO(r.text)
        reader = csv.DictReader(csv_file, delimiter=";")
        return list(reader), reader.fieldnames

    def update(self):
        print("🔄 Обновление базы...")
        self.donors, _ = self.load_csv(DONORS_CSV)
        self.donors.reverse()
        
        self.parts, headers = self.load_csv(PARTS_CSV)
        self.wheels, headers2 = self.load_csv(WHEELS_CSV)
        
        for h in headers:
            h_low = h.lower()
            if "артикул" in h_low or "номер" in h_low:
                self.number_key = h
            if "наимен" in h_low or "название" in h_low:
                self.name_key = h
            if "фото" in h_low or "image" in h_low:
                self.photo_key = h

cache = DataCache()
cache.update()

# Автообновление в отдельном потоке
def auto_update():
    while True:
        cache.update()
        time.sleep(300)

threading.Thread(target=auto_update, daemon=True).start()

# ===== ПОИСК =====
def find_part(query):
    query = normalize(fix_a(query))
    results = []
    for part in cache.parts:
        raw_number = part.get(cache.number_key, "")
        number = normalize(fix_a(raw_number))
        if not number:
            continue
        if query in number:
            results.append(part)
        if len(results) >= 20:
            break
    return results

def find_wheels(query):
    query = query.lower().replace(" ", "").replace("-", "")
    results = []
    for part in cache.wheels:
        radius = str(part.get("Диаметр диска", "")).lower().replace(" ", "")
        brand = str(part.get("Производитель диска", "")).lower()
        model = str(part.get("Модель диска", "")).lower()
        if query in radius or query in f"r{radius}":
            results.append(part)
        elif query in brand or query in model:
            results.append(part)
        if len(results) >= 20:
            break
    return results

# ===== КАРТОЧКИ ТОВАРОВ =====
def send_part_card(peer_id, index):
    track(peer_id, "views")
    results = user_results.get(peer_id, [])
    if not results or index >= len(results):
        return
    
    part = results[index]
    text = f"""🔧 {part.get(cache.name_key, '')}
Артикул: {part.get('Артикул', '')}
Цена: {part.get('Цена', '')} ₽
В наличии: {part.get('Наличие', '')}
({index+1}/{len(results)})"""
    
    send(peer_id, text)

def send_wheel_card(peer_id, index):
    track(peer_id, "views")
    results = user_results.get(peer_id, [])
    if not results or index >= len(results):
        return
    
    part = results[index]
    text = f"""🛞 {part.get('Производитель диска', '')} {part.get('Модель диска', '')}
R{part.get('Диаметр диска', '')}
Ширина: {part.get('Ширина диска', '')}
Вылет: {part.get('Вылет диска', '')}
Цена: {part.get('Цена', '')} ₽
({index+1}/{len(results)})"""
    
    send(peer_id, text)

def send_donor_card(peer_id, index):
    track(peer_id, "views")
    results = user_results.get(peer_id, [])
    if not results or index >= len(results):
        return
    
    donor = results[index]
    text = f"""🚘 {donor.get('Марка', '')} {donor.get('Модель', '')}
Год: {donor.get('Год', '')}
Пробег: {donor.get('Пробег', '')}
Цена: {donor.get('Цена', '')} ₽
({index+1}/{len(results)})"""
    
    send(peer_id, text)

# ===== ОТПРАВКА СООБЩЕНИЙ =====
def send(peer_id, text, keyboard=None):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=0,
            keyboard=keyboard if keyboard else get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")

# ===== КНОПКИ =====
def get_main_keyboard():
    return json.dumps({
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "open_app", "label": "🚗 Запчасти", "payload": json.dumps({"action": "parts"})}, "color": "primary"}
            ],
            [
                {"action": {"type": "open_app", "label": "🛞 Диски", "payload": json.dumps({"action": "wheels"})}, "color": "primary"}
            ],
            [
                {"action": {"type": "open_app", "label": "🚘 Доноры", "payload": json.dumps({"action": "donors"})}, "color": "positive"}
            ],
            [
                {"action": {"type": "open_app", "label": "❤️ Избранное", "payload": json.dumps({"action": "favorites"})}, "color": "negative"}
            ]
        ],
        "inline": true
    })

# ===== ОБРАБОТКА СООБЩЕНИЙ =====
def handle(event):
    if event.type == VkBotEventType.MESSAGE_NEW:
        handle_message(event)
    elif event.type == VkBotEventType.MESSAGE_EVENT:
        handle_callback(event)

def handle_message(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip().lower()

    # Обработка текстовых сообщений
    if text in ["/start", "начать"]:
        send(peer_id, "Привет! 👋 Выберите команду:", keyboard=get_main_keyboard())
        return

    # Обработка команд
    if text == "🚗 запчасти":
        user_state[peer_id] = "parts"
        send(peer_id, "Введи номер детали или код:")
        return

def handle_callback(event):
    data = event.obj.payload
    peer_id = event.obj.peer_id
    
    try:
        payload = json.loads(data)
        action = payload.get('action')
        
        if action == 'parts':
            user_state[peer_id] = "parts"
            send(peer_id, "Введи номер детали или код:")
            return
            
        if action == 'wheels':
            user_state[peer_id] = "wheels"
            send(peer_id, "Введи бренд диска:")
            return
            
        if action == 'donors':
            user_state[peer_id] = "donors"
            send(peer_id, "Выбор доноров")
            return
            
        if action == 'favorites':
            send(peer_id, "Ваши избранные товары")
            return
            
    except Exception as e:
        logging.error(f"Ошибка обработки callback: {e}")

# ===== ГЛАВНЫЙ ЦИКЛ =====
# Продолжение функции run_bot
def run_bot():
    print("🔥 VK BOT ULTRA ЗАПУЩЕН")
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                handle(event)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")

# ===== ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЙ =====
user_state = {}
user_results = {}
user_index = {}

# ===== СТАРТ БОТА =====
def run_bot():
    print("🔥 VK BOT ULTRA ЗАПУЩЕН")
    try:
        for event in longpoll.listen():
            handle(event)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    run_bot()
# ===== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ =====

def normalize(text):
    return str(text).lower().replace(" ", "").replace("-", "")

def log_search(user_id, query, mode):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{time} | {user_id} | {mode} | {query}\n")
    except Exception as e:
        print("Ошибка логирования:", e)

# ===== ИЗБРАННОЕ =====
def add_to_favorites(user_id, item):
    user_id = str(user_id)
    if user_id not in favorites:
        favorites[user_id] = []
    favorites[user_id].append(item)
    save_json(FAV_FILE, favorites)

def remove_from_favorites(user_id, item_id):
    user_id = str(user_id)
    if user_id in favorites:
        favorites[user_id] = [item for item in favorites[user_id] if item.get('Артикул') != item_id]
        save_json(FAV_FILE, favorites)

# ===== АДМИНИСТРАТОРСКИЕ КОМАНДЫ =====
def admin_commands(text, user_id):
    if user_id != ADMIN_ID:
        return False
    
    if text == "/stats":
        total_users = len(stats)
        send(user_id, f"👥 Всего пользователей: {total_users}")
        return True
    
    return False
