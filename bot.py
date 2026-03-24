# VK BOT ULTRA MAX
# =========================

import os
import json
import requests
import csv
import io
import threading
import time
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

# ===== НАСТРОЙКИ =====
load_dotenv = lambda: None  # если используешь .env, подключи dotenv
TOKEN = os.getenv("vk1.a.Fmog-6rNUAOTYVwC9-SJBo9dC5a87pMUET1xK_9Raxhk_l5V4Zqx1jCtWJXV7tZLappcJR6fIizfOv9X0OhMLnJbqjzej47aY5evfAj53IvfIgUo2w_vhBpjLGbgiBvaPZ3GrwFTdtR9D0TSGstCQM-L7aFf8_j6oqTxiRV7saahsFCInnvs7u53dtgLJB4lNI_apA5PsIpDqA3IWViAlA") or "ВАШ_ТОКЕН_ЗДЕСЬ"
GROUP_ID = 236843733  # ID вашей группы
ADMIN_ID = int(os.getenv("ADMIN_ID", 888230055))

# ===== ФАЙЛЫ ДАННЫХ =====
FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"

DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

# ===== ИНИЦИАЛИЗАЦИЯ VK =====
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# ===== ПЕРЕМЕННЫЕ =====
user_state = {}
user_index = {}
user_results = {}
favorites = {}
stats = {}

# ===== УТИЛИТЫ =====
def load_json(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

favorites = load_json(FAV_FILE)
stats = load_json(STATS_FILE)

# ===== ФУНКЦИЯ ОТПРАВКИ СООБЩЕНИЯ =====
def send(peer_id, message, keyboard=None):
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        keyboard=keyboard,
        random_id=0
    )

# ===== КЛАВИАТУРА МЕНЮ =====
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

# ===== ФУНКЦИИ ПОИСКА =====
def find_part(query):
    # сюда можно добавить поиск в PARTS_CSV
    return [{"Марка": "Toyota", "Модель": "Corolla", "Год": "2018", "Пробег": "50000 км"}]

def show_part(peer_id):
    i = user_index.get(peer_id, 0)
    results = user_results.get(peer_id, [])
    if not results:
        send(peer_id, "❌ Ничего не найдено")
        return
    d = results[i % len(results)]
    text = f"🚘 {d.get('Марка','')} {d.get('Модель','')}\nГод: {d.get('Год','')}\nПробег: {d.get('Пробег','')}\n({i+1}/{len(results)})"
    send(peer_id, text)

def find_wheels(query):
    # пример данных
    return [{"Производитель диска": "BBS"}]

def show_donor(peer_id):
    send(peer_id, "Показ доноров")  # сюда можно вставить логику

def track(user_id, action):
    stats[user_id] = stats.get(user_id, 0) + 1
    save_json(STATS_FILE, stats)

# ===== АДМИН-КОМАНДЫ =====
def admin(msg, peer_id):
    if peer_id != ADMIN_ID:
        return False
    if msg == "/stats":
        total = len(stats)
        send(peer_id, f"👥 Пользователей: {total}")
        return True
    return False

# ===== ОСНОВНОЙ ОБРАБОТЧИК =====
def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()
    if not text:
        send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
        return

    text_lower = text.lower()

    # ==== Команды меню ====
    if text_lower == "/start":
        send(peer_id, "Привет! 👋\nВыберите команду:", keyboard=get_main_keyboard())
        return
    elif text_lower == "🚗 запчасти":
        user_state[peer_id] = "parts"
        send(peer_id, "Введи номер детали или код:")
        return
    elif text_lower == "🛞 диски":
        user_state[peer_id] = "wheels"
        send(peer_id, "Введи бренд диска:")
        return
    elif text_lower == "🚘 доноры":
        user_state[peer_id] = "donors"
        user_index[peer_id] = 0
        show_donor(peer_id)
        return
    elif text_lower == "❤️ избранное":
        fav = favorites.get(str(peer_id), [])
        send(peer_id, f"❤️ У вас {len(fav)} товаров в избранном")
        return
    elif text_lower == "➡️":
        user_index[peer_id] = user_index.get(peer_id, 0) + 1
    elif text_lower == "⬅️":
        user_index[peer_id] = user_index.get(peer_id, 0) - 1

    # ==== Режим поиска ====
    mode = user_state.get(peer_id)
    if mode == "parts":
        if peer_id not in user_results:
            track(peer_id, "search")
            user_results[peer_id] = find_part(text)
            user_index[peer_id] = 0
        show_part(peer_id)
    elif mode == "wheels":
        res = find_wheels(text)
        if res:
            send(peer_id, f"🛞 {res[0].get('Производитель диска')}")
    elif mode == "donors":
        show_donor(peer_id)
    else:
        send(peer_id, "Я не понимаю команду 😅. Попробуйте /start.")

# ===== ЗАПУСК БОТА =====
def run_bot():
    print("🔥 VK ULTRA MAX STARTED")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            handle(event)
