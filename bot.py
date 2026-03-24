import os
import json
import csv
import requests
from io import StringIO
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

# ===== ЗАГРУЗКА ПЕРЕМЕННЫХ =====
load_dotenv()
TOKEN = os.getenv("vk1.a.Fmog-6rNUAOTYVwC9-SJBo9dC5a87pMUET1xK_9Raxhk_l5V4Zqx1jCtWJXV7tZLappcJR6fIizfOv9X0OhMLnJbqjzej47aY5evfAj53IvfIgUo2w_vhBpjLGbgiBvaPZ3GrwFTdtR9D0TSGstCQM-L7aFf8_j6oqTxiRV7saahsFCInnvs7u53dtgLJB4lNI_apA5PsIpDqA3IWViAlA")
ADMIN_ID = int(os.getenv("888230055", 0))
GROUP_ID = 236843733  # ID вашей группы

if not TOKEN:
    raise ValueError("TOKEN пустой! Проверьте .env")

# ===== VK INIT =====
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# ===== ДАННЫЕ =====
user_state = {}
user_index = {}
user_results = {}
favorites = {}
stats = {}

# ===== CSV ССЫЛКИ =====
DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

cache = {
    "donors": [],
    "parts": [],
    "wheels": []
}

# ===== ФУНКЦИЯ ЗАГРУЗКИ CSV =====
def load_csv(url):
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        f = StringIO(resp.text)
        reader = csv.DictReader(f)
        return list(reader)
    except Exception as e:
        print(f"Ошибка загрузки CSV: {e}")
        return []

def reload_all_csv():
    cache["donors"] = load_csv(DONORS_CSV)
    cache["parts"] = load_csv(PARTS_CSV)
    cache["wheels"] = load_csv(WHEELS_CSV)
    print("CSV файлы обновлены ✅")

reload_all_csv()

# ===== ФУНКЦИЯ ОТПРАВКИ =====
def send(peer_id, message, keyboard=None):
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        random_id=0,
        keyboard=keyboard
    )

# ===== КНОПКИ =====
def get_main_keyboard():
    kb = {
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
    return json.dumps(kb, ensure_ascii=False)

# ===== КАРТОЧКИ =====
def show_part(user_id):
    results = user_results.get(user_id, [])
    i = user_index.get(user_id, 0)
    if not results or i >= len(results):
        send(user_id, "❌ Ничего не найдено")
        return
    part = results[i]
    text = f"🔧 {part.get('Наименование','')}\nАртикул: {part.get('Артикул','')}\n💰 {part.get('Цена','')} ₽\n({i+1}/{len(results)})"
    send(user_id, text)

def show_donor(user_id):
    i = user_index.get(user_id, 0)
    donors = cache.get("donors", [])
    if not donors or i >= len(donors):
        send(user_id, "❌ Доноров нет")
        return
    d = donors[i]
    text = f"🚘 {d.get('Марка','')} {d.get('Модель','')}\nГод: {d.get('Год','')}\nПробег: {d.get('Пробег','')} ({i+1}/{len(donors)})"
    send(user_id, text)

# ===== ПОИСК =====
def find_part(text):
    return [p for p in cache.get("parts", []) if text.lower() in p.get("Наименование","").lower()]

def find_wheels(text):
    return [w for w in cache.get("wheels", []) if text.lower() in w.get("Производитель диска","").lower()]

# ===== ЛОГИКА ОБРАБОТКИ СООБЩЕНИЙ =====
def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text','').strip()
    if not text:
        send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
        return
    tl = text.lower()

    if tl == "/start":
        send(peer_id, "Привет! 👋\nВыберите команду:", keyboard=get_main_keyboard())
        return

    if tl == "🚗 запчасти":
        user_state[peer_id] = "parts"
        send(peer_id, "Введите номер детали или код:")
        return
    if tl == "🛞 диски":
        user_state[peer_id] = "wheels"
        send(peer_id, "Введите бренд диска:")
        return
    if tl == "🚘 доноры":
        user_state[peer_id] = "donors"
        user_index[peer_id] = 0
        show_donor(peer_id)
        return
    if tl == "❤️ избранное":
        fav = favorites.get(str(peer_id), [])
        send(peer_id, f"❤️ У вас {len(fav)} товаров в избранном")
        return

    if tl == "➡️":
        user_index[peer_id] = user_index.get(peer_id,0)+1
    if tl == "⬅️":
        user_index[peer_id] = user_index.get(peer_id,0)-1

    mode = user_state.get(peer_id)
    if mode == "parts":
        if peer_id not in user_results:
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
        send(peer_id, "Я не понимаю команду 😅. Попробуйте /start")

# ===== АДМИН =====
def admin(msg, peer_id):
    if peer_id != ADMIN_ID:
        return False
    if msg == "/stats":
        send(peer_id, f"👥 Всего пользователей: {len(stats)}")
        return True
    if msg == "/reload":
        reload_all_csv()
        send(peer_id, "✅ CSV обновлены")
        return True
    return False

# ===== ЗАПУСК =====
def run_bot():
    print("🔥 VK ULTRA BOT STARTED")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            peer_id = event.obj.message['peer_id']
            text = event.obj.message.get('text')
            print(f"Новое сообщение от {peer_id}: {text}")
            if admin(text, peer_id):
                continue
            handle(event)
