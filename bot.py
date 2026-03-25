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

# Проверка прав доступа
if not os.access(FAV_FILE, os.W_OK):
logging.error(f"Нет прав на запись в файл {FAV_FILE}")
exit(1)

if not os.access(STATS_FILE, os.W_OK):
logging.error(f"Нет прав на запись в файл {STATS_FILE}")
exit(1) 

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

# ===== VK INIT =====
vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkBotLongPoll(vk_session, 236843733)  
vk = vk_session.get_api()

# ===== КЭШ =====
class DataCache:
    def __init__(self):
        self.parts = []
        self.wheels = []
        self.donors = []

    def load_csv(self, url):
        try:
            r = requests.get(url, timeout=10)
            r.encoding = "cp1251"
            return list(csv.DictReader(io.StringIO(r.text), delimiter=";"))
        except Exception as e:
            logging.error(f"Ошибка загрузки CSV {url}: {e}")
            return []

    def update(self):
        logging.info("🔄 Обновление базы...")
        self.parts = self.load_csv(PARTS_CSV)
        self.wheels = self.load_csv(WHEELS_CSV)
        self.donors = self.load_csv(DONORS_CSV)

cache = DataCache()
cache.update()

# ===== АВТООБНОВЛЕНИЕ =====
def auto_update():
    while True:
        try:
            cache.update()
        except Exception as e:
            logging.error(f"Ошибка автообновления: {e}")
        time.sleep(300)

threading.Thread(target=auto_update, daemon=True).start()

# ===== ХРАНИЛИЩЕ =====
def load_json(file):
    try:
        # Проверяем существование файла
        if not os.path.exists(file):
            # Создаем пустой файл, если его нет
            with open(file, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        
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

# Создаем начальные файлы, если их нет
if not os.path.exists(FAV_FILE):
    with open(FAV_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

if not os.path.exists(STATS_FILE):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

favorites = load_json(FAV_FILE)
stats = load_json(STATS_FILE)

# ===== СОСТОЯНИЯ =====
user_state = {}
user_results = {}
user_index = {}

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

# ===== SEND =====
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

# ===== ПОИСК =====
def find_part(q):
    q = q.lower().replace(" ","")
    return [p for p in cache.parts if q in str(p.get("Артикул","")).lower()][:20]

def find_wheels(q):
    q = q.lower()
    return [w for w in cache.wheels if q in str(w.get("Производитель диска","")).lower()][:20]

# ===== КАРТОЧКИ =====
def show_part(user_id):
    track(user_id,"views")
    i = user_index[user_id]
    part = user_results[user_id][i]

    text = f"""🔧 {part.get('Наименование','')}
Артикул: {part.get('Артикул','')}
💰 {part.get('Цена','')} ₽
({i+1}/{len(user_results[user_id])})"""

    send(user_id, text)

def show_donor(user_id):
    i = user_index[user_id]
    if 0 <= i < len(cache.donors):
        d = cache.donors[i]
        text = f"""🚘 {d.get('Марка','')} {d.get('Модель','')}
Год: {d.get('Год','')}
Пробег: {d.get('Пробег','')}
({i+1}/{len(cache.donors)})"""
        send(user_id, text)
    else:
        send(user_id, "❌ Нет данных для отображения")

# ===== ЛОГИКА =====
def get_main_keyboard():
    keyboard = {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "🚗 Запчасти"}, "color": "primary"},
                {"action": {"type": "text", "label": "🛞 Диски"}, "color": "primary"}
            ],
            [
                {"action": {"type": "text", "label": "🚘 Доноры"}, "color": "positive"},
                {"action": {"type": "text", "label": "❤️ Избранное"}, "color": "negative"}
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)

# ===== ОБРАБОТКА СООБЩЕНИЙ =====
def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()

    if not text:
        send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
        return

    text_lower = text.lower()

    # ==== Команда /start ====
    if text_lower in ["/start", "start", "начать"]:
        send(peer_id, "Привет! 👋 Выберите команду:")
        return

    # ==== Основные кнопки ====
    if text_lower == "🚗 запчасти":
        user_state[peer_id] = "parts"
        vk.messages.send(
            peer_id=peer_id,
            message="Введи номер детали или код:",
            random_id=0
        )
        return
    elif text_lower == "🛞 диски":
        user_state[peer_id] = "wheels"
        vk.messages.send(
            peer_id=peer_id,
            message="Введи бренд диска:",
            random_id=0
        )
        return

    # Обработка навигации по результатам поиска
    elif text_lower == "➡️":
        if user_state.get(peer_id) in ["parts", "donors"]:
            user_index[peer_id] = min(user_index.get(peer_id, 0) + 1, len(user_results.get(peer_id, [])) - 1)
            if user_state[peer_id] == "parts":
                show_part(peer_id)
            elif user_state[peer_id] == "donors":
                show_donor(peer_id)

    elif text_lower == "⬅️":
        if user_state.get(peer_id) in ["parts", "donors"]:
            user_index[peer_id] = max(user_index.get(peer_id, 0) - 1, 0)
            if user_state[peer_id] == "parts":
                show_part(peer_id)
            elif user_state[peer_id] == "donors":
                show_donor(peer_id)

    # Обработка поиска по состоянию
    mode = user_state.get(peer_id)
    
    if mode == "parts":
        track(peer_id, "search")
        user_results[peer_id] = find_part(text)
        user_index[peer_id] = 0
        
        if user_results[peer_id]:
            show_part(peer_id)
        else:
            send(peer_id, "❌ Ничего не найдено")

    elif mode == "wheels":
        results = find_wheels(text)
        if results:
            send(peer_id, f"🛞 Найденные диски: {results[0].get('Производитель диска')}")
        else:
            send(peer_id, "❌ Диски не найдены")

    elif mode == "donors":
        show_donor(peer_id)

# ===== АДМИНКА =====
def admin_commands(text, user_id):
    if user_id != ADMIN_ID:
        return False
    
    if text == "/stats":
        total_users = len(stats)
        send(user_id, f"👥 Всего пользователей: {total_users}")
        return True
    
    return False

# ===== ГЛАВНЫЙ ЦИКЛ =====
def run_bot():
    print("🔥 VK BOT ULTRA ЗАПУЩЕН")
    
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                msg = event.obj.message
                peer_id = msg['peer_id']
                text = msg.get('text', '').strip()
                
                # Проверка админ-команд
                if admin_commands(text, peer_id):
                    continue
                
                # Обработка сообщений
                handle(event)
                
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    run_bot()
