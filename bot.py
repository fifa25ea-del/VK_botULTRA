
# =========================
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

# ===== НАСТРОЙКИ =====
TOKEN = "vk1.a.Fmog-6rNUAOTYVwC9-SJBo9dC5a87pMUET1xK_9Raxhk_l5V4Zqx1jCtWJXV7tZLappcJR6fIizfOv9X0OhMLnJbqjzej47aY5evfAj53IvfIgUo2w_vhBpjLGbgiBvaPZ3GrwFTdtR9D0TSGstCQM-L7aFf8_j6oqTxiRV7saahsFCInnvs7u53dtgLJB4lNI_apA5PsIpDqA3IWViAlA"
ADMIN_ID = 888230055

DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"

# ===== VK INIT =====
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import vk_api

vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkBotLongPoll(vk_session, 236843733)  
vk = vk_session.get_api()

for event in longpoll.listen():
    print(event)  # чтобы видеть все события
    if event.type == VkBotEventType.MESSAGE_NEW:
        peer_id = event.obj.peer_id  # обязательно peer_id
        text = event.obj.text
        print(f"Новое сообщение: {text}")

        vk.messages.send(
            peer_id=peer_id,  # <- используем peer_id
            message="Бот получил ваше сообщение ✅",
            random_id=0
        )

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

# ===== АВТООБНОВЛЕНИЕ =====
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

# ===== СОСТОЯНИЯ =====
user_state = {}
user_results = {}
user_index = {}

# ===== СТАТИСТИКА =====
def track(user_id, action):
    user_id = str(user_id)
    if user_id not in stats:
        stats[user_id] = {"search":0,"views":0}

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
def send(user_id, text):
    vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=0,
        keyboard=keyboard()
    )

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
    d = cache.donors[i]

    text = f"""🚘 {d.get('Марка','')} {d.get('Модель','')}
Год: {d.get('Год','')}
Пробег: {d.get('Пробег','')}
({i+1}/20)"""

    send(user_id, text)

# ===== ЛОГИКА =====
def handle(event):
    user_id = event.user_id
    text = event.text.lower()

    if text == "🚗 запчасти":
        user_state[user_id] = "parts"
        send(user_id, "Введи номер")
        return

    if text == "🛞 диски":
        user_state[user_id] = "wheels"
        send(user_id, "Введи бренд")
        return

    if text == "🚘 доноры":
        user_state[user_id] = "donors"
        user_index[user_id] = 0
        show_donor(user_id)
        return

    if text == "❤️ избранное":
        fav = favorites.get(str(user_id), [])
        send(user_id, f"❤️ {len(fav)} товаров")
        return

    if text == "➡️":
        user_index[user_id] += 1
    elif text == "⬅️":
        user_index[user_id] -= 1

    mode = user_state.get(user_id)

    if mode == "parts":
        if user_id not in user_results:
            track(user_id,"search")
            user_results[user_id] = find_part(text)
            user_index[user_id] = 0

        if not user_results[user_id]:
            send(user_id,"❌ Ничего не найдено")
            return

        show_part(user_id)

    elif mode == "wheels":
        res = find_wheels(text)
        if res:
            send(user_id, f"🛞 {res[0].get('Производитель диска')}")

    elif mode == "donors":
        show_donor(user_id)

# ===== АДМИН =====
def admin(msg, user_id):
    if user_id != ADMIN_ID:
        return False

    if msg == "/stats":
        total = len(stats)
        send(user_id, f"👥 Пользователей: {total}")
        return True

    return False

# ===== START =====
print("🔥 VK ULTRA STARTED")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        if not admin(event.text, event.user_id):
            handle(event)
def run_bot():
    print("Бот запущен")

if name == "__main__":
    run_bot()
