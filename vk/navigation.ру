from storage.session import get_session
from vk.cards import send_card

def next_item(vk, user_id):
    session = get_session(user_id)

    if not session["results"]:
        return

    session["index"] += 1
    if session["index"] >= len(session["results"]):
        session["index"] = 0

    item = session["results"][session["index"]]
    send_card(vk, user_id, item, session["index"], len(session["results"]))


def prev_item(vk, user_id):
    session = get_session(user_id)

    if not session["results"]:
        return

    session["index"] -= 1
    if session["index"] < 0:
        session["index"] = len(session["results"]) - 1

    item = session["results"][session["index"]]
    send_card(vk, user_id, item, session["index"], len(session["results"]))
