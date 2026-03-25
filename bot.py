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

# ===== ИНИЦИАЛИЗАЦИЯ VK =====
vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkBotLongPoll(vk_session, 236843733)  
vk = vk_session.get_api()

# ===== ГЛАВНЫЙ ЦИКЛ =====
def run_bot():
    print("🔥 VK BOT ULTRA ЗАПУЩЕН")
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                handle(event)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")

# ===== ОБРАБОТКА СООБЩЕНИЙ =====
def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()

    if not text:
        send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
        return

    text_lower = text.lower()

    # Обработка команд поиска
    if user_state.get(peer_id) == "parts":
        track(peer_id, "search")
        user_results[peer_id] = cache.find_part(text)  # Используем новый метод
        user_index[peer_id] = 0
        
        if user_results[peer_id]:
            show_part(peer_id)
        else:
            send(peer_id, "❌ Деталь не найдена")
            
    # Обработка команд
    if text_lower == "/start":
        send(peer_id, "Привет! 👋 Выберите команду:")
        return

    # Добавляем команду для запуска поиска
    elif text_lower == "поиск":
        send(peer_id, "Введите поисковый запрос:")
        user_state[peer_id] = "search"
        return

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

    # Добавляем метод поиска
    def search(self, query, category):
        if category == "parts":
            return [item for item in self.parts if query.lower() in item['Название'].lower()]
        elif category == "wheels":
            return [item for item in self.wheels if query.lower() in item['Производитель диска'].lower()]
        elif category == "donors":
            return [item for item in self.donors if query.lower() in item['Марка'].lower()]
        return []
# Автообновление в отдельном потоке
def auto_update():
    while True:
        cache.update()
        time.sleep(300)

threading.Thread(target=auto_update, daemon=True).start()

# Добавляем функцию поиска деталей
def find_part(self, query):
        query = query.lower()
        results = []
        for part in self.parts:
            if query in part['Название'].lower() or query in part['Артикул']:
                results.append(part)
        return results
    
# Добавляем функцию поиска дисков
def find_wheels(query):
    query = query.lower()
    results = []
    for wheel in cache.wheels:
        if query in wheel['Производитель диска'].lower():
            results.append(wheel)
    return results

# Функция отображения найденной детали
def show_part(peer_id):
    index = user_index.get(peer_id, 0)
    results = user_results.get(peer_id, [])
    
    if index < len(results):
        part = results[index]
        message = f"Карточка детали:\n"
        message += f"Название: {part.get('Название', 'Не указано')}\n"
        message += f"Артикул: {part.get('Артикул', 'Не указан')}\n"
        message += f"Цена: {part.get('Цена', 'Не указана')}\n"
        message += f"Ссылка: {part.get('Ссылка', 'Нет ссылки')}"
        send(peer_id, message)
    else:
        send(peer_id, "Нет данных для отображения")

# Функция отображения найденного донора
def show_donor(peer_id):
    index = user_index.get(peer_id, 0)
    results = user_results.get(peer_id, [])
    
    if index < len(results):
        donor = results[index]
        message = f"Донор №{index + 1}\n"
        message += f"Марка: {donor.get('Марка', 'Не указана')}\n"
        message += f"Модель: {donor.get('Модель', 'Не указана')}\n"
        message += f"Год: {donor.get('Год', 'Не указан')}\n"
        message += f"Цена: {donor.get('Цена', 'Не указана')}"
        send(peer_id, message)
    else:
        send(peer_id, "Нет данных для отображения")

# Не забудьте добавить эти функции в ваш основной файл


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
                {"action": {"type": "text", "label": "🚗 Запчасти"}, "color": "primary"},
                {"action": {"type": "text", "label": "🛞 Диски"}, "color": "primary"}
            ],
            [
                {"action": {"type": "text", "label": "🚘 Доноры"}, "color": "positive"},
                {"action": {"type": "text", "label": "❤️ Избранное"}, "color": "negative"}
            ]
        ]
    })

# ===== ОБРАБОТКА СООБЩЕНИЙ =====
def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()

    if not text:
        send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
        return

    text_lower = text.lower()

    # Обработка команд
    if text_lower == "/start":
        send(peer_id, "Привет! 👋 Выберите команду:")
        return

    # Обработка основных кнопок
    if text_lower == "🚗 запчасти":
        user_state[peer_id] = "parts"
        send(peer_id, "Введи номер детали или код:")
        return
    elif text_lower == "🛞 диски":
        user_state[peer_id] = "wheels"
        send(peer_id, "Введи бренд диска:")
        return

    # Обработка навигации
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

    # Обработка поиска
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
