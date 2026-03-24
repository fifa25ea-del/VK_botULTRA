
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
    if event.type == VkBotEventType.MESSAGE_NEW:
        msg = event.obj.message  # получаем объект сообщения
        peer_id = msg['peer_id']

        # Проверяем есть ли текст
        text = msg.get('text', '').strip()
        if not text:
            vk.messages.send(
                peer_id=peer_id,
                message="Я получил сообщение, но оно не текстовое 😅",
                random_id=0
            )
            continue

        print(f"Новое сообщение: {text}")
        vk.messages.send(
            peer_id=peer_id,
            message=f"Бот получил: {text}",
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
# ===== ОБРАБОТКА СООБЩЕНИЙ =====
def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()
    
    if not text:
        send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
        return

    text_lower = text.lower()

    # ==== Команды бота ====
    if text_lower == "/start":
        send(peer_id, "Привет! 👋\nЯ ваш VK-бот 🚀\nВыберите команду:\n🚗 запчасти\n🛞 диски\n🚘 доноры\n❤️ избранное")
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

    # ==== Режим поиска по состоянию пользователя ====
    mode = user_state.get(peer_id)

    if mode == "parts":
        if peer_id not in user_results:
            track(peer_id, "search")
            user_results[peer_id] = find_part(text)
            user_index[peer_id] = 0

        if not user_results[peer_id]:
            send(peer_id, "❌ Ничего не найдено")
            return

        show_part(peer_id)

    elif mode == "wheels":
        res = find_wheels(text)
        if res:
            send(peer_id, f"🛞 {res[0].get('Производитель диска')}")

    elif mode == "donors":
        show_donor(peer_id)

    else:
        # Если пользователь не выбрал режим
        send(peer_id, "Я не понимаю команду 😅. Попробуйте /start для списка команд.")

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
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            # логируем любое сообщение
            text = event.obj.message.get('text')
            print("Новое сообщение:", text)

            # сначала проверяем команды администратора
            if admin(text, event.obj.message['peer_id']):
                continue

            # вызываем обработчик, который реагирует на команды и текст
            handle(event)
