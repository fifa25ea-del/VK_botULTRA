# =========================
# VK BOT ULTRA (ИСПРАВЛЕННАЯ ВЕРСИЯ)
# =========================

import os
import vk_api
import requests
import csv
import io
import threading
import time
import json
import logging
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

# ===== НАСТРОЙКИ =====
TOKEN = "vk1.a.Ze-bIlYgJf9rdkgnhYmWc6U6Eg9DRgi0vLkokPQVV5fIMsfsLm8kVPpCBMD04qwimSsaZZS1R0e1qwndF1hj3ROCvebCapjcT7xVeOSAvAdIJ1rqPYevdcbGAIt6OxV9xreMd2w4JROXJnnKvE4XiDLIieNoPE6BMKERAjlIt8jpeKIughzD9VC7x9DdPjzgF_tvoZMRDGkbvIBycGNoeA"
GROUP_ID = 236843733 # ID вашей группы

DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ =====
user_state = {}    # Хранит текущее состояние пользователя (parts, wheels, donors)
user_results = {}  # Хранит результаты поиска для пользователя
user_index = {}    # Хранит текущий индекс в результатах поиска

# ===== ИНИЦИАЛИЗАЦИЯ ФАЙЛОВ =====
def init_files():
    try:
        for file in [FAV_FILE, STATS_FILE]:
            if not os.path.exists(file):
                with open(file, 'w', encoding='utf-8') as f:
                    f.write('{}')
    except Exception as e:
        logging.error(f"Ошибка файлов: {e}")
        exit(1)

# ===== ИНИЦИАЛИЗАЦИЯ VK API =====
def init_vk():
    try:
        vk_session = vk_api.VkApi(token=TOKEN)
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
        vk = vk_session.get_api()
        logging.info("Подключение к VK API успешно")
        return vk, longpoll
    except Exception as e:
        logging.error(f"Ошибка VK API: {e}")
        raise

# Инициализация
init_files()
try:
    vk, longpoll = init_vk()
except Exception as e:
    logging.error(f"Не удалось запустить бота: {e}")
    exit(1)

from vk_api.keyboard import VkKeyboard, VkKeyboardColor

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🚗 Запчасти", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🛞 Диски", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🚘 Доноры", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("❤️ Избранное", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def get_navigation_keyboard(index, total):
    keyboard = VkKeyboard(one_time=False)
    inv_char = '\u200B'
    
    # Назад
    if index > 0:
        keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY, payload={"action": "prev"})
    else:
        keyboard.add_button(inv_char, color=VkKeyboardColor.SECONDARY, payload={"action": "empty"})
    
    keyboard.add_line()
    
    # Вперёд
    if index < total - 1:
        keyboard.add_button("➡️ Вперёд", color=VkKeyboardColor.PRIMARY, payload={"action": "next"})
    else:
        keyboard.add_button(inv_char, color=VkKeyboardColor.SECONDARY, payload={"action": "empty"})
        
    keyboard.add_line()
    keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.SECONDARY, payload={"action": "home"})
    
    return keyboard.get_keyboard()

# ===== ОТПРАВКА СООБЩЕНИЙ =====
def send_safe(peer_id, text, keyboard=None):
    """Отправляет сообщение с обработкой ошибок"""
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=0,
            keyboard=keyboard if keyboard else get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")
        try:
            vk.messages.send(peer_id=peer_id, message="Ошибка. Попробуйте позже.", random_id=0)
        except:
            pass

# ===== ХРАНИЛИЩЕ (Избранное) =====
def load_json(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения: {e}")

favorites = load_json(FAV_FILE)

# ===== КЭШ ДАННЫХ =====
class DataCache:
    def __init__(self):
        self.parts = []
        self.wheels = []
        self.donors = []

    def load_csv(self, url):
        try:
            r = requests.get(url, timeout=20)
            r.encoding = "cp1251"
            return list(csv.DictReader(io.StringIO(r.text), delimiter=";"))
        except Exception as e:
            logging.error(f"Ошибка загрузки {url}: {e}")
            return []

    def update(self):
        try:
            logging.info("🔄 Обновление базы...")
            self.parts = self.load_csv(PARTS_CSV)
            self.wheels = self.load_csv(WHEELS_CSV)
            self.donors = self.load_csv(DONORS_CSV)
            logging.info("База обновлена")
        except Exception as e:
            logging.error(f"Критическая ошибка обновления: {e}")

# Создаем кэш и запускаем автообновление
cache = DataCache()
cache.update() # Первое обновление сразу

def auto_update():
    while True:
        cache.update()
        time.sleep(300) # 5 минут

threading.Thread(target=auto_update, daemon=True).start()

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def safe_get(data_dict, field_name, default="Не указано"):
    value = data_dict.get(field_name, "")
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default

def get_first_photo(photo_field):
    if not photo_field:
        return None
    for url in str(photo_field).split(','):
        url = url.strip()
        if url.startswith('http'):
            return url
    return None

def send_photo_with_caption(peer_id, photo_url, caption):
    """Отправляет фото с подписью в отдельном потоке"""
    def upload_and_send():
        try:
            response = requests.get(photo_url, timeout=10)
            response.raise_for_status()
            
            upload_url = vk.photos.getMessagesUploadServer()['upload_url']
            files = {'photo': ('image.jpg', response.content)}
            upload_data = requests.post(upload_url, files=files).json()
            
            photo_data = vk.photos.saveMessagesPhoto(**upload_data)[0]
            vk.messages.send(
                peer_id=peer_id,
                message=caption,
                attachment=f"photo{photo_data['owner_id']}_{photo_data['id']}",
                random_id=0,
                keyboard=get_main_keyboard() # Клавиатура для фото (можно убрать)
            )
            logging.info(f"Фото отправлено: {photo_url}")
        except Exception as e:
            logging.warning(f"Ошибка фото: {e}")

    thread = threading.Thread(target=upload_and_send)
    thread.daemon = True
    thread.start()

# ===== ЛОГИКА ПОИСКА И ОТОБРАЖЕНИЯ =====

def show_item(peer_id):
    """Универсальная функция для показа карточки (деталь/донор)"""
    state = user_state.get(peer_id)
    index = user_index.get(peer_id, 0)
    results = user_results.get(peer_id, [])
    
    if not results or index >= len(results):
        send_safe(peer_id, "Нет данных для отображения.")
        return

    item = results[index]
    
    if state == "parts":
        message = "🚗 Карточка детали:\n"
        message += f"Название: {safe_get(item, 'Наименование')}\n"
        message += f"Артикул: {safe_get(item, 'Артикул')}\n"
        
        price = safe_get(item, 'Цена')
        link = safe_get(item, 'Ссылка')
        
        if price != "Не указано":
            message += f"Цена: {price}\n"
            
        if link != "Не указано":
            message += f"Ссылка: {link}"
            
        photo_url = get_first_photo(item.get('Фото'))
        
    elif state == "donors":
        message = "🚘 Карточка донора:\n"
        message += f"Марка: {safe_get(item, 'Марка')}\n"
        message += f"Модель: {safe_get(item, 'Модель')}\n"
        
        year = safe_get(item, 'Год')
        price = safe_get(item, 'Цена')
        
        if year != "Не указано":
            message += f"Год: {year}\n"
            
        if price != "Не указано":
            message += f"Цена: {price}\n"
            
        link = safe_get(item, 'Ссылка')
        if link != "Не указано":
            message += f"Ссылка: {link}"
            
        photo_url = None # Фото доноров не обрабатываются в этом примере

    # Отправляем текст с навигацией
    keyboard = get_navigation_keyboard(index, len(results))
    send_safe(peer_id, message, keyboard=keyboard)
    
    # Отправляем фото в фоне (если есть и это деталь)
    if state == "parts" and photo_url:
         send_photo_with_caption(peer_id, photo_url, message)

def show_wheel_info(peer_id, wheel):
    """Показывает информацию о диске (без навигации)"""
    try:
        message = "🛞 Информация о диске:\n"
        message += f"Производитель: {safe_get(wheel, 'Производитель диска')}\n"
        message += f"Артикул: {safe_get(wheel, 'Артикул')}\n"
        message += f"Модель: {safe_get(wheel, 'Модель диска')}\n"
        
        size = safe_get(wheel, 'Размер')
        pcd = safe_get(wheel, 'PCD диска')
        
        if size != "Не указано":
             message += f"Размер: {size}\n"
             
        if pcd != "Не указано":
             message += f"PCD: {pcd}\n"
             
         message += f"Тип: {safe_get(wheel, 'Тип диска')}\n"
         message += f"Цена: {safe_get(wheel, 'Цена')}"
         
         send_safe(peer_id, message)
     except Exception as e:
         logging.error(f"Ошибка диска: {e}")
         send_safe(peer_id, "Ошибка при получении информации о диске.")

# ===== ИЗБРАННОЕ =====
def add_to_favorites(peer_id, item):
     if peer_id not in favorites:
         favorites[peer_id] = []
     if item not in favorites[peer_id]:
         favorites[peer_id].append(item)
         save_json(FAV_FILE, favorites)
         send_safe(peer_id, "Добавлено в избранное!")
     else:
         send_safe(peer_id, "Уже в избранном!")
         
def show_favorites(peer_id):
     fav_items = favorites.get(peer_id, [])
     if fav_items:
         message = "❤️ Избранное:\n"
         for i, item in enumerate(fav_items[:10], 1): # Покажем максимум 10 шт
             name = item.get('Наименование') or item.get('Марка') or str(item)
             message += f"{i}. {name}\n"
         send_safe(peer_id, message)
     else:
         send_safe(peer_id, "Избранное пустое.")

# ===== ГЛАВНЫЙ ОБРАБОТЧИК СОБЫТИЙ =====
def handle(event):
     msg = event.obj.message
     peer_id = msg['peer_id']
     
     # --- ОБРАБОТКА НАЖАТИЙ НА КНОПКИ ---
     payload_raw = msg.get('payload')
     action = None
     if payload_raw:
         try:
             action = json.loads(payload_raw).get('action')
         except Exception as e:
             logging.error(f"Плохой payload: {e}")
             
     text = msg.get('text', '').strip().lower()
     
     # Логика для кнопок (имеет приоритет над текстом)
     if action == "prev":
         user_index[peer_id] = max(0, user_index.get(peer_id, 0) - 1)
         show_item(peer_id)
         return
         
     if action == "next":
         total_results = len(user_results.get(peer_id, []))
         if total_results > 0:
             user_index[peer_id] = min(total_results - 1, user_index.get(peer_id, 0) + 1)
             show_item(peer_id)
         return
         
     if action == "home":
         user_state[peer_id] = None # Сброс состояния
         send_safe(peer_id, "🏠 Главное меню", keyboard=get_main_keyboard())
         return

     # --- ОБРАБОТКА ТЕКСТА ПОЛЬЗОВАТЕЛЯ ---
     current_state = user_state.get(peer_id)
     
     # Кнопки главного меню (работают по тексту или эмодзи)
     if text in ["🚗 запчасти", "запчасти"]:
         user_state[peer_id] = "parts"
         send_safe(peer_id, "🔎 Введите номер детали или артикул:", keyboard=get_main_keyboard())
         
     elif text in ["🛞 диски", "диски"]:
         user_state[peer_id] = "wheels"
         send_safe(peer_id, "🔎 Введите размер диска (например R18):", keyboard=get_main_keyboard())
         
     elif text in ["🚘 доноры", "доноры"]:
         user_state[peer_id] = "donors"
         send_safe(peer_id, "🔎 Введите марку или модель авто:", keyboard=get_main_keyboard())
         
     elif text in ["❤️ избранное", "избранное"]:
          show_favorites(peer_id)
          
     # Логика поиска по состоянию
     elif current_state == "parts":
          results = cache.search_parts(text)
          if results:
              user_results[peer_id] = results
              user_index[peer_id] = 0
              show_item(peer_id) # Покажет первую деталь с кнопками навигации
          else:
              send_safe(peer_id, "❌ Детали не найдены. Попробуйте другой запрос.")
              
     elif current_state == "wheels":
          results = cache.search_wheels(text)
          if results:
              show_wheel_info(peer_id, results[0]) # Для дисков показываем только первый результат без навигации
          else:
              send_safe(peer_id, "❌ Диски не найдены.")
              
     elif current_state == "donors":
          results = cache.search_donors(text)
          if results:
              user_results[peer_id] = results
              user_index[peer_id] = 0
              show_item(peer_id) # Покажет первого донора с кнопками навигации
          else:
              send_safe(peer_id, "❌ Доноры не найдены.")
              
# ===== ГЛАВНЫЙ ЦИКЛ БОТА =====
def run_bot():
     logging.basicConfig(level=logging.INFO,
                         format='%(asctime)s - %(levelname)s - %(message)s')
     print("🔥 VK BOT ULTRA ЗАПУЩЕН")
     try:
          for event in longpoll.listen():
               if event.type == VkBotEventType.MESSAGE_NEW:
                    handle(event)
     except KeyboardInterrupt:
          logging.info("Бот остановлен вручную.")
     except Exception as e:
          logging.critical(f"Критическая ошибка цикла: {e}")
          time.sleep(5)
          run_bot() # Перезапуск

if __name__ == "__main__":
     run_bot()
