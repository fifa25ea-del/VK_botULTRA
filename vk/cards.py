import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def build_keyboard():
    kb = VkKeyboard(inline=True)

    kb.add_button("⬅️", color=VkKeyboardColor.PRIMARY)
    kb.add_button("➡️", color=VkKeyboardColor.PRIMARY)

    kb.add_line()
    kb.add_button("❤️", color=VkKeyboardColor.NEGATIVE)
    kb.add_button("📞 Менеджер", color=VkKeyboardColor.POSITIVE)

    return kb.get_keyboard()


def send_card(vk, user_id, item, index, total):
    text = (
        f"🔧 {name}\n"
        f"Артикул: {article}\n"
        f"Номер: {number}\n"
        f"{brand} {model}\n"
        f"💰 {price} ₽\n\n"
        f"({index+1}/{len(results)})"
    )

    attachment = item.get("photo", "")

    vk.messages.send(
        user_id=user_id,
        message=text,
        attachment=attachment,
        keyboard=build_keyboard(),
        random_id=0
    )
