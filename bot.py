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

# ===== ИНИЦИАЛИЗАЦИЯ VK =====
vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkBotLongPoll(vk_session, 236843733)  
vk = vk_session.get_api()

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
user_state = {}
user_results = {}
user_index = {}

# ===== КНОПКИ =====
def get_main_keyboard():
    return json.dumps({
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "callback", "label": "🚗 Запчасти", "payload": {"cmd": "parts"}}, "color": "primary"}
            ],
            [
                {"action": {"type": "callback", "label": "🛞 Диски", "payload": {"cmd": "wheels"}}, "color": "primary"}
            ],
            [
                {"action": {"type": "callback", "label": "🚘 Доноры", "payload": {"cmd": "donors"}}, "color": "positive"}
            ],
            [
                {"action": {"type": "callback", "label": "❤️ Избранное", "payload": {"cmd": "favorites"}}, "color": "negative"}
            ]
        ],
        "inline": True
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

# ===== ОБРАБОТКА СОБЫТИЙ =====
def handle(event):
    try:
        if event.type == VkBotEventType.MESSAGE_NEW:
            handle_message(event)
        elif event.type == VkBotEventType.MESSAGE_EVENT:
            handle_callback(event)
    except Exception as e:
        logging.error(f"Ошибка обработки события: {e}")

# ===== ОБРАБОТКА СООБЩЕНИЙ =====
def handle_message(event):
    try:
        msg = event.obj.message
        peer_id = msg['peer_id']
        text = msg.get('text', '').strip().lower()

        if text in ["/start", "начать"]:
            send(peer_id, "Привет! Выберите команду:", keyboard=get_main_keyboard())
            return

        if peer_id in user_state:
            if user_state[peer_id] == "parts":
                user_results[peer_id] = find_part(text)
                user_index[peer_id] = 0
                if user_results[peer_id]:
                    send_part_card(peer_id, 0)
                else:
                    send(peer_id, "❌ Ничего не найдено")
                return

            if user_state[peer_id] == "wheels":
                user_results[peer_id] = find_wheels(text)
                user_index[peer_id] = 0
                if user_results[peer_id]:
                    send_wheel_card(peer_id, 0)
                else:
                    send(peer_id, "❌ Ничего не найдено")
                return
    except Exception as e:
        logging.error(f"Ошибка обработки сообщения: {e}")

# ===== ОБРАБОТКА CALLBACK =====
# ===== ОБРАБОТКА CALLBACK =====
def handle_callback(event):
    try:
        # Получаем данные из callback
        payload = event.obj.payload
        peer_id = event.obj.peer_id
        
        # Проверяем, является ли payload строкой и парсим JSON
        if isinstance(payload, str):
            payload = json.loads(payload)
            
        # Получаем команду из payload
        cmd = payload.get('cmd')
        
        # Обработка различных команд
        if cmd == 'parts':
            user_state[peer_id] = "parts"
            send(peer_id, "Введите номер детали или код:")
            return
            
        elif cmd == 'wheels':
            user_state[peer_id] = "wheels"
            send(peer_id, "Введите бренд диска:")
            return
            
        elif cmd == 'donors':
            user_state[peer_id] = "donors"
            user_results[peer_id] = cache.donors[:20]
            user_index[peer_id] = 0
            send_donor_card(peer_id, 0)
            return
            
        elif cmd == 'favorites':
            send(peer_id, "Ваши избранные товары")
            return
            
        else:
            send(peer_id, "Неизвестная команда")
            
    except Exception as e:
        logging.error(f"Ошибка обработки callback: {e}")
        send(peer_id, "Произошла ошибка при обработке запроса")

# Добавим дополнительную проверку в handle()
def handle(event):
    try:
        if event.type == VkBotEventType.MESSAGE_NEW:
            handle_message(event)
        elif event.type == VkBotEventType.MESSAGE_EVENT:
            handle_callback(event)
        else:
            logging.warning(f"Неизвестный тип события: {event.type}")
            
    except Exception as e:
        logging.error(f"Ошибка обработки события: {e}")

# Улучшим функцию отправки сообщений
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
                {"action": {"type": "callback", "label": "🚗 Запчасти", "payload": {"cmd": "parts"}}, "color": "primary"}
            ],
            [
                {"action": {"type": "callback", "label": "🛞 Диски", "payload": {"cmd": "wheels"}}, "color": "primary"}
            ],
            [
                {"action": {"type": "callback", "label": "🚘 Доноры", "payload": {"cmd": "donors"}}, "color": "positive"}
            ],
            [
                {"action": {"type": "callback", "label": "❤️ Избранное", "payload": {"cmd": "favorites"}}, "color": "negative"}
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
        # Инициализация кэша
        cache = DataCache()  # Теперь это должно работать
        cache.update()
        
        # Запускаем автообновление в отдельном потоке
        threading.Thread(target=auto_update, daemon=True).start()
        
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

