# =========================
# VK BOT ULTRA (ТОП ВЕРСИЯ)
# =========================
import re
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
from io import StringIO

def load_json(file_path):
    if not os.path.exists(file_path):
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_image(url):
    try:
        response = requests.get(url, timeout=3)
        return response.content
    except Exception as e:
        logging.warning(f"Ошибка загрузки фото: {e}")
        return None

def normalize_query(text: str) -> str:
    text = text.upper()

    # заменяем русские буквы на английские
    ru_to_en = {
        'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K',
        'М': 'M', 'Н': 'H', 'О': 'O', 'Р': 'P',
        'С': 'C', 'Т': 'T', 'Х': 'X'
    }

    for ru, en in ru_to_en.items():
        text = text.replace(ru, en)

    # убираем всё кроме букв и цифр
    text = re.sub(r'[^A-Z0-9]', '', text)

    # убираем ведущие буквы (например A)
    text = re.sub(r'^[A-Z]+', '', text)

    return text

def get_random_id():
    """Генерирует случайный ID для VK API (от 0 до 2^31−1)"""
    return random.randint(0, 2**31 - 1)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_latest_donors(data, limit=15):
    """Возвращает последние N доноров, новые — первыми."""
    # Берём последние N элементов
    latest = data[-limit:]
    # Переворачиваем, чтобы новые были в начале
    return latest[::-1]


def load_donors_csv(url, max_retries=3, timeout=30):
    """Загружает CSV с повторными попытками и увеличенным таймаутом."""
    for attempt in range(max_retries):
        try:
            logging.info(f"Попытка загрузки CSV (попытка {attempt + 1}/{max_retries})")
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            logging.info("CSV успешно загружен")
            return response.text
        except requests.exceptions.Timeout:
            logging.warning(f"Таймаут загрузки (попытка {attempt + 1}). Ждём перед повторной попыткой...")
            time.sleep(2 ** attempt)  # Экспоненциальная задержка: 2, 4, 8 секунд
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка загрузки CSV: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
    raise Exception("Не удалось загрузить CSV после нескольких попыток")

def get_item_id(item):
    return (
        str(item.get('Артикул') or '') +
        str(item.get('Номер') or '') +
        str(item.get('Номер товара') or '') +
        str(item.get('Наименование') or '') +
        str(item.get('Цена') or '')
    )

def save_favorites():
    with open(FAV_FILE, "w", encoding="utf-8") as f:
        json.dump(user_favorites, f, ensure_ascii=False, indent=2)

def load_favorites():
    global user_favorites
    user_favorites = load_json(FAV_FILE)
    
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

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ =====
watchlist = {}
user_state = {}  # Хранит текущее состояние пользователя
user_results = {}  # Хранит результаты поиска для пользователя
user_index = {}  # Хранит текущий индекс в результатах поиска
user_mode = {}  # peer_id → 'wheel', 'part' или None
initializing_wheels = set()  # Множество peer_id, которые сейчас инициализируют поиск дисков
_donors_cache = None
_last_cache_update = 0
_CACHE_TTL = 300  # Время жизни кэша — 5 минут
image_cache = {}
user_favorites = load_json(FAV_FILE) or {}



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

def get_parts_menu_keyboard():
    keyboard = VkKeyboard(one_time=False)
    
    # Первая строка: Поиск и Популярное
    keyboard.add_button("🔍 Поиск по номеру", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🔥 Популярное", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    
    # Вторая строка: Категории
    keyboard.add_button("⚙️ Двигатель", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🕹 Акпп", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    
    # Кнопка возврата
    keyboard.add_button("⬅️ В главное меню", color=VkKeyboardColor.NEGATIVE)
    
    return keyboard.get_keyboard()

def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    
    # Первая строка
    keyboard.add_button("🚗 Запчасти", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🛞 Диски", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    
    # Вторая строка
    keyboard.add_button("👨‍💻 Менеджер", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("❤️ Избранное", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    
    # Третья строка
    keyboard.add_button("🚘 Доноры", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()
    
def get_nav_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("❤️ Добавить в избранное", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.SECONDARY)
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

def get_image_cached(url):
    if url in image_cache:
        return image_cache[url]

    img = get_image(url)
    if img:
        image_cache[url] = img

    return img

def get_donors_data():
    """Загружает и возвращает данные доноров с кэшированием."""
    global _donors_cache, _last_cache_update

    current_time = time.time()

    # Проверяем, нужно ли обновлять кэш
    if (_donors_cache is None or
        current_time - _last_cache_update > _CACHE_TTL):

        logging.info("Обновляем кэш данных доноров")
        try:
            url = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Парсим CSV
            csv_reader = csv.DictReader(StringIO(response.text))
            _donors_cache = list(csv_reader)
            _last_cache_update = current_time

            logging.info(f"Кэш обновлён: {len(_donors_cache)} доноров")

        except Exception as e:
            logging.error(f"Не удалось обновить кэш: {e}")
            if _donors_cache is None:  # Если кэш пустой и загрузка не удалась
                return []

    return _donors_cache

def save_watchlist():
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения watchlist: {e}")
    
# ===== ОТПРАВКА СООБЩЕНИЙ =====
def send_safe(peer_id, text, keyboard=None):
    try:
        final_kb = None
        
        # 1. Если клавиатура вообще не передана
        if keyboard is None:
            final_kb = get_main_keyboard() # Убедись, что эта функция возвращает строку или объект
        else:
            final_kb = keyboard

        # 2. Если это объект VkKeyboard (у него есть метод get_keyboard)
        if hasattr(final_kb, 'get_keyboard'):
            final_kb = final_kb.get_keyboard()
        
        # 3. Если это всё ещё не строка (и не None), принудительно в JSON
        if final_kb and not isinstance(final_kb, str):
            import json
            final_kb = json.dumps(final_kb)

        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=get_random_id(),
            keyboard=final_kb
        )
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")
        
def send(peer_id, text, keyboard=None):
    try:
        # Проверяем клавиатуру
        if keyboard and not isinstance(keyboard, VkKeyboard):
            keyboard = get_main_keyboard()
        
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=get_random_id(),
            keyboard=keyboard.get_keyboard() if isinstance(keyboard, VkKeyboard) else get_main_keyboard()
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

def save_json(file_path, data): # file_path — это и есть наш WATCHLIST_FILE
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f'Ошибка сохранения {file_path}: {e}')


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

    def get_parts(self, category=None):
        if not category:
            return self.parts
    
    def get_engines(self, engine_number_query):
        """
        Поиск агрегатов: слово 'ДВИГАТЕЛЬ' + номер + цена > 30000.
        """
        query = normalize_query(engine_number_query)
        results = []
        
        for part in self.parts:
            # 1. Проверка на слово 'двигатель' в названии
            item_name = part.get('Наименование', '').lower()
            
            if 'двигатель' in item_name:
                # 2. Проверка цены (должна быть > 30000)
                raw_price = part.get('Цена', '0')
                # Очищаем цену от пробелов и лишних символов, оставляем только цифры
                clean_price = ''.join(filter(str.isdigit, str(raw_price)))
                
                try:
                    price_val = int(clean_price) if clean_price else 0
                except ValueError:
                    price_val = 0

                if price_val > 30000:
                    # 3. Проверка номера модели двигателя
                    raw_engine_val = part.get('Двигатель', '')
                    db_val_normalized = normalize_query(raw_engine_val)
                    
                    if query in db_val_normalized:
                        results.append(part)
                    
        return results
        
    def __init__(self):
        self.parts = []
        self.wheels = []
        self.donors = []
        self.akpp_base = []

    def _load_csv(self, url):
        try:
            r = requests.get(url, timeout=15)
            # Для ваших ссылок baz-on лучше использовать cp1251
            r.encoding = "cp1251" 
            # Используем delimiter=";" так как в ваших файлах точка с запятой
            return list(csv.DictReader(io.StringIO(r.text), delimiter=";"))
        except Exception as e:
            logging.error(f"Ошибка загрузки CSV с {url}: {e}")
            return []

    def load_local_akpp(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_path, "akpp.csv")
        
        if os.path.exists(file_path):
            try:
                # МЕНЯЕМ КОДИРОВКУ ТУТ:
                with open(file_path, mode='r', encoding='cp1251') as f:
                    # Также проверьте разделитель. В Excel это обычно ';'
                    reader = csv.DictReader(f, delimiter=';') 
                    self.akpp_base = list(reader)
                logging.info(f"✅ База АКПП загружена: {len(self.akpp_base)} строк")
            except Exception as e:
                logging.error(f"❌ Ошибка чтения akpp.csv: {e}")
                self.akpp_base = [] 
        else:
            logging.warning(f"⚠️ Файл {file_path} не найден.")
    
    def update(self):
        logging.info("🔄 Запуск обновления данных...")
        # Убедитесь, что метод _load_csv определен ВНУТРИ класса DataCache
        self.parts = self._load_csv(PARTS_CSV)
        self.wheels = self._load_csv(WHEELS_CSV)
        self.donors = self._load_csv(DONORS_CSV)
        
        # Загрузка локального файла АКПП
        self.load_local_akpp()
        
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

    donors_cache = None
    last_cache_update = 0
    CACHE_TTL = 300  # Время жизни кэша — 5 минут
    
    def get_donors_data():
        """Загружает и возвращает данные доноров с кэшированием."""
        global _donors_cache, _last_cache_update
    
        current_time = time.time()
    
        # Проверяем, нужно ли обновлять кэш
        if (_donors_cache is None or
            current_time - _last_cache_update > _CACHE_TTL):
    
            logging.info("Обновляем кэш данных доноров")
            try:
                url = "https://baz-on.ru/export/c592/5c6ca/stuttgart-site-carsrc.csv"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
    
                # Парсим CSV с использованием StringIO
                csv_reader = csv.DictReader(StringIO(response.text))
                _donors_cache = list(csv_reader)
                _last_cache_update = current_time
    
                logging.info(f"Кэш обновлён: {len(_donors_cache)} доноров")
    
            except requests.exceptions.Timeout:
                logging.error("Таймаут при загрузке CSV")
                if _donors_cache is None:
                    return []
            except requests.exceptions.RequestException as e:
                logging.error(f"Ошибка загрузки CSV: {e}")
                if _donors_cache is None:
                    return []
            except Exception as e:
                logging.error(f"Неожиданная ошибка при парсинге CSV: {e}")
                if _donors_cache is None:
                    return []
    
        return _donors_cache
    
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
            notify_watchlist()
        except Exception as e:
            logging.error(f"Ошибка автообновления: {e}")
        time.sleep(300)  # Обновляем каждые 5 минут

# Запускаем поток автообновления
threading.Thread(target=auto_update, daemon=True).start()

def notify_watchlist():
    global watchlist
    try:
        for peer_id, queries in list(watchlist.items()):
            to_remove = []
            for query in queries:
                results = find_part(query)
                if results:  # если появилась хотя бы одна деталь
                    send(peer_id, f"🔔 Товар '{query}' появился в базе!")
                    show_part_info(peer_id, results[0])
                    to_remove.append(query)  # убираем из списка отслеживания
            # удаляем отправленные
            for q in to_remove:
                queries.remove(q)
            if not queries:
                watchlist.pop(peer_id)
        save_watchlist()
    except Exception as e:
        logging.error(f"Ошибка при уведомлении watchlist: {e}")

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

def enter_wheel_mode(peer_id):
    user_mode[peer_id] = 'wheel'
    show_wheel_item(peer_id, 0)  # показываем первый элемент


def enter_part_mode(peer_id):
    user_mode[peer_id] = 'part'
    show_part_item(peer_id, 0)  # показываем первый элемент

def render_current_item(peer_id):
    """Решает, какую функцию отрисовки вызвать на основе данных."""
    results = user_results.get(peer_id, [])
    index = user_index.get(peer_id, 0)
    
    if not results or index >= len(results):
        return

    item = results[index]

    # Если есть VIN или 'Номер донора' — это точно донор
    if 'VIN' in item or 'Номер донора' in item or 'Марка' in item:
        show_donor(peer_id)
    # Если есть КПП/АКПП в названии — вызываем show_akpp
    elif 'маркировка' in str(item).lower() and 'кпп' in str(item).lower():
        show_akpp(peer_id)
    # Иначе — обычная деталь
    else:
        show_part(peer_id)

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
        message += f"Номер запчасти: {safe_get(part, 'Номер')}\n"
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

        # Логика кнопок зависит от того, где мы находимся
        if current_state == "favorites_view":
            # Режим просмотра избранного
            keyboard.add_button("🗑 Удалить", color=VkKeyboardColor.NEGATIVE)
            keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.NEGATIVE)
            keyboard.add_line()
        else: 
            # Обычный поиск запчастей
            keyboard.add_button("❤️ Добавить в избранное", color=VkKeyboardColor.POSITIVE)
            keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.NEGATIVE)
            keyboard.add_line()
        
        # Кнопки навигации (всегда добавляем)
        keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
        keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()  # Новая строка для кнопки обновления
        
        # Кнопка обновления
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

def show_engine(peer_id, item=None):
    results = user_results.get(peer_id, [])
    index = user_index.get(peer_id, 0)

    if not results:
        send_safe(peer_id, "❌ Данные двигателя не найдены.")
        return

    if item is None:
        item = results[index]

    # --- 1. ФОРМИРУЕМ ТЕКСТ (Стиль как в АКПП) ---
    title = "🚀 ДВИГАТЕЛЬ"
    model_engine = item.get('Двигатель') or item.get('Маркировка') or 'Не указана'
    price = item.get('Цена') or 'По запросу'
    body = item.get('Кузов') or 'Не указан'
    item_id = item.get('Артикул') or item.get('Номер') or '---'
    
    msg = (
        f"{title}\n"
        f"💰 Цена: {price} руб.\n\n"
        f"⛽ Модель ДВС: {model_engine}\n"
        f"🚗 Кузов: {body}\n"
        f"📄 Комментарий: {item.get('Комментарий', 'информация отсутствует')}\n"
        f"🔢 Артикул: {item_id}\n\n"
        f"📊 Результат {index + 1} из {len(results)}"
    )

    # --- 2. ПОДГОТОВКА КЛАВИАТУРЫ ---
    keyboard_data = get_nav_keyboard()

    # --- 3. ЗАГРУЗКА ФОТО ---
    photos_str = item.get('Фото') or item.get('Превью', '')
    photo_url = None
    if photos_str:
        photo_url = photos_str.split(',')[0].strip()

    if photo_url and photo_url.startswith('http'):
        try:
            response = requests.get(photo_url, timeout=20)
            response.raise_for_status()

            upload_url = vk.photos.getMessagesUploadServer()['upload_url']
            files = {'photo': ('engine.jpg', response.content)}
            upload_data = requests.post(upload_url, files=files, timeout=15).json()

            photo_data = vk.photos.saveMessagesPhoto(
                server=upload_data['server'],
                photo=upload_data['photo'],
                hash=upload_data['hash']
            )[0]
            
            attachment = f"photo{photo_data['owner_id']}_{photo_data['id']}"
            
            vk.messages.send(
                peer_id=peer_id,
                message=msg,
                attachment=attachment,
                keyboard=keyboard_data,
                random_id=get_random_id()
            )
            return 
        except Exception as e:
            logging.error(f"Ошибка загрузки фото двигателя: {e}")
    
    # Отправка без фото, если что-то пошло не так
    send_safe(peer_id, msg, keyboard=keyboard_data)

def show_item(peer_id, item):
    if 'Диаметр диска' in item:
        show_wheel(peer_id, item)
    elif 'VIN' in item:
        show_donor(peer_id, item)
    elif 'двигатель' in str(item.get('Наименование', '')).lower():
        show_engine(peer_id, item)
    else:
        show_part(peer_id, item)

def show_akpp(peer_id):
    results = user_results.get(peer_id, [])
    idx = user_index.get(peer_id, 0)

    if not results or not (0 <= idx < len(results)):
        send_safe(peer_id, "Данные АКПП не найдены.")
        return

    part = results[idx]
    
    # --- 1. ОСНОВНЫЕ ДАННЫЕ ИЗ ЛОКАЛЬНОЙ БАЗЫ АКПП ---
    title = part.get('Запчасть') or part.get('Наименование') or 'АКПП'
    price = part.get('Цена') or 'По запросу'
    marking = part.get('Маркировка') or part.get('Номер производителя') or 'Не указана'
    item_id = part.get('Номер товара') or part.get('Артикул') or '---'
    
    # --- 2. УМНЫЙ ПОИСК ФОТО ПО АРТИКУЛУ В ОНЛАЙН-БАЗЕ ---
    photo_url = None
    
    # Сначала проверяем, вдруг в самом файле АКПП уже есть ссылка
    photos_str = part.get('Превью') or part.get('Фото', '')
    
    if not photos_str or photos_str == "Не указано":
        # Если в АКПП пусто, ищем этот же артикул в основной базе запчастей (cache.parts)
        # Мы ищем совпадение по 'Номер товара' или 'Артикул'
        for main_part in cache.parts:
            main_id = main_part.get('Артикул') or main_part.get('Номер')
            if main_id == item_id:
                # Нашли! Берем фото из основной базы
                photos_str = main_part.get('Фото') or main_part.get('Превью', '')
                break

    # Извлекаем первый URL, если нашли хоть что-то
    if photos_str and photos_str != "Не указано":
        photo_url = photos_str.split(',')[0].strip()

    # --- 3. ФОРМИРУЕМ ТЕКСТ ---
    msg = (
        f"🕹 {title}\n"
        f"💰 Цена: {price} руб.\n\n"
        f"⚙️ Модель КПП: {marking}\n"
        f"🚗 Кузов: {part.get('Кузов', '---')}\n"
        f"🚜 Комплектация: {part.get('Комплектация', '---')}\n\n"
        f"🔢 ID товара: {item_id}\n\n"
        f"📊 Результат {idx + 1} из {len(results)}"
    )

    # --- 4. ЗАГРУЗКА И ОТПРАВКА (ЕДИНЫЙ БЛОК) ---
    keyboard_data = get_nav_keyboard()

    if photo_url and photo_url.startswith('http'):
        try:
            response = requests.get(photo_url, timeout=7)
            response.raise_for_status()

            upload_url = vk.photos.getMessagesUploadServer()['upload_url']
            files = {'photo': ('image.jpg', response.content)}
            upload_data = requests.post(upload_url, files=files, timeout=10).json()

            photo_data = vk.photos.saveMessagesPhoto(
                server=upload_data['server'],
                photo=upload_data['photo'],
                hash=upload_data['hash']
            )[0]
            
            attachment = f"photo{photo_data['owner_id']}_{photo_data['id']}"
            
            vk.messages.send(
                peer_id=peer_id,
                message=msg,
                attachment=attachment,
                keyboard=keyboard_data,
                random_id=get_random_id()
            )
            return 
        except Exception as e:
            logging.error(f"Ошибка подтягивания фото из онлайн-базы: {e}")

    # Если фото так и не нашли или произошла ошибка загрузки
    send_safe(peer_id, msg, keyboard=keyboard_data)

def show_wheel(peer_id):
    """Показывает карточку диска с защитой от дублирования."""
    # Пропускаем повторный вызов, если уже инициализируем поиск дисков
    if peer_id in initializing_wheels:
        logging.debug(f"Пропуск повторного вызова show_wheel для {peer_id} во время инициализации")
        return

    try:
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])
    
        if not results: 
            return

        # Упрощаем: берем напрямую по индексу. 
        # (Реверсируйте сам список results один раз при поиске, а не здесь)
        wheel = results[index]
        total_items = len(results)

        # Формируем текст карточки
        message = "🛞 Карточка диска:\n"
        message += f"Производитель: {safe_get(wheel, 'Производитель диска')}\n"
        message += f"Артикул: {safe_get(wheel, 'Артикул')}\n"
        message += f"Модель: {safe_get(wheel, 'Модель диска')}\n"
        message += f"Размер: {safe_get(wheel, 'Диаметр диска')}\n"

        price = safe_get(wheel, 'Цена')
        if price != "Не указано":
            message += f"Цена: {price}\n"

        link = safe_get(wheel, 'Ссылка')
        if link not in ("Не указано", "Нет ссылки"):
            message += f"Ссылка: {link}\n"

        # Нумерация: показываем позицию в отображаемом порядке (новые первыми)
        current_position = index + 1
        message += f"\n📊 {current_position} из {total_items}"

        # Создаём клавиатуру
        keyboard = VkKeyboard(one_time=False)

   
        keyboard.add_button("❤️ Добавить в избранное", color=VkKeyboardColor.POSITIVE)
        keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()

        
        # Третья строка — навигация только если есть несколько элементов
        if total_items > 1:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
            keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
            keyboard.add_line()

        # Четвёртая строка
        keyboard.add_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY)

        keyboard_data = keyboard.get_keyboard()

        # Отправка сообщения с фото и текстом
        photo_url = get_first_photo(wheel.get('Фото', ''))


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
                logging.warning(f"Ошибка загрузки фото: {e}")
                # Передаем keyboard_data (строку), а не объект клавиатуры
                send_safe(peer_id, message, keyboard=keyboard_data) 
            else:
                # Если фото нет вообще
                if not photo_url:
                    send_safe(peer_id, message, keyboard=keyboard_data)


    except Exception as e:
        logging.critical(f"ФАТАЛЬНАЯ ошибка в show_wheel для {peer_id}: {e}")
        send_safe(peer_id, "Произошла критическая ошибка при отображении диска. Обратитесь к администратору.")
        
def show_donor(peer_id):
    """Показывает карточку донора с навигацией (без добавления в избранное)."""
    try:
        # Получаем текущие данные пользователя
        index = user_index.get(peer_id, 0)
        results = user_results.get(peer_id, [])

        # Проверяем, есть ли результаты поиска
        if not results:
            send_safe(peer_id, "Нет результатов поиска для отображения")
            return

        total_items = len(results)  # Объявляем переменную total_items

        # Проверяем корректность индекса
        if index < 0 or index >= total_items:
            # Если индекс вышел за границы, сбрасываем на первый элемент
            index = 0
            user_index[peer_id] = 0

        donor = results[index]
        current_position = index + 1  # Текущая позиция (1-based)

        # Формируем текст карточки
        message = "🚗 Карточка донора:\n"
        message += f"Номер донора: {safe_get(donor, 'Номер')}\n"
        message += f"Марка: {safe_get(donor, 'Марка')}\n"
        message += f"Модель: {safe_get(donor, 'Модель')}\n"
        message += f"Кузов: {safe_get(donor, 'Кузов')}\n"
        message += f"Цвет: {safe_get(donor, 'Цвет')}\n"
        message += f"Год: {safe_get(donor, 'Год')}\n"
        message += f"Двигатель: {safe_get(donor, 'Двигатель')}\n"
        message += f"VIN: {safe_get(donor, 'VIN')}\n"

        comment = safe_get(donor, 'Комментарий')
        if comment != "Не указано":
            message += f"Комментарий: {comment}\n"

        link = safe_get(donor, 'Ссылка')
        if link not in ("Не указано", "Нет ссылки"):
            message += f"Ссылка: {link}\n"

        # Добавляем информацию о позиции в результатах
        message += f"\n📊 {current_position} из {total_items}"

        # Создаём клавиатуру
        keyboard = VkKeyboard(one_time=False)

        # Первая строка: навигация (только если есть несколько элементов)
        if total_items > 1:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
            keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
            keyboard.add_line()

        # Вторая строка: дополнительные действия
        keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY)

        keyboard_data = keyboard.get_keyboard()

        # Отправка сообщения с фото и текстом
        photo_url = get_first_photo(donor.get('Фото', ''))

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
                logging.warning(f"Ошибка загрузки фото (доноры): {e}. Отправляем только текст.")
                send_safe(peer_id, message, keyboard=keyboard)
        else:
            send_safe(peer_id, message, keyboard=keyboard)

    except Exception as e:
        logging.critical(f"ФАТАЛЬНАЯ ошибка в show_donor для {peer_id}: {e}")
        send_safe(peer_id, "Произошла критическая ошибка при отображении донора. Обратитесь к администратору.")

def show_favorite_card(peer_id):
    try:
        # DEBUG
        print(f"[DEBUG] peer_id={peer_id}, user_results keys={list(user_results.keys())}")
        results = user_results.get(peer_id, [])
        print(f"[DEBUG] results={results}")
        
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
            message += f"Ссылка: {link}\n"
        message += f"\n📊 {current_position} из {total_items}"

        # Создаём клавиатуру с соблюдением лимитов VK
        keyboard = VkKeyboard(one_time=False)

        # Первая строка: 2 кнопки
        keyboard.add_button("🗑 Удалить", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_button("🏠 Меню", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()  # Переход на новую строку

        # Вторая строка: навигация (только если есть несколько элементов)
        if total_items > 1:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
            keyboard.add_button("➡️ Вперед", color=VkKeyboardColor.PRIMARY)
            keyboard.add_line()  # Новая строка

        # Третья строка: кнопка обновления
        keyboard.add_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY)

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
                logging.warning(f"Ошибка фото в избранном: {e}. Отправляем текст.")
                send_safe(peer_id, message, keyboard=keyboard)  # Передаём объект клавиатуры, а не JSON
        else:
            send_safe(peer_id, message, keyboard=keyboard)  # Аналогично — объект клавиатуры

    except Exception as e:
        logging.error(f"Критическая ошибка в show_favorite_card: {e}")
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
    peer_id = str(peer_id)

    if peer_id not in user_favorites:
        user_favorites[peer_id] = []

    item_id = get_item_id(item)

    # проверка на дубликат
    for fav in user_favorites[peer_id]:
        if get_item_id(fav) == item_id:
            send_safe(peer_id, "ℹ️ Уже есть в избранном.")
            return

    user_favorites[peer_id].append(item)
    save_favorites()

    send_safe(peer_id, "✅ Добавлено в избранное!")

def show_favorites(peer_id):
    peer_id = str(peer_id)
    favs = user_favorites.get(peer_id, [])

    if not favs:
        send_safe(peer_id, "❌ Избранное пусто.")
        return

    user_state[peer_id] = {
        "mode": "favorites",
        "index": 0
    }

    show_favorite_item(peer_id)

def show_favorite_item(peer_id):
    peer_id = str(peer_id)
    state = user_state.get(peer_id, {})
    index = state.get("index", 0)

    favs = user_favorites.get(peer_id, [])
    item = favs[index]

    if 'Диаметр диска' in item:
        show_wheel(peer_id)
    elif 'VIN' in item:
        show_donor(peer_id)
    elif 'двигатель' in str(item.get('Наименование', '')).lower():
        show_engine(peer_id)
    else:
        show_part(peer_id)

    keyboard = VkKeyboard(inline=False)
    keyboard.add_button("⬅️", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("➡️", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("❌ Удалить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("🔙 Назад", color=VkKeyboardColor.SECONDARY)

    send_safe(peer_id, message, keyboard)

def remove_favorite(peer_id):
    peer_id = str(peer_id)
    state = user_state.get(peer_id, {})
    index = state.get("index", 0)

    favs = user_favorites.get(peer_id, [])

    if not favs:
        send_safe(peer_id, "❌ Нечего удалять.")
        return

    favs.pop(index)

    if index >= len(favs):
        index = max(0, len(favs) - 1)

    user_state[peer_id]["index"] = index

    save_favorites()

    send_safe(peer_id, "🗑 Удалено!")

    if favs:
        show_favorite_item(peer_id)
    else:
        send_safe(peer_id, "📭 Избранное теперь пусто.")

def handle(event):
    peer_id = event.obj.message['peer_id']
    text = event.obj.message['text']
    text_lower = text.lower().strip()

    state = user_state.get(peer_id, {})
    if not isinstance(state, dict):
        state = {}

    mode = state.get("mode")

    # ========= ГЛАВНОЕ МЕНЮ =========
    if text_lower in ["🏠 главное меню", "меню", "главное меню", "start"]:
        user_state[peer_id] = {}
        user_results.pop(peer_id, None)
        user_index.pop(peer_id, None)
        send_safe(peer_id, "🏠 Главное меню", keyboard=get_main_keyboard())
        return

    # ========= ИЗБРАННОЕ =========
    if text_lower == "❤️ избранное":
        show_favorites(peer_id)
        return

    if text_lower == "❤️ добавить в избранное":
        results = user_results.get(peer_id, [])
        index = user_index.get(peer_id, 0)

        if results:
            add_to_favorites(peer_id, results[index])
        else:
            send_safe(peer_id, "❌ Нет товара.")
        return

    # ========= НАВИГАЦИЯ В ИЗБРАННОМ =========
    if mode == "favorites":
        favs = user_favorites.get(str(peer_id), [])

        if not favs:
            send_safe(peer_id, "❌ Избранное пусто")
            return

        if text_lower == "➡️":
            state["index"] = (state.get("index", 0) + 1) % len(favs)
            show_favorite_item(peer_id)
            return

        if text_lower == "⬅️":
            state["index"] = (state.get("index", 0) - 1) % len(favs)
            show_favorite_item(peer_id)
            return

        if text_lower == "❌ удалить":
            remove_favorite(peer_id)
            return

        if text_lower == "🔙 назад":
            user_state.pop(peer_id, None)
            send_safe(peer_id, "↩️ В меню", get_main_keyboard())
            return

    # ========= ОБЫЧНАЯ НАВИГАЦИЯ =========
    if text_lower in ["➡️ вперед", "⬅️ назад"]:
        results = user_results.get(peer_id, [])

        if not results:
            return

        idx = user_index.get(peer_id, 0)

        if text_lower == "➡️ вперед":
            idx = (idx + 1) % len(results)
        else:
            idx = (idx - 1) % len(results)

        user_index[peer_id] = idx
        item = results[idx]

        if 'Диаметр диска' in item:
            show_wheel(peer_id)
        elif 'VIN' in item:
            show_donor(peer_id)
        elif 'двигатель' in str(item.get('Наименование', '')).lower():
            show_engine(peer_id)
        elif mode == "akpp_view":
            show_akpp(peer_id)
        else:
            show_part(peer_id)

        return

    # ========= СОСТОЯНИЯ ВВОДА =========

    if mode == "await_engine_number":
        results = cache.get_engines(text)

        if results:
            user_results[peer_id] = results
            user_index[peer_id] = 0
            user_state[peer_id] = {"mode": "engine_view"}
            show_engine(peer_id)
        else:
            send_safe(peer_id, "❌ Двигатель не найден")
        return

    if mode == "wait_part_number":
        query = normalize_query(text)
        results = cache.search_parts(query)

        if results:
            user_results[peer_id] = results
            user_index[peer_id] = 0
            user_state[peer_id] = {"mode": "parts"}
            show_part(peer_id)
        else:
            user_state[peer_id] = {"watch_query": query}
            send_safe(peer_id, f"❌ '{query}' не найден", keyboard=get_watch_keyboard())
        return

    if mode == "wheels":
        results = cache.search_wheels(text)

        if results:
            user_results[peer_id] = results
            user_index[peer_id] = 0
            show_wheel(peer_id)
        else:
            send_safe(peer_id, "❌ Диски не найдены")
        return

    # ========= АКПП =========

    if text_lower == "🕹 акпп":
        user_state[peer_id] = {"mode": "await_akpp_body"}
        send_safe(peer_id, "Введите кузов (например 211):")
        return

    if mode == "await_akpp_body":
        body = "".join(filter(str.isdigit, text)) or text.upper()

        user_state[peer_id] = {
            "mode": "await_akpp_drive",
            "body": body
        }

        kb = VkKeyboard(one_time=True)
        kb.add_button("Задний", color=VkKeyboardColor.PRIMARY)
        kb.add_button("Полный", color=VkKeyboardColor.PRIMARY)
        kb.add_line()
        kb.add_button("Передний", color=VkKeyboardColor.SECONDARY)

        send_safe(peer_id, f"Кузов {body}. Укажите привод:", keyboard=kb.get_keyboard())
        return

    if mode == "await_akpp_drive":
        drive = text.lower()
        body = state.get("body")

        results = []

        for part in cache.akpp_base:
            name = str(part).lower()

            if body in name and drive[:4] in name and "акпп" in name:
                results.append(part)

        if results:
            user_results[peer_id] = results
            user_index[peer_id] = 0
            user_state[peer_id] = {"mode": "akpp_view"}
            show_akpp(peer_id)
        else:
            send_safe(peer_id, "❌ АКПП не найдена")
            user_state[peer_id] = {"mode": "parts_menu"}
        return

    # ========= МЕНЮ =========

    if text_lower == "🚗 запчасти":
        user_state[peer_id] = {"mode": "parts_menu"}
        send_safe(peer_id, "Выберите раздел:", keyboard=get_parts_menu_keyboard())
        return

    if text_lower == "⚙️ двигатель":
        user_state[peer_id] = {"mode": "await_engine_number"}
        send_safe(peer_id, "Введите номер двигателя:")
        return

    if text_lower == "🔍 поиск по номеру":
        user_state[peer_id] = {"mode": "wait_part_number"}
        send_safe(peer_id, "Введите номер детали:")
        return

    if text_lower == "🛞 диски":
        user_state[peer_id] = {"mode": "wheels"}
        send_safe(peer_id, "Введите размер:")
        return

    if text_lower == "🚘 доноры":
        results = cache.get_latest_donors(limit=15)

        if results:
            user_results[peer_id] = results
            user_index[peer_id] = 0
            user_state[peer_id] = {"mode": "donors"}
            show_donor(peer_id)
        else:
            send_safe(peer_id, "Нет данных")
        return
# Запуск бота
def run_bot():
    print("🔥 VK BOT ULTRA ЗАПУЩЕН")
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                handle(event)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        time.sleep(5)
        run_bot()

def auto_restart():
    """Функция для бесконечного перезапуска бота при ошибках"""
    while True:
        try:
            run_bot()
        except Exception as e:
            logging.error(f"Бот упал. Перезапуск через 10 секунд... Ошибка: {e}")
            time.sleep(10)

if __name__ == "__main__":
    init_files()
    # Загружаем данные из файлов в глобальные переменные
    user_favorites.update(load_json(FAV_FILE))
    # ИСПРАВЛЕНО: используем WATCHLIST_FILE вместо WATCH_FILE
    watchlist.update(load_json(WATCHLIST_FILE)) 
    
    print(f"✅ Данные загружены. Избранное: {len(user_favorites)}")
    auto_restart()
    
   
