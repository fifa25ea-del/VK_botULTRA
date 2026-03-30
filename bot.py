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
from urllib.parse import urlparse
import random

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
    keyboard.add_line()
    keyboard.add_button("👨‍💻 Менеджер", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.NEGATIVE)
    
    return keyboard.get_keyboard()

def send_photo_with_caption(peer_id, photo_url, caption):
    """Отправляет фото с подписью"""
    def upload_and_send():
        try:
            # Загружаем изображение
            response = requests.get(photo_url, timeout=10, stream=True)
            response.raise_for_status() # Проверка статуса 200 OK

            # Проверяем, что сервер вернул картинку (а не HTML-страницу с ошибкой 404)
            content_type = response.headers.get('Content-Type', '')
            if 'image' not in content_type:
                logging.warning(f"URL не содержит изображение (Content-Type: {content_type}): {photo_url}")
                return # Просто выходим, если это не картинка

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
                random_id=0
            )
            logging.info(f"Фото успешно отправлено: {photo_url}")

        except requests.exceptions.Timeout:
            logging.warning(f"Таймаут при загрузке фото: {photo_url}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"Ошибка сети при загрузке фото: {e}")
        except Exception as e:
            logging.error(f"Неизвестная ошибка при обработке фото: {e}")

    thread = threading.Thread(target=upload_and_send)
    thread.daemon = True
    thread.start()

def get_first_photo(photo_field):
    """Извлекает первую валидную ссылку на фото из строки с несколькими ссылками"""
    if not photo_field:
        return None

    # Иногда ссылки разделены не просто запятой, а запятой с пробелом или спецсимволами
    # Разбиваем строку по запятым
    potential_urls = [url.strip() for url in str(photo_field).split(',')]
    
    # Проверяем каждую найденную ссылку
    for url in potential_urls:
        # Пропускаем пустые строки
        if not url:
            continue
            
        # Проверяем, что ссылка начинается на http или https
        if url.startswith('http://') or url.startswith('https://'):
            # Иногда ссылки могут содержать закодированные символы (например, %20 вместо пробела)
            # или быть повреждены. Проверим минимальную длину и наличие точки (домен)
            if len(url) > 10 and '.' in urlparse(url).netloc:
                return url
            
    return None

# ===== ОТПРАВКА СООБЩЕНИЙ =====
def send_safe(peer_id, text, keyboard=None):
    """Безопасная отправка сообщения с обработкой ошибок"""
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=0,
            keyboard=keyboard if keyboard else get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Критическая ошибка отправки VK API для {peer_id}: {e}")
        # Попытка отправить простое сообщение без клавиатуры
        try:
            vk.messages.send(
                peer_id=peer_id,
                message="Произошла ошибка при отправке сообщения. Попробуйте позже.",
                random_id=0
            )
        except:
            pass  # Игнорируем, если даже простое сообщение не отправляется

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
    
    def get_latest_donors(self, limit=15):
        """
        Возвращает список последних 'limit' доноров из локального кэша.
        Сортировка: от НОВЫХ к СТАРЫМ.
        """
        # Создаем копию списка, чтобы не сломать исходный порядок в кэше
        donors_copy = self.donors.copy()
        
        # Если доноров меньше, чем лимит, просто возвращаем все что есть
        if len(donors_copy) <= limit:
            return donors_copy
        
        # Берем последние 'limit' элементов из списка.
        # Предполагается, что в CSV-файле самые свежие авто находятся в конце.
        latest_donors = donors_copy[-limit:]
        
        # Так как мы взяли срез с конца, порядок будет [Старый_в_выборке, ..., Новый_в_выборке].
        # Нам нужно перевернуть его, чтобы [Новый_в_выборке, ..., Старый_в_выборке].
        latest_donors.reverse()
        
        return latest_donors
        
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
    """Показывает карточку детали ОДНИМ сообщением (текст + фото + клавиатура)."""
    try:
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])
        current_state = user_state.get(peer_id)

        if not results:
            send_safe(peer_id, "Нет результатов поиска для отображения")
            return

        if index >= len(results) or index < 0:
            send_safe(peer_id, "Нет данных для отображения (некорректный индекс)")
            return

        part = results[index]

        # Проверка целостности данных
        if not part or not any(str(v).strip() for v in part.values()):
            send_safe(peer_id, "Данные о детали повреждены. Попробуйте поиск заново.")
            return

        # --- 1. ФОРМИРУЕМ ТЕКСТ КАРТОЧКИ ---
        message = "🚗 Карточка детали:\n"
        message += f"Название: {safe_get(part, 'Наименование')}\n"
        message += f"Кузов: {safe_get(part, 'Кузов')}\n"
        message += f"Артикул: {safe_get(part, 'Артикул')}\n"

        price = safe_get(part, 'Цена')
        if price != "Не указано":
            message += f"Цена: {price}\n"

        link = safe_get(part, 'Ссылка')
        if link != "Не указано" and link != "Нет ссылки":
            message += f"Ссылка: {link}"

        # --- ДОБАВЛЯЕМ НУМЕРАЦИЮ ---
        total_items = len(results)
        current_position = index + 1
        message += f"\n📊 {current_position} из {total_items}"


        # --- 2. СОЗДАЕМ КЛАВИАТУРУ ---
        keyboard = VkKeyboard(one_time=False)
        
        # Логика кнопок зависит от того, где мы находимся: в поиске или в избранном
        if current_state == "favorites_view":
            # Если мы в режиме просмотра избранного
            keyboard.add_button("🗑 Удалить", color=VkKeyboardColor.NEGATIVE)
            keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.NEGATIVE)
            keyboard.add_line()
        else: 
            # Если мы в обычном поиске запчастей
            keyboard.add_button("❤️ Добавить в избранное", color=VkKeyboardColor.POSITIVE)
            keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.NEGATIVE)
            keyboard.add_line()

        # Кнопки навигации (всегда добавляем)
        keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
        keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
        
        # Кнопка обновления (на отдельной строке)
        keyboard.add_line() 
        keyboard.add_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY)

        keyboard_data = keyboard.get_keyboard()


        # --- 3. ОТПРАВЛЯЕМ СООБЩЕНИЕ (С ФОТО ИЛИ БЕЗ) ---
        photo_url = get_first_photo(part.get('Фото', ''))

        if photo_url:
            try:
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
                
                # Отправляем ОДНО сообщение с фото и клавиатурой
                vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    attachment=attachment,
                    keyboard=keyboard_data,
                    random_id=get_random_id()
                )

            except requests.exceptions.RequestException as e:
                logging.warning(f"Ошибка загрузки фото (запчасти): {e}. Отправляем только текст.")
                send_safe(peer_id, message, keyboard=keyboard_data)
                
            except Exception as e:
                logging.error(f"Неизвестная ошибка при отправке фото детали: {e}")
                send_safe(peer_id, message, keyboard=keyboard_data)

        else:
            # Если фото нет в базе, сразу отправляем текст с клавиатурой
            send_safe(peer_id, message, keyboard=keyboard_data)

    except Exception as e:
        logging.critical(f"ФАТАЛЬНАЯ ошибка в show_part для {peer_id}: {e}")
        send_safe(peer_id, "Произошла критическая ошибка при отображении детали.")
        
def show_wheel(peer_id):
    """Показывает карточку диска: фото + текст с кнопками одним сообщением."""
    try:
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])

        if not results:
            send_safe(peer_id, "Нет результатов поиска для отображения")
            return

        # Реверсивный порядок (свежие объявления первыми)
        reversed_results = list(results)
        reversed_results.reverse()

        total_items = len(reversed_results)
        reversed_index = total_items - 1 - index

        if reversed_index >= total_items or reversed_index < 0:
            send_safe(peer_id, "Нет данных для отображения")
            return

        wheel = reversed_results[reversed_index]

        # Проверка целостности данных
        if not wheel or not any(str(v).strip() for v in wheel.values()):
            send_safe(peer_id, "Данные о диске повреждены. Попробуйте поиск заново.")
            return

        # Формируем текст карточки
        message = "🛞 Карточка диска:\n"
        message += f"Производитель: {safe_get(wheel, 'Производитель диска')}\n"
        message += f"Артикул: {safe_get(wheel, 'Артикул')}\n"
        message += f"Модель: {safe_get(wheel, 'Модель диска')}\n"
        message += f"Размер: {safe_get(wheel, 'Размер')}\n"

        price = safe_get(wheel, 'Цена')
        if price != "Не указано":
            message += f"Цена: {price}\n"

        link = safe_get(wheel, 'Ссылка')
        if link not in ("Не указано", "Нет ссылки"):
            message += f"Ссылка: {link}\n"  # Добавлено \n для единообразия форматирования

        # Добавляем нумерацию
        current_position = reversed_index + 1
        message += f"\n📊 {current_position} из {total_items}"

        # Создаём клавиатуру
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()
        keyboard.add_button("❤️ Добавить в избранное", color=VkKeyboardColor.POSITIVE)

        if total_items > 1:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)

        keyboard.add_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY)

        if total_items > 1:
            keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)

        keyboard_data = keyboard.get_keyboard()

        # Отправка сообщения с фото и текстом
        photo_url = get_first_photo(wheel.get('Фото', ''))

        if photo_url:
            try:
                # Загружаем фото
                response = requests.get(photo_url, timeout=10)
                response.raise_for_status()

                # Получаем URL для загрузки
                upload_url = vk.photos.getMessagesUploadServer()['upload_url']
                files = {'photo': ('image.jpg', response.content)}
                upload_data = requests.post(upload_url, files=files, timeout=15).json()

                # Сохраняем фото
                photo_data = vk.photos.saveMessagesPhoto(
                    server=upload_data['server'],
                    photo=upload_data['photo'],
                    hash=upload_data['hash']
                )[0]

                attachment = f"photo{photo_data['owner_id']}_{photo_data['id']}"

                # Отправляем сообщение с фото, текстом и клавиатурой
                vk.messages.send(
                    peer_id=peer_id,
                    message=message,
                    attachment=attachment,
                    keyboard=keyboard_data,
                    random_id=get_random_id()
                )
            except requests.exceptions.RequestException as e:
                logging.warning(f"Ошибка загрузки фото (диски): {e}. Отправляем только текст.")
                send_safe(peer_id, message, keyboard=keyboard_data)
            except Exception as e:
                logging.error(f"Неизвестная ошибка при отправке фото диска: {e}")
                send_safe(peer_id, message, keyboard=keyboard_data)
        else:
            # Если фото нет в базе, отправляем просто текст с кнопками
            send_safe(peer_id, message, keyboard=keyboard_data)

    except Exception as e:
        logging.critical(f"ФАТАЛЬНАЯ ошибка в show_wheel для {peer_id}: {e}")
        send_safe(peer_id, "Произошла критическая ошибка при отображении диска. Обратитесь к администратору.")

def show_donor(peer_id):
    """
    Показывает карточку донора: сначала фото, затем текст с кнопками.
    """
    try:
        results = user_results.get(peer_id, [])
        index = user_index.get(peer_id, 0)

        if not results or index >= len(results) or index < 0:
            send(peer_id, "🚫 Данные о доноре недоступны. Попробуйте начать сначала.")
            return

        donor = results[index]

        # --- 1. ФОРМИРУЕМ ТЕКСТ И КЛАВИАТУРУ ---
        message_text = "🚘 Карточка авто-донора:\n"
        message_text += f"Марка: {safe_get(donor, 'Марка')}\n"
        message_text += f"Модель: {safe_get(donor, 'Модель')}\n"
        message_text += f"Цвет: {safe_get(donor, 'Цвет')}\n"
        message_text += f"Год: {safe_get(donor, 'Год')}\n"
        message_text += f"Двигатель: {safe_get(donor, 'Двигатель')}\n"
        message_text += f"VIN: {safe_get(donor, 'VIN')}"

        # Добавляем цену и ссылку, если они есть
        price = safe_get(donor, 'Цена')
        if price != "Не указано":
            message_text += f"\nЦена: {price}"
            
        link = safe_get(donor, 'Ссылка')
        if link != "Не указано" and link != "Нет ссылки":
            message_text += f"\nСсылка: {link}"

        # Создаем клавиатуру
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()
        keyboard.add_button("❤️ Добавить в избранное", color=VkKeyboardColor.POSITIVE)
        keyboard.add_line()
        
        total_items = len(results)
        if total_items > 1:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
            keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
            keyboard.add_line()
        
        keyboard.add_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY)
        
        keyboard_data = keyboard.get_keyboard()

        # --- 2. ОТПРАВЛЯЕМ ФОТО (ЕСЛИ ЕСТЬ) ---
        photo_url = get_first_photo(donor.get('Фото', ''))

        if photo_url:
            try:
                # Загружаем изображение
                response = requests.get(photo_url, timeout=10)
                response.raise_for_status()

                # Загружаем фото в VK
                upload_url = vk.photos.getMessagesUploadServer()['upload_url']
                files = {'photo': ('image.jpg', response.content)}
                upload_data = requests.post(upload_url, files=files, timeout=15).json()

                photo_data = vk.photos.saveMessagesPhoto(
                    server=upload_data['server'],
                    photo=upload_data['photo'],
                    hash=upload_data['hash']
                )[0]
                
                attachment = f"photo{photo_data['owner_id']}_{photo_data['id']}"
                
                # Отправляем ТОЛЬКО ФОТО (без текста и кнопок)
                vk.messages.send(
                    peer_id=peer_id,
                    attachment=attachment,
                    random_id=get_random_id()
                )
                
            except Exception as e:
                logging.warning(f"Ошибка загрузки фото (доноры): {e}. Отправляем только текст.")
                # Если фото не загрузилось, отправляем текст с кнопками сразу
                send(peer_id, message_text, keyboard=keyboard_data)
                return # Останавливаем функцию здесь

        # --- 3. ОТПРАВЛЯЕМ ТЕКСТ С КЛАВИАТУРОЙ ---
        # Этот код выполнится в любом случае:
        #   - Если фото не было.
        #   - Если фото было отправлено успешно.
        send(peer_id, message_text, keyboard=keyboard_data)

    except Exception as e:
        logging.critical(f"ФАТАЛЬНАЯ ошибка в show_donor для {peer_id}: {e}")
        send(peer_id, "Произошла критическая ошибка при отображении донора.")

def show_favorite_card(peer_id):
    """Отображает одну карточку из списка избранного."""
    try:
        results = user_results.get(peer_id, [])
        index = user_index.get(peer_id, 0)

        if not results:
            send(peer_id, "Избранное пусто.", keyboard=get_main_keyboard())
            user_state[peer_id] = None
            return

        item = results[index]
        total_items = len(results)
        current_position = index + 1

        # Формируем текст карточки
        name = item.get('Наименование') or item.get('Модель диска') or item.get('Марка') or 'Товар'
        message = f"📦 {name}\n"
        
        article = item.get('Артикул') or item.get('Номер')
        if article:
            message += f"Артикул: {article}\n"
            
        message += f"Цена: {item.get('Цена', 'Не указана')}\n"
        link = item.get('Ссылка')
        if link and link not in ["Не указано", "Нет ссылки"]:
            message += f"Ссылка: {link}"
            
        message += f"\n📊 {current_position} из {total_items}"

        # Создаем клавиатуру (строго 2 кнопки в первом ряду)
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("🗑 Удалить", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_button("🏠 Меню", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()

        if total_items > 1:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
            keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
        
        keyboard_data = keyboard.get_keyboard()

        # Пробуем отправить фото с текстом и клавиатурой одним сообщением
        photo_url = get_first_photo(item.get('Фото', ''))

        if photo_url:
            try:
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
                # Если с фото беда, отправляем просто текст с клавиатурой
                logging.warning(f"Ошибка фото в избранном: {e}. Отправляем текст.")
                send_safe(peer_id, message, keyboard=keyboard_data)
        else:
            # Если фото нет в базе, отправляем текст с клавиатурой
            send_safe(peer_id, message, keyboard=keyboard_data)

    except Exception as e:
        logging.error(f"Ошибка в show_favorite_card: {e}")
        send(peer_id, "Произошла ошибка при отображении избранного.")

# ===== ДОБАВЛЯЕМ ПОИСК ПО КРИТЕРИЯМ =====

def find_part(query):
    query = query.lower()
    results = []
    for part in cache.parts:
        if query in part.get('Номер', '').lower() or query in part.get('Артикул', '').lower():
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
    """Открывает режим просмотра избранного."""
    fav_items = favorites.get(peer_id, [])
    
    if not fav_items:
        send(peer_id, "❤️ Ваше избранное пусто.", keyboard=get_main_keyboard())
        return

    user_results[peer_id] = fav_items
    user_index[peer_id] = 0
    user_state[peer_id] = "favorites_view"
    
    show_favorite_card(peer_id)


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
            send(peer_id, "Введите номер детали или артикул:", keyboard=None)
            return
        elif text_lower in ["🛞 диски", "диски"]:
            user_state[peer_id] = "wheels"
            send(peer_id, "Введите размер (например, R18 или 18):", keyboard=None)
            return
        elif text_lower in ["🚘 доноры", "доноры"]:
            user_state[peer_id] = "donors"
            latest_donors = cache.get_latest_donors(limit=15)
            if latest_donors:
                user_results[peer_id] = latest_donors
                user_index[peer_id] = 0
                show_donor(peer_id)
            else:
                send(peer_id, "🚫 Не удалось загрузить список доноров.", keyboard=get_main_keyboard())
                user_state[peer_id] = None
            return
        elif text_lower in ["❤️ избранное", "избранное"]:
            show_favorites(peer_id)
            return
        elif text_lower in ["👨‍💻 менеджер", "менеджер"]:
            user_state[peer_id] = "manager"
            send(peer_id, "👨‍💻 Вас приветствует менеджер!\n\nОпишите ваш вопрос или задачу. Сообщение будет перенаправлено специалисту.", keyboard=None)
            return
        elif text_lower in ["⬅️ назад", "назад", "сброс", "отмена"]:
            user_state[peer_id] = None
            user_results.pop(peer_id, None)
            user_index.pop(peer_id, None)
            send(peer_id, "Меню сброшено. Чем помочь?", keyboard=get_main_keyboard())
            return

        # Если мы здесь, значит нажата кнопка внутри карточки или введен текст в режиме поиска
        current_state = user_state.get(peer_id)

        # --- БЛОК ДЛЯ ЗАПЧАСТЕЙ (Parts) ---
        if current_state == "parts":
            # Получаем текущие результаты и индекс для этого пользователя
            results = user_results.get(peer_id, [])
            index = user_index.get(peer_id, 0)

            # --- 1. ОБРАБОТКА КНОПОК (Имеют приоритет над поиском) ---
            if text in ["⬅️ Назад", "Назад"]:
                # Проверяем, есть ли что листать
                if results and len(results) > 1:
                    new_index = index - 1
                    # Если ушли за начало списка, переходим в конец
                    if new_index < 0:
                        new_index = len(results) - 1
                    user_index[peer_id] = new_index
                    show_part(peer_id)
                return

            elif text in ["➡️ Вперед", "Вперед"]:
                if results and len(results) > 1:
                    new_index = index + 1
                    # Если ушли за конец списка, переходим в начало
                    if new_index >= len(results):
                        new_index = 0
                    user_index[peer_id] = new_index
                    show_part(peer_id)
                return

            elif text in ["🔄 Обновить", "Обновить"]:
                # Просто обновляем текущую карточку (перезагрузка фото/текста)
                show_part(peer_id)
                return

            elif text == "❤️ Добавить в избранное":
                # Логика остается прежней
                index = user_index.get(peer_id, 0)
                results = user_results.get(peer_id, [])
                if results and index < len(results):
                    current_item = results[index]
                    add_to_favorites(peer_id, current_item)
                else:
                    send(peer_id, "Ошибка: не удалось найти элемент для добавления.")
                return

            # --- 2. ПОИСКОВЫЙ ЗАПРОС (Если это не кнопка) ---
            # Если мы дошли досюда, значит нажата кнопка поиска или введено сообщение
            logging.info(f"Начинаем поиск деталей для запроса: '{text}'")
            results = cache.search_parts(text)
            if results:
                user_results[peer_id] = results
                user_index[peer_id] = 0 # Сбрасываем на первую позицию при новом поиске
                show_part(peer_id)
            else:
                send(peer_id, "❌ Детали не найдены. Попробуйте другой запрос или номер.")
        
        # --- БЛОК ДЛЯ ДИСКОВ (Wheels) ---
        elif current_state == "wheels":
             # 1. Проверяем кнопки навигации и избранного
             if text in ["⬅️ Назад", "Назад"]:
                 if len(user_results.get(peer_id, [])) > 1:
                     new_index = (user_index.get(peer_id, 0) - 1) % len(user_results[peer_id])
                     user_index[peer_id] = new_index
                     show_wheel(peer_id)
                 else:
                     send(peer_id, "Сначала нужно выполнить поиск. Введите размер диска (например, R18).")
                 return

             elif text in ["🔄 Обновить", "Обновить"]:
                 # Если есть результаты, обновляем фото/текст. Если нет — просим ввести запрос.
                 if user_results.get(peer_id):
                     show_wheel(peer_id)
                 else:
                     send(peer_id, "Сначала нужно выполнить поиск. Введите размер диска (например, R18).")
                 return

             elif text == "❤️ Добавить в избранное":
                 index = user_index.get(peer_id, 0)
                 results = user_results.get(peer_id, [])
                 if results and index < len(results):
                     current_item = results[index]
                     add_to_favorites(peer_id, current_item)
                 else:
                     send(peer_id, "Ошибка: не удалось найти элемент для добавления.")
                 return

             # 2. Если это не кнопка — это поисковый запрос по размеру
             else:
                 logging.info(f"Начинаем поиск дисков для запроса: '{text}'")
                 results = cache.search_wheels(text)
                 
                 if results:
                     user_results[peer_id] = results
                     user_index[peer_id] = 0
                     show_wheel(peer_id)
                 else:
                     send(peer_id, "❌ Диски не найдены. Проверьте введенное число (например, 17 или R18).")
        
        # --- БЛОК ДЛЯ ДОНОРОВ (Donors) ---
        elif current_state == "donors":
             # В этом режиме мы либо листаем список последних доноров,
             # ЛИБО ищем по марке/модели (если пользователь ввел текст в поле поиска VK)
             
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

             # Если это не кнопка — это поисковый запрос по марке/модели
             else:
                 logging.info(f"Начинаем поиск доноров для запроса: '{text}'")
                 results = cache.search_donors(text)
                 
                 if results:
                     user_results[peer_id] = results
                     user_index[peer_id] = 0 
                     show_donor(peer_id)
                 else:
                     send(peer_id, "❌ Доноры не найдены.")
        
        # --- БЛОК МЕНЕДЖЕРА (Manager) ---
        elif current_state == "manager":
             # Здесь логика перенаправления сообщения администратору.
             # В текущем коде она не реализована.
             send(ADMIN_ID, f"Запрос от пользователя {peer_id}:\n{text}")
             send(peer_id, "👨‍💻 Ваше сообщение передано менеджеру! Ответ поступит в ближайшее время.", keyboard=get_main_keyboard())
             user_state[peer_id] = None # Сбрасываем состояние после отправки

        elif current_state == "favorites_view":
            results = user_results.get(peer_id, [])
            index = user_index.get(peer_id, 0)
            
            # --- КНОПКА УДАЛЕНИЯ ---
            if text == "🗑 Удалить":
                if results and index < len(results):
                    # 1. Удаляем из списка в памяти
                    del results[index]
                    
                    # 2. Сохраняем изменения в файл
                    favorites[peer_id] = results
                    save_json(FAV_FILE, favorites)
                    
                    send(peer_id, "Товар удален из избранного.")
                    
                    # 3. Проверяем, не пуст ли список теперь
                    if len(results) == 0:
                        send(peer_id, "Избранное очищено.", keyboard=get_main_keyboard())
                        user_state[peer_id] = None
                        user_results.pop(peer_id, None)
                        return

                    # 4. Показываем следующую карточку (или предыдущую)
                    # Если удалили последний элемент, index станет за пределами списка
                    if index >= len(results):
                        user_index[peer_id] = len(results) - 1
                    
                    show_favorite_card(peer_id)
                return

            # --- КНОПКИ НАВИГАЦИИ ---
            elif text in ["⬅️ Назад", "Назад"]:
                if len(results) > 1:
                    new_index = (index - 1) % len(results)
                    user_index[peer_id] = new_index
                    show_favorite_card(peer_id)
                else:
                    send(peer_id, "В избранном только один товар.")
                return

            elif text in ["➡️ Вперед", "Вперед"]:
                if len(results) > 1:
                    new_index = (index + 1) % len(results)
                    user_index[peer_id] = new_index
                    show_favorite_card(peer_id)
                else:
                    send(peer_id, "В избранном только один товар.")
                return

            # --- КНОПКА ВЫХОДА ---
            elif text in ["🏠 Меню", "🏠 Главное меню", "⬅️ назад", "назад"]:
                user_state[peer_id] = None
                user_results.pop(peer_id, None)
                user_index.pop(peer_id, None)
                send(peer_id, "Меню сброшено. Чем помочь?", keyboard=get_main_keyboard())
                return
                
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
