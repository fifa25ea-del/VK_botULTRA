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
        for file in [FAV_FILE, STATS_FILE]:
            if not os.path.exists(file):
                with open(file, 'w', encoding='utf-8') as f:
                    f.write('{}')
            if not os.access(file, os.W_OK):
                raise PermissionError(f"Нет прав записи в файл {file}")
    except Exception as e:
        print(f"Ошибка при инициализации файлов: {e}")
        exit(1)

init_files()

# ===== ИНИЦИАЛИЗАЦИЯ VK =====
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

# Автообновление
def auto_update():
    while True:
        cache.update()
        time.sleep(300)

threading.Thread(target=auto_update, daemon=True).start()

# ===== ХРАНИЛИЩЕ =====
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

# ===== ПОИСК =====
def find_part(q):
    q = q.lower().replace(" ", "")
    return [p for p in cache.parts if q in str(p.get("Артикул", "")).lower()][:20]

def find_wheels(q):
    q = q.lower()
    return [w for w in cache.wheels if q in str(w.get("Производитель диска", "")).lower()][:20]

# ===== КАРТОЧКИ =====

# Отображение информации о детали
def show_part(user_id):
    track(user_id, "views")
    i = user_index[user_id]
    part = user_results[user_id][i]
    
    text = f"""🔧 {part.get('Наименование', '')}
Артикул: {part.get('Артикул', '')}
Цена: {part.get('Цена', '')} ₽
В наличии: {part.get('Наличие', '')}
({i+1}/{len(user_results[user_id])})"""
    
    send(user_id, text)

# Отображение информации о диске
def show_wheel(user_id):
    track(user_id, "views")
    i = user_index[user_id]
    wheel = user_results[user_id][i]
    
    text = f"""🛞 {wheel.get('Производитель диска', '')}
Размер: {wheel.get('Размер', '')}
Ширина: {wheel.get('Ширина', '')}
Вылет: {wheel.get('Вылет', '')}
({i+1}/{len(user_results[user_id])})"""
    
    send(user_id, text)

# Отображение информации о доноре
def show_donor(user_id):
    track(user_id, "views")
    i = user_index[user_id]
    donor = cache.donors[i]
    
    text = f"""🚘 {donor.get('Марка', '')} {donor.get('Модель', '')}
Год: {donor.get('Год', '')}
Пробег: {donor.get('Пробег', '')}
Цена: {donor.get('Цена', '')} ₽
({i+1}/20)"""
    
    send(user_id, text)

# Отображение избранного
def show_favorites(user_id):
    fav_items = favorites.get(str(user_id), [])
    
    if not fav_items:
        send(user_id, "❤️ В избранном пока ничего нет")
        return
    
    text = "❤️ Избранное:\n"
    for i, item in enumerate(fav_items, 1):
        text += f"{i}. {item.get('Наименование', '')} - {item.get('Цена', '')} ₽\n"
    
    send(user_id, text)

# Улучшенная функция отправки сообщений
def send(user_id, text):
    try:
        vk.messages.send(
            peer_id=user_id,
            message=text,
            random_id=0,
            keyboard=get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")

# Обработка навигации по результатам
def navigate_results(user_id, direction):
    if direction == "➡️":
        user_index[user_id] = min(user_index[user_id] + 1, len(user_results[user_id]) - 1)
    elif direction == "⬅️":
        user_index[user_id] = max(user_index[user_id] - 1, 0)
    
    mode = user_state[user_id]
    if mode == "parts":
        show_part(user_id)
    elif mode == "wheels":
        show_wheel(user_id)
    elif mode == "donors":
        show_donor(user_id)
# ===== ОБРАБОТКА СООБЩЕНИЙ =====
def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()
    text_lower = text.lower()

    if not text:
        send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
        return

    # Обработка команды /start
    if text_lower == "/start":
        send(peer_id, "Привет! 👋 Выберите команду:", keyboard=get_main_keyboard())
        return

    # Обработка основных команд
    if text_lower == "🚗 запчасти":
        user_state[peer_id] = "parts"
        send(peer_id, "Введи номер детали или код:")
        return

    if text_lower == "🛞 диски":
        user_state[peer_id] = "wheels"
        send(peer_id, "Введи бренд диска:")
        return

    if text_lower == "🚘 доноры":
        user_state[peer_id] = "donors"
        user_index[peer_id] = 0
        show_donor(peer_id)
        return

    if text_lower == "❤️ избранное":
        fav = favorites.get(str(peer_id), [])
        send(peer_id, f"❤️ У вас {len(fav)} товаров в избранном")
        return

    # Обработка навигации
    if text_lower in ["➡️", "⬅️"]:
        navigate_results(peer_id, text_lower)
        return

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

# ===== НАВИГАЦИЯ =====
def navigate_results(user_id, direction):
    try:
        if direction == "➡️":
            user_index[user_id] = min(user_index[user_id] + 1, len(user_results[user_id]) - 1)
        elif direction == "⬅️":
            user_index[user_id] = max(user_index[user_id] - 1, 0)

        mode = user_state[user_id]
        if mode == "parts":
            show_part(user_id)
        elif mode == "wheels":
            show_wheel(user_id)
        elif mode == "donors":
            show_donor(user_id)
    except Exception as e:
        logging.error(f"Ошибка навигации: {e}")
        send(user_id, "❌ Ошибка при навигации")

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
