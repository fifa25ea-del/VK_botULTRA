import os
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"


# ===== ЗАГРУЗКА ПЕРЕМЕННЫХ =====
load_dotenv()
TOKEN = os.getenv("vk1.a.Fmog-6rNUAOTYVwC9-SJBo9dC5a87pMUET1xK_9Raxhk_l5V4Zqx1jCtWJXV7tZLappcJR6fIizfOv9X0OhMLnJbqjzej47aY5evfAj53IvfIgUo2w_vhBpjLGbgiBvaPZ3GrwFTdtR9D0TSGstCQM-L7aFf8_j6oqTxiRV7saahsFCInnvs7u53dtgLJB4lNI_apA5PsIpDqA3IWViAlA")
GROUP_ID = 236843733  # числовой ID вашей группы
ADMIN_ID = int(os.getenv("888230055", 0))

if not TOKEN:
    raise ValueError("TOKEN пустой! Проверьте .env")

# ===== ИНИЦИАЛИЗАЦИЯ VK =====
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# ===== ДАННЫЕ =====
user_state = {}
user_index = {}
user_results = {}
favorites = {}
stats = {}

# ===== ФУНКЦИЯ ОТПРАВКИ СООБЩЕНИЯ =====
def send(peer_id, message):
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        random_id=0
    )

# ===== ФУНКЦИИ ПОИСКА/ПОКАЗА (ВАШИ) =====
def find_part(text):
    # ваша логика поиска деталей
    return []

def show_part(user_id):
    # ваша логика показа части
    send(user_id, "Показ деталей")

def find_wheels(text):
    # ваша логика поиска дисков
    return []

def show_donor(user_id):
    # ваша логика показа доноров
    send(user_id, "Показ доноров")

def track(user_id, action):
    # ваша логика трекинга
    pass

# ===== ЛОГИКА ОБРАБОТКИ СООБЩЕНИЙ =====
def handle(event):
    peer_id = event.obj.peer_id
    text = event.obj.text
    if text is None:
        return
    text_lower = text.lower()
    
    if text_lower == "🚗 запчасти":
        user_state[peer_id] = "parts"
        send(peer_id, "Введи номер")
        return

    if text_lower == "🛞 диски":
        user_state[peer_id] = "wheels"
        send(peer_id, "Введи бренд")
        return

    if text_lower == "🚘 доноры":
        user_state[peer_id] = "donors"
        user_index[peer_id] = 0
        show_donor(peer_id)
        return

    if text_lower == "❤️ избранное":
        fav = favorites.get(str(peer_id), [])
        send(peer_id, f"❤️ {len(fav)} товаров")
        return

    if text_lower == "➡️":
        user_index[peer_id] = user_index.get(peer_id,0) + 1
    elif text_lower == "⬅️":
        user_index[peer_id] = user_index.get(peer_id,0) - 1

    mode = user_state.get(peer_id)

    if mode == "parts":
        if peer_id not in user_results:
            track(peer_id,"search")
            user_results[peer_id] = find_part(text)
            user_index[peer_id] = 0

        if not user_results[peer_id]:
            send(peer_id,"❌ Ничего не найдено")
            return

        show_part(peer_id)

    elif mode == "wheels":
        res = find_wheels(text)
        if res:
            send(peer_id, f"🛞 {res[0].get('Производитель диска')}")

    elif mode == "donors":
        show_donor(peer_id)

# ===== АДМИН-КОМАНДЫ =====
def admin(msg, peer_id):
    if peer_id != ADMIN_ID:
        return False

    if msg == "/stats":
        total = len(stats)
        send(peer_id, f"👥 Пользователей: {total}")
        return True

    return False

# ===== ОСНОВНОЙ ЦИКЛ =====
print("🔥 VK ULTRA STARTED")

def run_bot():
    print("Бот запущен")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            peer_id = event.obj.peer_id
            text = event.obj.text
            print(f"Новое сообщение: {text}")

            if admin(text, peer_id):
                continue

            handle(event)
