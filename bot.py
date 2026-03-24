from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import vk_api
import os

# ===== ПЕРЕМЕННЫЕ =====
TOKEN = os.getenv("vk1.a.x9T8g9mSGkAbjr25wgv4J-Xkn_1KL8Yvw-OOocoeIaHsdOrzhU1zgtT5-UYYuOFX5m6xecF9UO8OkrFB4BuKgpqR7JkelZVqpV7w0jMu5kuU8OW8_gOz0uVi38MdsPe0ZcbxESB_7h6Kls-bu60aqU_1tHHrLl7hwuAtkMnK4jXcX6JH3dKP7RiAAn6feDfoRmAu5UfEBNkTJRB9JCokNw")        # Токен вашей группы
GROUP_ID = 236843733                       # Числовой ID вашей группы
ADMIN_ID = int(os.getenv("888230055", 0))   # Ваш VK ID для админ-команд

# ===== ИНИЦИАЛИЗАЦИЯ VK =====
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

print("🔥 VK BOT STARTED")

# ===== ФУНКЦИЯ ОТПРАВКИ СООБЩЕНИЯ =====
def send(peer_id, message):
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        random_id=0
    )

# ===== ОБРАБОТКА АДМИН-КОМАНД =====
def admin_command(user_id, text):
    if user_id != ADMIN_ID:
        return False
    if text == "/stats":
        send(user_id, "👥 Бот активен и слушает сообщения")
        return True
    return False

# ===== ОСНОВНОЙ ЦИКЛ LONGPOLL =====
for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        user_id = event.obj.from_id
        text = event.obj.text
        print(f"Новое сообщение от {user_id}: {text}")

        # Проверка админ-команд
        if admin_command(user_id, text):
            continue

        # Простой ответ на любое сообщение
        send(user_id, "Бот получил ваше сообщение ✅")
