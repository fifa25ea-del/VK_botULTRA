sessions = {}

def get_session(user_id):
    if user_id not in sessions:
        sessions[user_id] = {
            "results": [],
            "index": 0,
            "mode": None,
            "favorites": []
        }
    return sessions[user_id]

def add_favorite(user_id):
    session = get_session(user_id)
    item = session["results"][session["index"]]

    session["favorites"].append(item)
