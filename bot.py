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
import logging
import re
import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===== НАСТРОЙКИ =====
TOKEN = "vk1.a.Fmog-6rNUAOTYVwC9-SJBo9dC5a87pMUET1xK_9Raxhk_l5V4Zqx1jCtWJXV7tZLappcJR6fIizfOv9X0OhMLnJbqjzej47aY5evfAj53IvfIgUo2w_vhBpjLGbgiBvaPZ3GrwFTdtR9D0TSGstCQM-L7aFf8_j6oqTxiRV7saahsFCInnvs7u53dtgLJB4lNI_apA5PsIpDqA3IWViAlA"  # Замените на актуальный токен
ADMIN_ID = 888230055

# URL для загрузки данных
DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

# Файлы для хранения данных
FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"
LOG_FILE = "logs.txt"

# ===== ИНИЦИАЛИЗАЦИЯ VK =====
vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkBotLongPoll(vk_session, 236843733)  
vk = vk_session.get_api()

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
user_state = {}
user_results = {}
user_index = {}

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
        self.number_key_wheels = None
        self.name_key_wheels = None
        self.photo_key_wheels = None

    def load_csv(self, url):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=30)
            response.encoding = "cp1251"
            csv_file = io.StringIO(response.text)
            reader = csv.DictReader(csv_file, delimiter=";")
            return list(reader), reader.fieldnames
        except Exception as e:
            logging.error(f"Ошибка загрузки CSV: {e}")
            return [], []

    def update(self):
        try:
            print("🔄 Обновление базы данных...")
            self.donors, _ = self.load_csv(DONORS_CSV)
            self.donors.reverse()
            
            self.parts, headers = self.load_csv(PARTS_CSV)
            self.wheels, headers2 = self.load_csv(WHEELS_CSV)
            
            # Определяем ключи для поиска
            for header in headers:
                header_lower = header.lower()
                if "артикул" in header_lower or "номер" in header_lower:
                    self.number_key = header
                if "наимен" in header_lower or "название" in header_lower:
                    self.name_key = header
                if "фото" in header_lower or "image" in header_lower:
                    self.photo_key = header
        except Exception as e:
            logging.error(f"Ошибка обновления кэша: {e}")

# Создаем экземпляр кэша
cache = DataCache()
cache.update()

# Автообновление в отдельном потоке
def auto_update():
    while True:
        try:
            cache.update()
            time.sleep(300)  # Обновление каждые 5 минут
        except Exception as e:
            logging.error(f"Ошибка автообновления: {e}")

threading.Thread(target=auto_update, daemon=True).start()

# ===== ОБРАБОТКА CALLBACK =====
def handle_callback(event):
    try:
        logging.info(f"Получен callback от пользователя {event.obj.peer_id}")  # Добавляем логирование
        
        payload = event.obj.payload
        peer_id = event.obj.peer_id
        
        if isinstance(payload, str):
            payload = json.loads(payload)
            
        cmd = payload.get('cmd')
        
        # Обработка команд с логированием
        if cmd == 'parts':
            logging.info(f"Пользователь {peer_id} выбрал команду parts")
            user_state[peer_id] = "parts"
            send(peer_id, "Введите номер детали или код:")
            
        elif cmd == 'wheels':
            logging.info(f"Пользователь {peer_id} выбрал команду wheels")
            user_state[peer_id] = "wheels"
            send(peer_id, "Введите бренд диска:")
            
        elif cmd == 'donors':
            logging.info(f"Пользователь {peer_id} выбрал команду donors")
            user_state[peer_id] = "donors"
            user_results[peer_id] = cache.donors[:20]
            user_index[peer_id] = 0
            send_donor_card(peer_id, 0)
            
        elif cmd == 'favorites':
            logging.info(f"Пользователь {peer_id} выбрал команду favorites")
            send(peer_id, "Ваши избранные товары")
            
        else:
            logging.warning(f"Неизвестная команда: {cmd}")
            send(peer_id, "Неизвестная команда")
            
    except Exception as e:
        logging.error(f"Ошибка обработки callback: {e}")
        send(peer_id, "Произошла ошибка при обработке запроса")


# Добавим дополнительную проверку в handle()
def handle(event):
    try:
        logging.info(f"Новое событие: {event.type}")
        
        if event.type == VkBotEventType.MESSAGE_NEW:
            handle_message(event)
        elif event.type == VkBotEventType.MESSAGE_EVENT:  # Проверяем именно этот тип
            handle_callback(event)
        else:
            logging.warning(f"Неизвестный тип события: {event.type}")
            
    except Exception as e:
        logging.error(f"Ошибка обработки события: {e}")

# Улучшим функцию отправки сообщений
def send(peer_id, text, keyboard=None):
    try:
        logging.info(f"Отправка сообщения пользователю {peer_id}")
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=0,
            keyboard=keyboard if keyboard else get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")
        send(peer_id, "Произошла ошибка при отправке сообщения")

# Добавим проверку прав доступа
def check_access(peer_id):
    # Здесь можно добавить логику проверки прав пользователя
    return True

# Модифицируем handle_message
def handle_message(event):
    try:
        msg = event.obj.message
        peer_id = msg['peer_id']
        text = msg.get('text', '').strip().lower()

        # Проверка на пустое сообщение
        if not text:
            send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
            return

        # Обработка команды /start
        if text in ["/start", "начать"]:
            send(peer_id, "Привет! 👋 Выберите команду:", keyboard=get_main_keyboard())
            return

        # Обработка состояний
        if peer_id in user_state:
            current_state = user_state[peer_id]
            
            if current_state == "parts":
                track(peer_id, "search")
                search_results = find_part(text)
                user_results[peer_id] = search_results
                user_index[peer_id] = 0
                
                if search_results:
                    send_part_card(peer_id, 0)
                else:
                    send(peer_id, "❌ Ничего не найдено")
                return

            elif current_state == "wheels":
                track(peer_id, "search")
                search_results = find_wheels(text)
                user_results[peer_id] = search_results
                user_index[peer_id] = 0
                
                if search_results:
                    send_wheel_card(peer_id, 0)
                else:
                    send(peer_id, "❌ Ничего не найдено")
                return

            elif current_state == "donors":
                # Если в состоянии доноры, обрабатываем поиск по донорам
                search_results = find_donor(text)  # Добавьте функцию поиска доноров
                user_results[peer_id] = search_results
                user_index[peer_id] = 0
                
                if search_results:
                    send_donor_card(peer_id, 0)
                else:
                    send(peer_id, "❌ Ничего не найдено")
                return

        # Если сообщение не в состоянии, показываем главную клавиатуру
        send(peer_id, "Выберите команду:", keyboard=get_main_keyboard())

    except Exception as e:
        logging.error(f"Ошибка обработки сообщения: {e}")
        send(peer_id, "Произошла ошибка при обработке сообщения. Попробуйте еще раз.")

# Добавьте функцию поиска доноров
def find_donor(query):
    try:
        query = normalize(fix_a(query))
        results = []
        for donor in cache.donors:
            if query in donor.get('Марка', '').lower() or \
               query in donor.get('Модель', '').lower() or \
               query in donor.get('Год', '').lower():
                results.append(donor)
            if len(results) >= 20:
                break
        return results
    except Exception as e:
        logging.error(f"Ошибка поиска донора: {e}")
        return []

# ===== КАРТОЧКИ ТОВАРОВ (продолжение) =====
def send_donor_card(peer_id, index):
    try:
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
    except Exception as e:
        logging.error(f"Ошибка отправки карточки донора: {e}")

# ===== ОТПРАВКА СООБЩЕНИЙ (дополнения) =====
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

# ===== КНОПКИ И НАВИГАЦИЯ =====
def get_main_keyboard():
    return json.dumps({
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "callback", "label": "Запчасти", "payload": {"cmd": "parts"}}, "color": "primary"}
            ],
            [
                {"action": {"type": "callback", "label": "Диски", "payload": {"cmd": "wheels"}}, "color": "primary"}
            ],
            [
                {"action": {"type": "callback", "label": "Доноры", "payload": {"cmd": "donors"}}, "color": "positive"}
            ],
            [
                {"action": {"type": "callback", "label": "Избранное", "payload": {"cmd": "favorites"}}, "color": "negative"}
            ]
        ],
        "inline": True
    })

# Функция навигации между карточками
def navigate(peer_id, direction):
    try:
        if user_state.get(peer_id) in ["parts", "wheels", "donors"]:
            if direction == "next":
                user_index[peer_id] = min(user_index[peer_id] + 1, len(user_results[peer_id]) - 1)
            elif direction == "prev":
                user_index[peer_id] = max(user_index[peer_id] - 1, 0)

            if user_state[peer_id] == "parts":
                send_part_card(peer_id, user_index[peer_id])
            elif user_state[peer_id] == "wheels":
                send_wheel_card(peer_id, user_index[peer_id])
            elif user_state[peer_id] == "donors":
                send_donor_card(peer_id, user_index[peer_id])
    except Exception as e:
        logging.error(f"Ошибка навигации: {e}")

# ===== ГЛАВНЫЙ ЦИКЛ =====
def run_bot():
    print("🔥 VK BOT ULTRA ЗАПУЩЕН")
    try:
        for event in longpoll.listen():
            handle(event)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")

# ===== СТАРТ БОТА =====
if __name__ == "__main__":
    try:
        # Инициализация кэша уже выполнена выше
        
        # Запускаем бота
        run_bot()
        
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        exit(1)

# ===== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ =====
def normalize(text):
    return str(text).lower().replace(" ", "").replace("-", "")

def log_search(user_id, query, mode):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp} | {user_id} | {mode} | {query}\n")
    except Exception as e:
        logging.error(f"Ошибка логирования: {e}")

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

# ===== ПОИСК ТОВАРОВ =====
def find_part(query):
    try:
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
    except Exception as e:
        logging.error(f"Ошибка поиска детали: {e}")
        return []

def find_wheels(query):
    try:
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
    except Exception as e:
        logging.error(f"Ошибка поиска дисков: {e}")
        return []

# ===== КАРТОЧКИ ТОВАРОВ =====
def send_part_card(peer_id, index):
    try:
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
    except Exception as e:
        logging.error(f"Ошибка отправки карточки детали: {e}")
def send_wheel_card(peer_id, index):
    try:
        track(peer_id, "views")
        results = user_results.get(peer_id, [])
        
        if not results or index >= len(results):
            send(peer_id, "Нет доступных записей")
            return
        
        part = results[index]
        
        # Формируем основную информацию
        text = f"""🛞 {part.get('Производитель диска', '')} {part.get('Модель диска', '')}
R{part.get('Диаметр диска', '')}
Ширина: {part.get('Ширина диска', '')}
Вылет: {part.get('Вылет диска', '')}
Цена: {part.get('Цена', '')} ₽
({index+1}/{len(results)})"""
        
        # Добавляем дополнительную информацию, если она есть
        additional_info = []
        
        mounting = part.get('Крепеж', '')
        if mounting:
            additional_info.append(f"Крепеж: {mounting}")
            
        pcd = part.get('PCD', '')
        if pcd:
            additional_info.append(f"PCD: {pcd}")
            
        h_size = part.get('H-размер', '')
        if h_size:
            additional_info.append(f"H-размер: {h_size}")
            
        if additional_info:
            text += "\n" + "\n".join(additional_info)
            
        # Отправляем сообщение
        send(peer_id, text)
        
    except Exception as e:
        logging.error(f"Ошибка отправки карточки диска: {e}")
        send(peer_id, "Произошла ошибка при отправке карточки диска")

# Допишем функцию отправки сообщений с проверкой ошибок
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
        send(peer_id, "Произошла ошибка при отправке сообщения")

# Добавим проверку наличия всех необходимых полей в данных
def check_data_integrity():
    try:
        # Проверяем наличие обязательных полей в данных
        if not cache.parts:
            logging.error("База данных запчастей пуста")
        
        if not cache.wheels:
            logging.error("База данных дисков пуста")
        
        if not cache.donors:
            logging.error("База данных доноров пуста")
            
        # Проверяем наличие ключей для поиска
        if not cache.number_key:
            logging.error("Не определен ключ номера детали")
            
        if not cache.name_key:
            logging.error("Не определен ключ названия детали")
            
    except Exception as e:
        logging.error(f"Ошибка проверки целостности данных: {e}")

# ===== СТАРТ БОТА =====
if __name__ == "__main__":
    try:
        # Загружаем базу данных
        cache.update()
        
        # Проверяем целостность данных
        check_data_integrity()
        
        # Запускаем автообновление
        threading.Thread(target=auto_update, daemon=True).start()
        
        # Запускаем основной цикл бота
        run_bot()
        
    except Exception as e:
        logging.error(f"Критическая ошибка при запуске: {e}")
        exit(1)

# Дополнительные проверки:
# 1. Убедимся, что все функции определены до их использования
# 2. Проверим права доступа к файлам
# 3. Проверим подключение к интернету для загрузки CSV

# Рекомендации по тестированию:
# 1. Проверьте права доступа к файлам favorites.json, stats.json, logs.txt
# 2. Убедитесь, что есть доступ к URL для загрузки CSV
# 3. Проверьте актуальность версии Python (должна быть 3.6+)
# 4. Установите необходимые библиотеки:
# pip install vk_api requests

# Отладка:
# 1. Проверьте логи на наличие ошибок:
# tail -f logs.txt
# 2. Проверьте права доступа:
# chmod 644 favorites.json stats.json logs.txt
# 3. Проверьте существование директории для логов

