def normalize_query(q):
    q = q.lower()
    q = q.replace("а", "a")  # русская → английская
    return q

def find_part(query, data):
    query = query.lower().replace("а", "a")

    results = []

    for item in data:
        text = (
            item["article"] +
            item["name"] +
            item["brand"] +
            item["model"]
        ).lower()

        if query in text:
            results.append(item)

    return results[:50]
