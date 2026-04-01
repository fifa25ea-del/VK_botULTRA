import re
import os
import vk_api
import requests
import csv
import io
import threading
import time
import json
import logging
import random
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from urllib.parse import urlparse
from io import StringIO

# ===== НАСТРОЙКИ =====
TOKEN = "vk1.a.Ze-bIlYgJf9rdkgnhYmWc6U6Eg9DRgi0vLkokPQVV5fIMsfsLm8kVPpCBMD04qwimSsaZZS1R0e1qwndF1hj3ROCvebCapjcT7xVeOSAvAdIJ1rqPYevdcbGAIt6OxV9xreMd2w4JROXJnnKvE4XiDLIieNoPE6BMKERAjlIt8jpeKIughzD9VC7x9DdPjzgF_tvoZMRDGkbvIBycGNoeA"
GROUP_ID = 236843733
ADMIN_ID = 888230055

DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"
WATCHLIST_FILE = "watchlist.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===== ЗАГРУЗКА И СОХРАНЕНИЕ ДАННЫХ =====
def load_json(file, default=None):
    if default is None: default = {}
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки {file}: {e}")
    return default

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения {file}: {e}")

# Инициализация
favorites = load_json(FAV_FILE)
stats = load_json(STATS_FILE)
watchlist = load_json(WATCHLIST_FILE)

user_state = {}
user_results = {}
user_index = {}

# ===== КЛАСС КЭША ДАННЫХ =====
class DataCache:
    def __init__(self):
        self.parts = []
        self.wheels = []
        self.donors = []

    def load_csv(self, url):
        try:
            r = requests.get(url, timeout=20)
            r.encoding = "utf-8"  # Или cp1251 в зависимости от источника
            return list(csv.DictReader(io.StringIO(r.text), delimiter=";"))
        except Exception as e:
            logging.error(f"Ошибка загрузки CSV с {url}: {e}")
            return []

    def update(self):
        logging.info("🔄 Обновление базы данных...")
        self.parts = self.load_csv(PARTS_CSV)
        self.wheels = self.load_csv(WHEELS_CSV)
        self.donors = self.load_csv(DONORS_CSV)
        logging.info(f"База обновлена: Запчасти({len(self.parts)}), Диски({len(self.wheels)}), Доноры({len(self.donors)})")

cache = DataCache()

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def get_random_id():
    return random.randint(0, 2**31 - 1)

def safe_get(data_dict, field_name, default="Не указано"):
    value = data_dict.get(field_name, "")
    return str(value).strip() if value else default

def get_first_photo(photo_field):
    if not photo_field: return None
    urls = [url.strip() for url in str(photo_field).split(',')]
    for url in urls:
        if url.startswith('http') and '.' in url:
            return url
    return None

def normalize_query(text: str) -> str:
    text = text.upper()
    ru_to_en = {'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O', 'Р': 'P', 'С': 'C', 'Т': 'T', 'Х': 'X'}
    for ru, en in ru_to_en.items():
        text = text.replace(ru, en)
    return re.sub(r'[^A-Z0-9]', '', text)

# ===== VK API И КЛАВИАТУРЫ =====
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🚗 Запчасти", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🛞 Диски", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("👨‍💻 Менеджер", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("❤️ Избранное", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🚘 Доноры", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_nav_keyboard(current_idx, total_count, is_fav=False):
    keyboard = VkKeyboard(one_time=False)
    if is_fav:
        keyboard.add_button("🗑 Удалить", color=VkKeyboardColor.NEGATIVE)
    else:
        keyboard.add_button("❤️ В избранное", color=VkKeyboardColor.POSITIVE)
    
    keyboard.add_button("🏠 Меню", color=VkKeyboardColor.SECONDARY)
    
    if total_count > 1:
        keyboard.add_line()
        keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
        keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
    
    return keyboard.get_keyboard()

# ===== ОТПРАВКА СООБЩЕНИЙ =====
def send_msg(peer_id, message, keyboard=None, attachment=None):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=message,
            random_id=get_random_id(),
            keyboard=keyboard or get_main_keyboard(),
            attachment=attachment
        )
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")

def show_item(peer_id):
    state = user_state.get(peer_id)
    results = user_results.get(peer_id, [])
    idx = user_index.get(peer_id, 0)

    if not results:
        send_msg(peer_id, "Ничего не найдено.")
        return

    item = results[idx]
    is_fav = (state == "view_favorites")
    
    # Формирование текста в зависимости от типа
    if state in ["parts", "view_favorites"]:
        text = f"🚗 Деталь:\nНазвание: {safe_get(item, 'Наименование')}\nАртикул: {safe_get(item, 'Артикул')}\nЦена: {safe_get(item, 'Цена')}\nСостояние: {safe_get(item, 'Состояние')}"
    elif state == "wheels":
        text = f"🛞 Диски:\nМодель: {safe_get(item, 'Модель диска')}\nДиаметр: {safe_get(item, 'Диаметр диска')}\nЦена: {safe_get(item, 'Цена')}"
    else: # donors
        text = f"🚘 Донор:\nМарка: {safe_get(item, 'Марка')}\nМодель: {safe_get(item, 'Модель')}\nГод: {safe_get(item, 'Год')}\nЦвет: {safe_get(item, 'Цвет')}"

    text += f"\n\n📊 {idx + 1} из {len(results)}"
    
    # Работа с фото
    attachment = None
    photo_url = get_first_photo(item.get('Фото', ''))
    if photo_url:
        try:
            upload = vk_api.VkUpload(vk_session)
            img_data = requests.get(photo_url, timeout=10).content
            photo = upload.photo_messages(photos=io.BytesIO(img_data))[0]
            attachment = f"photo{photo['owner_id']}_{photo['id']}"
        except:
            logging.warning("Не удалось загрузить фото")

    send_msg(peer_id, text, keyboard=get_nav_keyboard(idx, len(results), is_fav), attachment=attachment)

# ===== ЛОГИКА ОБРАБОТКИ СООБЩЕНИЙ =====
def handle_event(event):
    if event.type != VkBotEventType.MESSAGE_NEW: return
    
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()
    text_low = text.lower()

    # Навигация и общие команды
    if text_low in ["🏠 главное меню", "🏠 меню", "начать"]:
        user_state[peer_id] = None
        send_msg(peer_id, "Выберите раздел:", keyboard=get_main_keyboard())
        return

    if text_low == "➡️ вперед":
        if peer_id in user_results:
            user_index[peer_id] = (user_index[peer_id] + 1) % len(user_results[peer_id])
            show_item(peer_id)
        return

    if text_low == "⬅️ назад":
        if peer_id in user_results:
            user_index[peer_id] = (user_index[peer_id] - 1) % len(user_results[peer_id])
            show_item(peer_id)
        return

    # Выбор разделов
    if text_low == "🚗 запчасти":
        user_state[peer_id] = "parts_input"
        send_msg(peer_id, "Введите номер или название запчасти:")
        return

    if text_low == "🛞 диски":
        user_state[peer_id] = "wheels_input"
        send_msg(peer_id, "Введите диаметр (например, 18):")
        return

    if text_low == "🚘 доноры":
        user_state[peer_id] = "donors"
        user_results[peer_id] = cache.donors[::-1][:20] # Последние 20
        user_index[peer_id] = 0
        show_item(peer_id)
        return

    if text_low == "❤️ избранное":
        favs = favorites.get(str(peer_id), [])
        if not favs:
            send_msg(peer_id, "У вас пока нет избранных товаров.")
        else:
            user_state[peer_id] = "view_favorites"
            user_results[peer_id] = favs
            user_index[peer_id] = 0
            show_item(peer_id)
        return

    # Добавление в избранное
    if text_low == "❤️ в избранное":
        if peer_id in user_results:
            item = user_results[peer_id][user_index[peer_id]]
            p_id_str = str(peer_id)
            if p_id_str not in favorites: favorites[p_id_str] = []
            if item not in favorites[p_id_str]:
                favorites[p_id_str].append(item)
                save_json(FAV_FILE, favorites)
                send_msg(peer_id, "✅ Добавлено в избранное!")
        return

    # Удаление из избранного
    if text_low == "🗑 удалить":
        p_id_str = str(peer_id)
        if p_id_str in favorites and peer_id in user_results:
            idx = user_index[peer_id]
            favorites[p_id_str].pop(idx)
            save_json(FAV_FILE, favorites)
            send_msg(peer_id, "🗑 Удалено из избранного.")
            # Возврат в меню или обновление списка
            if not favorites[p_id_str]:
                send_msg(peer_id, "Список пуст.", keyboard=get_main_keyboard())
            else:
                user_results[peer_id] = favorites[p_id_str]
                user_index[peer_id] = 0
                show_item(peer_id)
        return

    # Поиск (если состояние ожидает ввода)
    state = user_state.get(peer_id)
    if state == "parts_input":
        query = normalize_query(text)
        res = [p for p in cache.parts if query in normalize_query(p.get('Артикул', '')) or query in normalize_query(p.get('Номер', ''))]
        if res:
            user_state[peer_id] = "parts"
            user_results[peer_id] = res
            user_index[peer_id] = 0
            show_item(peer_id)
        else:
            send_msg(peer_id, f"Ничего не найдено по запросу {text}. Попробуйте другой номер.")
        return

    if state == "wheels_input":
        query = "".join(filter(str.isdigit, text))
        res = [w for w in cache.wheels if query in "".join(filter(str.isdigit, w.get('Диаметр диска', '')))]
        if res:
            user_state[peer_id] = "wheels"
            user_results[peer_id] = res
            user_index[peer_id] = 0
            show_item(peer_id)
        else:
            send_msg(peer_id, "Диски такого размера не найдены.")
        return

# ===== ФОНОВОЕ ОБНОВЛЕНИЕ =====
def auto_update():
    while True:
        try:
            cache.update()
        except Exception as e:
            logging.error(f"Ошибка автообновления: {e}")
        time.sleep(600) # Раз в 10 минут

# ===== ЗАПУСК =====
if __name__ == "__main__":
    cache.update()
    threading.Thread(target=auto_update, daemon=True).start()
    logging.info("🔥 БОТ ЗАПУЩЕН")
    for event in longpoll.listen():
        try:
            handle_event(event)
        except Exception as e:
            logging.error(f"Критическая ошибка: {e}")
            time.sleep(2)
