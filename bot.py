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
GROUP_ID = 236843733
ADMIN_ID = 888230055

DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"

# ===== ИНИЦИАЛИЗАЦИЯ ФАЙЛОВ =====
def init_files():
    try:
        for file in [FAV_FILE, STATS_FILE]:
            if not os.path.exists(file):
                with open(file, 'w', encoding='utf-8') as f:
                    f.write('{}')
            if not os.access(file, os.W_OK):
                raise PermissionError(f"Нет прав записи в файл {file}")
    except Exception as e:
        logging.error(f"Ошибка при инициализации файлов: {e}")
        exit(1)

# Инициализируем файлы
init_files()

# ===== ИНИЦИАЛИЗАЦИЯ VK API =====
def init_vk_api():
    try:
        vk_session = vk_api.VkApi(token=TOKEN)
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
        vk = vk_session.get_api()
        print("Подключение к VK API успешно")
        return vk_session, longpoll, vk
    except Exception as e:
        logging.error(f"Ошибка инициализации VK API: {e}")
        raise

# Инициализируем VK API
try:
    vk_session, longpoll, vk = init_vk_api()
except Exception as e:
    logging.error(f"Не удалось инициализировать VK API: {e}")
    exit(1)

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
# ===== КЭШ =====
class DataCache:
    def __init__(self):
        self.parts = []
        self.wheels = []
        self.donors = []

    def load_csv(self, url):
        try:
            r = requests.get(url, timeout=15)
            r.encoding = "cp1251"
            return list(csv.DictReader(io.StringIO(r.text), delimiter=";"))
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка загрузки CSV с {url}: {e}")
            return []
        except Exception as e:
            logging.error(f"Неизвестная ошибка при загрузке CSV: {e}")
            return []

    def update(self):
        try:
            print("🔄 Обновление базы...")
            self.parts = self.load_csv(PARTS_CSV)
            self.wheels = self.load_csv(WHEELS_CSV)
            self.donors = self.load_csv(DONORS_CSV)
            print("База данных успешно обновлена")
        except Exception as e:
            logging.error(f"Критическая ошибка при обновлении базы: {e}")

    def search_parts(self, query):
        """Поиск деталей по названию или артикулу"""
        query = query.lower()
        results = []
        for part in self.parts:
            if query in part.get('Название', '').lower() or \
               query in part.get('Артикул', '').lower():
                results.append(part)
        return results

    def search_wheels(self, query):
        """Поиск дисков по производителю"""
        query = query.lower()
        results = []
        for wheel in self.wheels:
            if query in wheel.get('Производитель диска', '').lower():
                results.append(wheel)
        return results

    def search_donors(self, query):
        """Поиск доноров по марке или модели"""
        query = query.lower()
        results = []
        for donor in self.donors:
            if query in donor.get('Марка', '').lower() or \
               query in donor.get('Модель', '').lower():
                results.append(donor)
        return results

    def get_part_details(self, part_id):
        """Получение детальной информации о детали"""
        for part in self.parts:
            if part.get('ID') == part_id:
                return part
        return None

# Создаем экземпляр кэша
cache = DataCache()

# Первое обновление данных
try:
    cache.update()
except Exception as e:
    logging.error(f"Ошибка при первом обновлении данных: {e}")

# Автообновление в отдельном потоке
def auto_update():
    while True:
        try:
            cache.update()
        except Exception as e:
            logging.error(f"Ошибка автообновления: {e}")
        time.sleep(300)  # Обновляем каждые 5 минут

# Запускаем поток автообновления
threading.Thread(target=auto_update, daemon=True).start()

# Добавляем методы для работы с результатами поиска
def show_part_info(peer_id, part):
    message = f"Информация о детали:\n"
    message += f"Название: {part.get('Название', 'Не указано')}\n"
    message += f"Артикул: {part.get('Артикул', 'Не указан')}\n"
    message += f"Цена: {part.get('Цена', 'Не указана')}\n"
    message += f"Ссылка: {part.get('Ссылка', 'Нет ссылки')}"
    send(peer_id, message)
def show_donor_info(peer_id, donor):
    try:
        message = f"🚘 Информация о доноре:\n"
        message += f"Марка: {donor.get('Марка', 'Не указана')}\n"
        message += f"Модель: {donor.get('Модель', 'Не указана')}\n"
        message += f"Год выпуска: {donor.get('Год', 'Не указан')}\n"
        message += f"Цена: {donor.get('Цена', 'Не указана')}\n"
        message += f"Пробег: {donor.get('Пробег', 'Не указан')}\n"
        message += f"Город: {donor.get('Город', 'Не указан')}\n"
        message += f"Ссылка: {donor.get('Ссылка', 'Нет ссылки')}"
        
        send(peer_id, message)
    except Exception as e:
        logging.error(f"Ошибка при отображении информации о доноре: {e}")
        send(peer_id, "Произошла ошибка при получении информации о доноре")

# Функция для показа информации о детали
def show_part_info(peer_id, part):
    try:
        message = f"🚗 Информация о детали:\n"
        message += f"Название: {part.get('Название', 'Не указано')}\n"
        message += f"Артикул: {part.get('Артикул', 'Не указан')}\n"
        message += f"Цена: {part.get('Цена', 'Не указана')}\n"
        message += f"Наличие: {part.get('Наличие', 'Не указано')}\n"
        message += f"Ссылка: {part.get('Ссылка', 'Нет ссылки')}"
        
        send(peer_id, message)
    except Exception as e:
        logging.error(f"Ошибка при отображении информации о детали: {e}")
        send(peer_id, "Произошла ошибка при получении информации о детали")

# Функция для показа информации о диске
def show_wheel_info(peer_id, wheel):
    try:
        message = f"🛞 Информация о диске:\n"
        message += f"Производитель: {wheel.get('Производитель диска', 'Не указан')}\n"
        message += f"Размер: {wheel.get('Размер', 'Не указан')}\n"
        message += f"Цена: {wheel.get('Цена', 'Не указана')}\n"
        message += f"Ссылка: {wheel.get('Ссылка', 'Нет ссылки')}"
        
        send(peer_id, message)
    except Exception as e:
        logging.error(f"Ошибка при отображении информации о диске: {e}")
        send(peer_id, "Произошла ошибка при получении информации о диске")

# Обновляем функцию обработки сообщений
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

    # Обработка поиска доноров
    if user_state.get(peer_id) == "donors":
        track(peer_id, "search_donors")
        user_results[peer_id] = cache.search_donors(text)
        user_index[peer_id] = 0

        if user_results[peer_id]:
            show_donor_info(peer_id, user_results[peer_id][0])
        else:
            send(peer_id, "❌ Донор не найден")
        return
    # Обработка навигации для доноров
    elif text_lower in ["➡️", "следующий"]:
        if user_state.get(peer_id) == "donors":
            try:
                # Получаем текущий индекс
                current_index = user_index.get(peer_id, 0)
                # Получаем результаты поиска
                results = user_results.get(peer_id, [])
                
                # Проверяем, есть ли следующие элементы
                if current_index + 1 < len(results):
                    # Увеличиваем индекс
                    user_index[peer_id] = current_index + 1
                    # Показываем следующую запись
                    show_donor_info(peer_id, results[user_index[peer_id]])
                else:
                    send(peer_id, "🚫 Это последний результат")
                    
            except Exception as e:
                logging.error(f"Ошибка при переходе к следующему донору: {e}")
                send(peer_id, "Произошла ошибка при переходе к следующему результату")
    elif text_lower in ["⬅️", "предыдущий"]:
        if user_state.get(peer_id) == "donors":
            try:
                # Получаем текущий индекс
                current_index = user_index.get(peer_id, 0)
                # Получаем результаты поиска
                results = user_results.get(peer_id, [])
                
                # Проверяем, есть ли предыдущие элементы
                if current_index > 0:
                    # Уменьшаем индекс
                    user_index[peer_id] = current_index - 1
                    # Показываем предыдущую запись
                    show_donor_info(peer_id, results[user_index[peer_id]])
                else:
                    send(peer_id, "🚫 Это первый результат")
                    
            except Exception as e:
                logging.error(f"Ошибка при переходе к предыдущему донору: {e}")
                send(peer_id, "Произошла ошибка при переходе к предыдущему результату")
    
    # Обработка поиска доноров
    elif user_state.get(peer_id) == "donors":
        try:
            track(peer_id, "search_donors")
            # Выполняем поиск
            user_results[peer_id] = cache.search_donors(text)
            user_index[peer_id] = 0
            
            if user_results[peer_id]:
                # Показываем первый результат
                show_donor_info(peer_id, user_results[peer_id][0])
            else:
                send(peer_id, "❌ Донор не найден")
                
        except Exception as e:
            logging.error(f"Ошибка при поиске донора: {e}")
            send(peer_id, "Произошла ошибка при поиске донора")
    
    # ===== ДОБАВЛЯЕМ ФУНКЦИИ ПОКАЗА ИНФОРМАЦИИ =====

def show_part(peer_id):
    try:
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])
        
        if index < len(results):
            part = results[index]
            message = f"🚗 Карточка детали:\n"
            message += f"Название: {part.get('Название', 'Не указано')}\n"
            message += f"Артикул: {part.get('Артикул', 'Не указан')}\n"
            message += f"Цена: {part.get('Цена', 'Не указана')}\n"
            message += f"Ссылка: {part.get('Ссылка', 'Нет ссылки')}"
            send(peer_id, message)
        else:
            send(peer_id, "Нет данных для отображения")
    except Exception as e:
        logging.error(f"Ошибка при показе детали: {e}")

def show_donor(peer_id):
    try:
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])
        
        if index < len(results):
            donor = results[index]
            message = f"🚘 Карточка донора:\n"
            message += f"Марка: {donor.get('Марка', 'Не указана')}\n"
            message += f"Модель: {donor.get('Модель', 'Не указана')}\n"
            message += f"Год: {donor.get('Год', 'Не указан')}\n"
            message += f"Цена: {donor.get('Цена', 'Не указана')}\n"
            message += f"Ссылка: {donor.get('Ссылка', 'Нет ссылки')}"
            send(peer_id, message)
        else:
            send(peer_id, "Нет данных для отображения")
    except Exception as e:
        logging.error(f"Ошибка при показе донора: {e}")

# ===== ДОБАВЛЯЕМ ПОИСК ПО КРИТЕРИЯМ =====

def find_part(query):
    query = query.lower()
    results = []
    for part in cache.parts:
        if query in part.get('Название', '').lower() or query in part.get('Артикул', '').lower():
            results.append(part)
    return results

def find_donor(query):
    query = query.lower()
    results = []
    for donor in cache.donors:
        if query in donor.get('Марка', '').lower() or query in donor.get('Модель', '').lower():
            results.append(donor)
    return results

# ===== ДОБАВЛЯЕМ ИЗБРАННОЕ =====

def add_to_favorites(peer_id, item):
    if peer_id not in favorites:
        favorites[peer_id] = []
    if item not in favorites[peer_id]:
        favorites[peer_id].append(item)
        save_json(FAV_FILE, favorites)
        send(peer_id, "Добавлено в избранное!")
    else:
        send(peer_id, "Уже в избранном!")

def show_favorites(peer_id):
    fav_items = favorites.get(peer_id, [])
    if fav_items:
        message = "❤️ Избранное:\n"
        for i, item in enumerate(fav_items, 1):
            message += f"{i}. {item.get('Название', 'Не указано')}\n"
        send(peer_id, message)
    else:
        send(peer_id, "Избранное пустое")

# ===== ОБНОВЛЯЕМ HANDLE() =====

def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()

    if not text:
        send(peer_id, "Я получил сообщение, но оно не текстовое 😅")
        return

    text_lower = text.lower()

    # Обработка команд
    if text_lower in ["/start", "начать"]:
        send(peer_id, "Привет! 👋 Выберите команду:", keyboard=get_main_keyboard())
        return

    # Обработка кнопки "Запчасти"
    if text_lower == "🚗 запчасти":
        user_state[peer_id] = "parts"
        send(peer_id, "Введите номер детали или код:")
        return

    # Обработка кнопки "Диски"
    elif text_lower == "🛞 диски":
        user_state[peer_id] = "wheels"
        send(peer_id, "Введите бренд диска:")
        return

    # Обработка кнопки "Доноры"
    elif text_lower == "🚘 доноры":
        user_state[peer_id] = "donors"
        send(peer_id, "Введите марку автомобиля:")
        return

    # Обработка кнопки "Избранное"
    elif text_lower == "❤️ избранное":
        show_favorites(peer_id)
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

    # Обработка поиска деталей
    if user_state.get(peer_id) == "parts":
        track(peer_id, "search")
        user_results[peer_id] = cache.search_parts(text)
        user_index[peer_id] = 0
        
        if user_results[peer_id]:
            show_part(peer_id)
        else:
            send(peer_id, "❌ Детали не найдены")

    # Обработка поиска дисков
    elif user_state.get(peer_id) == "wheels":
        results = cache.search_wheels(text)
        if results:
            send(peer_id, f"🛞 Найденные диски: {results[0].get('Производитель диска')}")
        else:
            send(peer_id, "❌ Диски не найдены")

    # Обработка поиска доноров
    elif user_state.get(peer_id) == "donors":
        results = cache.search_donors(text)
        if results:
            user_results[peer_id] = results
            user_index[peer_id] = 0
            show_donor(peer_id)
        else:
            send(peer_id, "❌ Доноры не найдены")

    # Если команда не распознана
    else:
        send(peer_id, "Неизвестная команда. Используйте кнопки меню или команду /start")

# Запуск бота
# ===== ГЛАВНЫЙ ЦИКЛ =====
def run_bot():
    print("🔥 VK BOT ULTRA ЗАПУЩЕН")
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                handle(event)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        time.sleep(5)  # пауза перед перезапуском
        run_bot()  # перезапуск бота

# Добавляем обработку ошибок при запуске
if __name__ == "__main__":
    try:
        # Инициализируем все компоненты
        init_files()
        load_json(FAV_FILE)
        load_json(STATS_FILE)
        
        # Запускаем основной цикл
        run_bot()
    except Exception as e:
        logging.error(f"Критическая ошибка при запуске бота: {e}")
        time.sleep(10)  # пауза перед повторной попыткой
        run_bot()  # повторный запуск

# Добавляем автоматический перезапуск при падении
def auto_restart():
    while True:
        try:
            run_bot()
        except Exception as e:
            logging.error(f"Бот упал. Перезапуск... {e}")
            time.sleep(10)

# Запускаем поток с автоперезапуском
threading.Thread(target=auto_restart, daemon=True).start()
