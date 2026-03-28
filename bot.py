# =========================
# VK BOT ULTRA (ТОП ВЕРСИЯ)
# =========================
import random
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
from urllib.parse import urlparse
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def get_random_id():
    """Генерирует случайный ID для VK API (от 0 до 2^31−1)"""
    return random.randint(0, 2**31 - 1)


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===== НАСТРОЙКИ =====
TOKEN = "vk1.a.Ze-bIlYgJf9rdkgnhYmWc6U6Eg9DRgi0vLkokPQVV5fIMsfsLm8kVPpCBMD04qwimSsaZZS1R0e1qwndF1hj3ROCvebCapjcT7xVeOSAvAdIJ1rqPYevdcbGAIt6OxV9xreMd2w4JROXJnnKvE4XiDLIieNoPE6BMKERAjlIt8jpeKIughzD9VC7x9DdPjzgF_tvoZMRDGkbvIBycGNoeA"
GROUP_ID = 236843733
ADMIN_ID = 888230055

DONORS_CSV = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
PARTS_CSV = "https://baz-on.ru/export/c592/e61a0/stuttgart-drom.csv"
WHEELS_CSV = "https://baz-on.ru/export/c592/77023/drom-wheels.csv"

FAV_FILE = "favorites.json"
STATS_FILE = "stats.json"

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ =====
user_state = {}  # Хранит текущее состояние пользователя
user_results = {}  # Хранит результаты поиска для пользователя
user_index = {}  # Хранит текущий индекс в результатах поиска


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

from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)

    keyboard.add_button("🚗 Запчасти", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🛞 Диски", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🚘 Доноры", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("❤️ Избранное", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.NEGATIVE)
    
    return keyboard.get_keyboard()

def send_photo_with_caption(peer_id, photo_url, caption):
    """Отправляет фото с подписью. Возвращает True при успехе, False при ошибке."""
    try:
        if not photo_url or not isinstance(photo_url, str):
            logging.warning("Некорректный URL фото, пропуск отправки")
            return False

        # Загружаем изображение
        response = requests.get(photo_url, timeout=10, stream=True)
        response.raise_for_status()

        # Проверяем, что сервер вернул картинку
        content_type = response.headers.get('Content-Type', '')
        if 'image' not in content_type:
            logging.warning(f"URL не содержит изображение (Content-Type: {content_type}): {photo_url}")
            return False

        # Загрузка во временное хранилище VK
        upload_response = vk.photos.getMessagesUploadServer()
        upload_url = upload_response['upload_url']

        # Используем content из ответа
        files = {'photo': ('image.jpg', response.content)}
        upload_result = requests.post(upload_url, files=files, timeout=15)
        upload_data = upload_result.json()

        # Сохранение и отправка
        photo_data = vk.photos.saveMessagesPhoto(
            server=upload_data['server'],
            photo=upload_data['photo'],
            hash=upload_data['hash']
        )[0]

        vk.messages.send(
            peer_id=peer_id,
            message=caption,
            attachment=f"photo{photo_data['owner_id']}_{photo_data['id']}",
            random_id=get_random_id()  # Исправлено: используем функцию
        )
        logging.info(f"Фото успешно отправлено: {photo_url}")
        return True

    except requests.exceptions.Timeout:
        logging.warning(f"Таймаут при загрузке фото: {photo_url}")
        return False
    except requests.exceptions.RequestException as e:
        logging.warning(f"Ошибка сети при загрузке фото: {e}")
        return False
    except Exception as e:
        logging.error(f"Неизвестная ошибка при обработке фото: {e}")
        return False

def get_first_photo(photo_field):
    """Извлекает первую валидную ссылку на фото"""
    if not photo_field:
        return None

    # Убираем лишние пробелы и разбиваем по запятым
    photo_urls = [url.strip() for url in str(photo_field).split(',') if url.strip()]
    
    # Проверяем наличие http/https
    for url in photo_urls:
        if url.startswith('http://') or url.startswith('https://'):
            return url
            
    return None


# ===== ОТПРАВКА СООБЩЕНИЙ =====
def send_safe(peer_id, text, keyboard=None):
    """Безопасная отправка сообщения с обработкой ошибок"""
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=get_random_id(),  # Исправлено
            keyboard=keyboard if keyboard else get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Критическая ошибка отправки VK API для {peer_id}: {e}")
        # Попытка отправить простое сообщение без клавиатуры
        try:
            vk.messages.send(
                peer_id=peer_id,
                message="Произошла ошибка при отправке сообщения. Попробуйте позже.",
                random_id=get_random_id()  # Исправлено
            )
        except:
            pass
            
def send(peer_id, text, keyboard=None):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=get_random_id(),  # Исправлено
            keyboard=keyboard if keyboard else get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")
        
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
            if query in part.get('Номер', '').lower() or \
               query in part.get('Артикул', '').lower():
                results.append(part)
        return results

    def search_wheels(self, query):
        """
        Поиск дисков строго по полю 'Диаметр диска'.
        Игнорирует бренд и модель.
        Понимает форматы: 18, R18, r18.
        """
        # Нормализуем ввод: убираем пробелы, 'R', переводим в нижний регистр
        user_input = query.strip().lower().replace('r', '').replace(' ', '')
        
        # Если пользователь ввел не число, возвращаем пустой список (поиск только по размеру)
        if not user_input.isdigit():
            return []
    
        results = []
        target_diameter = user_input # Например, "18"
    
        for wheel in self.wheels:
            # Берем значение из поля 'Диаметр диска'
            db_diameter = safe_get(wheel, 'Диаметр диска', '').lower()
            
            # Извлекаем только цифры из базы (на случай, если там есть доп. символы)
            db_digits = ''.join(filter(str.isdigit, db_diameter))
    
            # Сравниваем только цифры
            if target_diameter == db_digits:
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
def safe_get(data_dict, field_name, default="Не указано"):
    """Безопасно получает значение из словаря, очищает от пробелов"""
    value = data_dict.get(field_name, "")
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default

def show_part_info(peer_id, part):
    logging.debug(f"Пытаемся получить фото по ссылке: {part.get('Фото', '')}")
    """Показывает подробную информацию о детали"""
    try:
        message = "🚗 Информация о детали:\n"
        message += f"Название: {safe_get(part, 'Наименование')}\n"
        message += f"Артикул: {safe_get(part, 'Артикул')}\n"
        message += f"Номер: {safe_get(part, 'Номер')}\n"
        message += f"Цена: {safe_get(part, 'Цена')}\n"
        comment = safe_get(part, 'Комментарий')
        if comment != "Не указано":
            message += f"Комментарий: {comment}"
        send(peer_id, message)
    except Exception as e:
        logging.error(f"Критическая ошибка в show_part_info: {e}")
        send(peer_id, "Произошла ошибка при получении информации о детали")

def show_donor_info(peer_id, donor):
    """Показывает подробную информацию о доноре"""
    try:
        message = "🚘 Информация о доноре:\n"
        message += f"Марка: {donor.get('Марка', 'Не указана')}\n"
        message += f"Модель: {donor.get('Модель', 'Не указана')}\n"
        message += f"Год выпуска: {donor.get('Год', 'Не указан')}\n"
        message += f"Цена: {donor.get('Цена', 'Не указана')}\n"
        message += f"Пробег: {donor.get('Пробег', 'Не указан')}"
        send(peer_id, message)
    except Exception as e:
        logging.error(f"Ошибка при отображении информации о доноре: {e}")
        send(peer_id, "Произошла ошибка при получении информации о доноре")

def show_wheel_info(peer_id, wheel):
    """Показывает подробную информацию о диске"""
    try:
        message = "🛞 Информация о диске:\n"
        message += f"Производитель: {wheel.get('Производитель диска', 'Не указан')}\n"
        message += f"Артикул: {wheel.get('Артикул', 'Не указан')}\n"
        message += f"Модель диска: {wheel.get('Модель диска', 'Не указана')}\n"
        message += f"Размер: {wheel.get('Размер', 'Не указан')}\n"
        message += f"PCD диска: {wheel.get('PCD диска', 'Не указан')}\n"
        message += f"Тип диска: {wheel.get('Тип диска', 'Не указан')}\n"
        message += f"Цена: {wheel.get('Цена', 'Не указана')}"
        send(peer_id, message)
    except Exception as e:
        logging.error(f"Ошибка при отображении информации о диске: {e}")
        send(peer_id, "Произошла ошибка при получении информации о диске")


def show_part(peer_id):
    """Показывает карточку детали с кнопками навигации"""
    try:
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])

        if not results:
            send_safe(peer_id, "Нет результатов поиска для отображения")
            return

        # --- НОВОЕ: РЕВЕРСИВНЫЙ ПОРЯДОК ---
        # Создаем перевернутую копию списка, чтобы не ломать исходные данные
        reversed_results = list(results)  # Создаем копию
        reversed_results.reverse()        # Переворачиваем (свежие будут первыми)

        # Обновляем индекс, так как список перевернулся
        # Если был индекс 0 (первый в старом списке), он станет последним в новом
        total_items = len(reversed_results)
        reversed_index = total_items - 1 - index

        # Проверяем границы нового индекса
        if reversed_index >= total_items or reversed_index < 0:
            send_safe(peer_id, "Нет данных для отображения")
            return

        part = reversed_results[reversed_index]

        # Формируем текст карточки (остальной код без изменений)
        message = "🚗 Карточка детали:\n"
        message += f"Название: {safe_get(part, 'Наименование')}\n"
        message += f"Артикул: {safe_get(part, 'Артикул')}\n"
        
        price = safe_get(part, 'Цена')
        if price != "Не указано":
            message += f"Цена: {price}\n"

        link = safe_get(part, 'Ссылка')
        if link != "Не указано" and link != "Нет ссылки":
            message += f"Ссылка: {link}"

        # Добавляем нумерацию с учетом перевернутого списка
        current_position = reversed_index + 1
        message += f"\n📊 {current_position} из {total_items}"

        # Создаём клавиатуру
        keyboard = VkKeyboard(one_time=False)

        if total_items > 1:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)

        keyboard.add_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY)

        if total_items > 1:
            keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
            
        keyboard_data = keyboard.get_keyboard()
        
        # Отправляем фото и текст (как мы исправили ранее)
        photo_url = get_first_photo(part.get('Фото', ''))
        
        if photo_url:
            try:
                # Загрузка фото и отправка ОДНИМ сообщением
                response = requests.get(photo_url, timeout=10)
                response.raise_for_status()
                
                upload_url = vk.photos.getMessagesUploadServer()['upload_url']
                files = {'photo': ('image.jpg', response.content)}
                upload_data = requests.post(upload_url, files=files, timeout=15).json()

                photo_data = vk.photos.saveMessagesPhoto(
                    server=upload_data['server'],
                    photo=upload_data['photo'],
                    hash=upload_data['hash']
                )[0]
                
                attachment = f"photo{photo_data['owner_id']}_{photo_data['id']}"
                
                vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    attachment=attachment,
                    keyboard=keyboard_data,
                    random_id=get_random_id()
                )
            except Exception as e:
                logging.warning(f"Ошибка отправки фото: {e}. Отправляем только текст.")
                send_safe(peer_id, message, keyboard=keyboard_data)
        else:
            send_safe(peer_id, message, keyboard=keyboard_data)

    except Exception as e:
        logging.critical(f"Ошибка в show_part для {peer_id}: {e}")
        send_safe(peer_id, "Произошла ошибка при отображении детали.")
        
def show_wheel(peer_id):
    """Показывает результаты поиска: галерея фото из разных карточек, затем первая карточка."""
    try:
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])

        if not results:
            send_safe(peer_id, "Нет результатов поиска для отображения")
            return

        # Реверсивный порядок (свежие объявления первыми)
        reversed_results = list(results)
        reversed_results.reverse()
        user_results[peer_id] = reversed_results # Сохраняем новый порядок для навигации
        
        total_items = len(reversed_results)
        if total_items == 0:
            send_safe(peer_id, "Ничего не найдено.")
            return

        # --- НОВЫЙ БЛОК: ОТПРАВКА ГАЛЕРЕИ ФОТО (каждое фото - отдельным сообщением) ---
        # Собираем первые валидные фото из первых 8 карточек
        photos_to_send = []
        for wheel in reversed_results[:8]:
            photos_field = str(wheel.get('Фото', ''))
            photo_urls = [url.strip() for url in photos_field.split(',') if url.strip()]
            
            for url in photo_urls:
                if url.startswith('http'):
                    photos_to_send.append(url)
                    break # Берем только одно фото с карточки
            
            if len(photos_to_send) >= 8:
                break

        # Функция для отправки одного фото (вложением)
        def send_single_photo(url):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                upload_url = vk.photos.getMessagesUploadServer()['upload_url']
                files = {'photo': ('image.jpg', response.content)}
                upload_data = requests.post(upload_url, files=files, timeout=15).json()

                photo_data = vk.photos.saveMessagesPhoto(
                    server=upload_data['server'],
                    photo=upload_data['photo'],
                    hash=upload_data['hash']
                )[0]

                vk.messages.send(
                    peer_id=peer_id,
                    attachment=f"photo{photo_data['owner_id']}_{photo_data['id']}",
                    random_id=get_random_id()
                )
            except Exception as e:
                logging.warning(f"Не удалось отправить фото {url}: {e}")

        # Отправляем галерею (в том же потоке, чтобы фото пришли до текста)
        for photo_url in photos_to_send:
            send_single_photo(photo_url)


        # --- СТАРЫЙ БЛОК: ОТПРАВКА КАРТОЧКИ С КНОПКАМИ ---
        wheel = reversed_results[index]

        message = "🛞 Карточка диска:\n"
        message += f"Производитель: {safe_get(wheel, 'Производитель диска')}\n"
        message += f"Артикул: {safe_get(wheel, 'Артикул')}\n"
        message += f"Модель: {safe_get(wheel, 'Модель диска')}\n"
        message += f"Размер: {safe_get(wheel, 'Размер')}\n"
        
        price = safe_get(wheel, 'Цена')
        if price != "Не указано":
            message += f"Цена: {price}\n"

        link = safe_get(wheel, 'Ссылка')
        if link != "Не указано" and link != "Нет ссылки":
            message += f"Ссылка: {link}"

        current_position = index + 1
        message += f"\n📊 {current_position} из {total_items}"

        keyboard = VkKeyboard(one_time=False)

        if total_items > 1:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)

        keyboard.add_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY)

        if total_items > 1:
            keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
            
        send_safe(peer_id, message, keyboard=keyboard.get_keyboard())

    except Exception as e:
        logging.critical(f"Ошибка в show_wheel для {peer_id}: {e}")
        send_safe(peer_id, "Произошла критическая ошибка при отображении дисков.")

def show_donor(peer_id):
    """Показывает карточку донора из результатов поиска"""
    try:
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])

        if index < len(results):
            donor = results[index]
            message = "🚘 Карточка донора:\n"
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
        send(peer_id, "Произошла ошибка при отображении донора")

# ===== ДОБАВЛЯЕМ ПОИСК ПО КРИТЕРИЯМ =====

def find_part(query):
    query = query.lower()
    results = []
    for part in cache.parts:
        if query in part.get('Номер', '').lower() or query in part.get('Артикул', '').lower():
            results.append(part)
    return results

def find_wheels(query, db):
    query = query.lower().replace(" ", "").replace("-", "")
    results = []

    for part in db:
        radius = str(part.get("Диаметр диска", "")).lower().replace(" ", "")
        brand = str(part.get("Производитель диска", "")).lower()
        model = str(part.get("Модель диска", "")).lower()

        # Поиск по радиусу
        if query in radius or query in f"r{radius}":
            results.append(part)
        # Поиск по бренду/модели
        elif query in brand or query in model:
            results.append(part)

        if len(results) >= 20:
            break

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


def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()
    text_lower = text.lower()

    logging.info(f"Получено сообщение от {peer_id}: '{text}'")
    logging.info(f"Текущее состояние пользователя: {user_state.get(peer_id)}")

    try:
        if not text:
            return

        # Обработка кнопок главного меню
        if text_lower in ["🚗 запчасти", "запчасти"]:
            user_state[peer_id] = "parts"
            send(peer_id, "Введите номер детали:", keyboard=None)
            return
        elif text_lower in ["🛞 диски", "диски"]:
            user_state[peer_id] = "wheels"
            send(peer_id, "Введите размер, например R18:", keyboard=None)
            return
        elif text_lower in ["🚘 доноры", "доноры"]:
            user_state[peer_id] = "donors"
            send(peer_id, "Введите марку авто:", keyboard=None)
            return
        elif text_lower in ["❤️ избранное", "избранное"]:
            show_favorites(peer_id)
            return
        elif text_lower in ["⬅️ назад", "назад", "сброс", "отмена"]:
            user_state[peer_id] = None
            user_results[peer_id] = []
            user_index[peer_id] = 0
            send(peer_id, "Меню сброшено. Чем помочь?", keyboard=get_main_keyboard())
            return

        # --- ОСНОВНАЯ ЛОГИКА ПОИСКА И НАВИГАЦИИ ---
        current_state = user_state.get(peer_id)

        # --- Блок для ЗАПЧАСТЕЙ (Parts) ---
        if current_state == "parts":
            # Проверяем кнопки навигации
            if text in ["⬅️ Назад", "Назад"]:
                _handle_navigation(peer_id, -1)
                return
            elif text in ["➡️ Вперед", "Вперед"]:
                _handle_navigation(peer_id, 1)
                return
            elif text in ["🔄 Обновить", "Обновить"]:
                show_part(peer_id)
                return
            
            # Если это не кнопка — это поисковый запрос
            logging.info(f"Начинаем поиск деталей для запроса: '{text}'")
            results = cache.search_parts(text)

            if results:
                user_results[peer_id] = results
                user_index[peer_id] = 0
                show_part(peer_id)
            else:
                send(peer_id, "❌ Детали не найдены. Попробуйте другой запрос или номер.")

        # --- Блок для ДИСКОВ (Wheels) ---
        elif current_state == "wheels":
            # Получаем текущие результаты для этого пользователя
            results = user_results.get(peer_id, [])

            # --- 1. СНАЧАЛА ПРОВЕРЯЕМ НАВИГАЦИОННЫЕ КОМАНДЫ ---
            if text in ["⬅️ Назад", "Назад"]:
                if results and len(results) > 1:
                    new_index = user_index.get(peer_id, 0) - 1
                    if new_index < 0:
                        new_index = len(results) - 1 # Цикл в начало
                    user_index[peer_id] = new_index
                    show_wheel(peer_id)
                else:
                    # Если результатов нет или он один, просто игнорируем или выводим подсказку
                    send(peer_id, "Сначала нужно выполнить поиск. Введите размер диска (например, R18).")
                return

            elif text in ["➡️ Вперед", "Вперед"]:
                if results and len(results) > 1:
                    new_index = user_index.get(peer_id, 0) + 1
                    if new_index >= len(results):
                        new_index = 0 # Цикл в конец
                    user_index[peer_id] = new_index
                    show_wheel(peer_id)
                else:
                    send(peer_id, "Сначала нужно выполнить поиск. Введите размер диска (например, R18).")
                return

            elif text in ["🔄 Обновить", "Обновить"]:
                # Если нажали обновить без поиска, просто просим ввести размер
                if not results:
                     send(peer_id, "Сначала нужно выполнить поиск. Введите размер диска (например, R18).")
                else:
                    show_wheel(peer_id)
                return

            # --- 2. ЕСЛИ ЭТО НЕ КНОПКА, ЗНАЧИТ ЭТО ПОИСКОВЫЙ ЗАПРОС ---
            else:
                logging.info(f"Начинаем поиск дисков для запроса: '{text}'")
                results = cache.search_wheels(text)

                if results:
                    user_results[peer_id] = results
                    user_index[peer_id] = 0 # Всегда начинаем с первого элемента при новом поиске
                    show_wheel(peer_id)
                else:
                    send(peer_id, "❌ Диски не найдены. Проверьте введенное число (например, 17 или R18).")

        # --- Блок для ДОНОРОВ (Donors) ---
        elif current_state == "donors":
             # Проверяем кнопки навигации
            if text in ["⬅️ Назад", "Назад"]:
                results = user_results.get(peer_id, [])
                if results and len(results) > 1:
                    new_index = user_index.get(peer_id, 0) - 1
                    if new_index < 0:
                        new_index = len(results) - 1
                    user_index[peer_id] = new_index
                    show_donor(peer_id)
                return

            elif text in ["➡️ Вперед", "Вперед"]:
                results = user_results.get(peer_id, [])
                if results and len(results) > 1:
                    new_index = user_index.get(peer_id, 0) + 1
                    if new_index >= len(results):
                        new_index = 0
                    user_index[peer_id] = new_index
                    show_donor(peer_id)
                return

            # Если это не кнопка — это поисковый запрос
            else:
                logging.info(f"Начинаем поиск доноров для запроса: '{text}'")
                results = cache.search_donors(text)
                
                if results:
                    user_results[peer_id] = results
                    user_index[peer_id] = 0 
                    show_donor(peer_id)
                else:
                    send(peer_id, "❌ Доноры не найдены.")

    except Exception as e:
        # Этот блок поймает любые ошибки в логике выше (например, проблемы с сетью при поиске)
        logging.error(f"Ошибка при обработке сообщения от {peer_id}: {e}")
        send(peer_id, "Произошла внутренняя ошибка. Попробуйте еще раз или нажмите 'Назад'.")


def _handle_navigation(peer_id: int, direction: int) -> None:
    """
    Обрабатывает навигацию по результатам (вперёд/назад).

    Args:
        peer_id: ID пользователя.
        direction: направление (-1 — назад, 1 — вперёд).
    """
    results = user_results.get(peer_id, [])
    if not results or len(results) <= 1:
        return  # Навигация не нужна для 0–1 результата

    current_index = user_index.get(peer_id, 0)
    new_index = current_index + direction

    # Циклическая навигация
    if new_index < 0:
        new_index = len(results) - 1
    elif new_index >= len(results):
        new_index = 0

    user_index[peer_id] = new_index
    show_part(peer_id)
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
