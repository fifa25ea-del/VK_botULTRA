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
current_message_id

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

    return keyboard.get_keyboard()

def get_navigation_keyboard(index, total):
    """Создает клавиатуру с кнопками навигации"""
    keyboard = VkKeyboard(one_time=False)

    # Создаем невидимый символ (Zero-Width Space)
    # Он не виден пользователю, но для VK это валидный символ.
    invisible_char = '\u200B' 

    # --- Блок кнопок "Назад" и "Вперёд" ---
    # Используем невидимый символ для заглушек

    if index > 0:
        keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
    else:
        # Кнопка-заглушка, которая выглядит как пустая
        keyboard.add_button(invisible_char, color=VkKeyboardColor.SECONDARY)

    keyboard.add_line() # Перенос на следующую строку для колонки кнопок

    if index < total - 1:
        keyboard.add_button("➡️ Вперёд", color=VkKeyboardColor.PRIMARY)
    else:
        keyboard.add_button(invisible_char, color=VkKeyboardColor.SECONDARY)

    # --- Блок возврата в меню ---
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
def send_message(peer_id, text, keyboard=None, save_id=True):
    """Отправляет сообщение и сохраняет его ID для последующего редактирования"""
    try:
        # Используем метод send, чтобы получить ID
        sent_message = vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=0, # Для метода send random_id обязателен
            keyboard=keyboard if keyboard else get_main_keyboard()
        )
        
        # Если флаг save_id включен, сохраняем ID в наш словарь
        if save_id:
            current_message_id[peer_id] = sent_message

        logging.info(f"Сообщение успешно отправлено (ID: {sent_message})")
        
    except Exception as e:
        logging.error(f"Ошибка отправки/редактирования сообщения: {e}")
        # Попытка отправить простое сообщение без клавиатуры в случае сбоя
        try:
            vk.messages.send(
                peer_id=peer_id,
                message="Произошла ошибка при отправке сообщения. Попробуйте позже.",
                random_id=0
            )
        except:
            pass

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
        """Поиск всех деталей с точным совпадением номера или артикула"""
        query = query.strip().lower()
        results = []
        for part in self.parts:
            # Проверяем и номер, и артикул (на случай, если пользователь ввел артикул)
            part_number = safe_get(part, 'Номер', '').lower()
            part_article = safe_get(part, 'Артикул', '').lower()
            
            if query == part_number or query == part_article:
                results.append(part)
        return results

    def search_wheels(self, query):
        """Поиск дисков по производителю"""
        query = query.lower()
        results = []
        for wheel in self.wheels:
            if query in wheel.get('Диаметр диска', '').lower():
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
        send_message(peer_id, message)
    except Exception as e:
        logging.error(f"Критическая ошибка в show_part_info: {e}")
        send_message(peer_id, "Произошла ошибка при получении информации о детали")

def show_donor_info(peer_id, donor):
    """Показывает подробную информацию о доноре"""
    try:
        message = "🚘 Информация о доноре:\n"
        message += f"Марка: {donor.get('Марка', 'Не указана')}\n"
        message += f"Модель: {donor.get('Модель', 'Не указана')}\n"
        message += f"Год выпуска: {donor.get('Год', 'Не указан')}\n"
        message += f"Цена: {donor.get('Цена', 'Не указана')}\n"
        message += f"Пробег: {donor.get('Пробег', 'Не указан')}"
        send_message(peer_id, message)
    except Exception as e:
        logging.error(f"Ошибка при отображении информации о доноре: {e}")
        send_message(peer_id, "Произошла ошибка при получении информации о доноре")

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
        send_message(peer_id, message)
    except Exception as e:
        logging.error(f"Ошибка при отображении информации о диске: {e}")
        send_message(peer_id, "Произошла ошибка при получении информации о диске")

def send_message(peer_id, text, keyboard=None, save_id=True):
    """Отправляет сообщение и сохраняет его ID для последующего редактирования"""
    try:
        # Используем метод send, чтобы получить ID
        sent_message = vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=0, # Для метода send random_id обязателен
            keyboard=keyboard if keyboard else get_main_keyboard()
        )
        
        # Если флаг save_id включен, сохраняем ID в наш словарь
        if save_id:
            current_message_id[peer_id] = sent_message

        logging.info(f"Сообщение успешно отправлено (ID: {sent_message})")
        
    except Exception as e:
        logging.error(f"Ошибка отправки/редактирования сообщения: {e}")
        # Попытка отправить простое сообщение без клавиатуры в случае сбоя
        try:
            vk.messages.send(
                peer_id=peer_id,
                message="Произошла ошибка при отправке сообщения. Попробуйте позже.",
                random_id=0
            )
        except:
            pass

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
            send_message(peer_id, message)
        else:
            send_message(peer_id, "Нет данных для отображения")
    except Exception as e:
        logging.error(f"Ошибка при показе донора: {e}")
        send_message(peer_id, "Произошла ошибка при отображении донора")

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
        send_message(peer_id, "Добавлено в избранное!")
    else:
        send_message(peer_id, "Уже в избранном!")

def show_favorites(peer_id):
    fav_items = favorites.get(peer_id, [])
    if fav_items:
        message = "❤️ Избранное:\n"
        for i, item in enumerate(fav_items, 1):
            message += f"{i}. {item.get('Название', 'Не указано')}\n"
        send_message(peer_id, message)
    else:
        send_message(peer_id, "Избранное пустое")


def handle(event):
    msg = event.obj.message
    peer_id = msg['peer_id']
    text = msg.get('text', '').strip()
    
    # --- НОВЫЙ БЛОК: Обработка кнопок навигации ---
    current_state = user_state.get(peer_id)
    
    # Проверяем нажатие кнопок только если мы находимся в режиме просмотра запчастей
    if current_state == "parts":
        if text == "⬅️ Назад":
            user_index[peer_id] = max(0, user_index.get(peer_id, 0) - 1)
            show_part(peer_id)
            return
            
        if text == "➡️ Вперёд":
            total_results = len(user_results.get(peer_id, []))
            user_index[peer_id] = min(total_results - 1, user_index.get(peer_id, 0) + 1)
            show_part(peer_id)
            return
            
        if text == "🏠 Главное меню":
            user_state[peer_id] = None
            send_message(peer_id, "Возврат в главное меню.", keyboard=get_main_keyboard())
            return

    # --- СТАРЫЙ БЛОК: Обработка ввода пользователя ---
    text_lower = text.lower()
    
    if text_lower in ["🚗 запчасти", "запчасти"]:
        user_state[peer_id] = "parts"
        send_message(peer_id, "Введите номер детали:", keyboard=get_main_keyboard())
        return

    # ... остальные кнопки (диски, доноры) остаются без изменений ...

    # Блок поиска (остался почти прежним)
    if current_state == "parts":
        results = cache.search_parts(text)
        if results:
            user_results[peer_id] = results
            user_index[peer_id] = 0 # Всегда начинаем с первого элемента при новом поиске
            show_part(peer_id) # Покажем первый результат с новой клавиатурой
        else:
            send_message(peer_id, "❌ Детали не найдены. Попробуйте другой запрос.")
        
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
