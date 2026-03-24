import requests
import csv
import io
from config import PARTS_CSV, WHEELS_CSV, DONORS_CSV
from storage.cache import cache

def load_csv(url):
    r = requests.get(url)
    r.encoding = "cp1251"

    reader = csv.DictReader(io.StringIO(r.text), delimiter=";")

    data = []

    for row in reader:
        data.append({
            "article": row.get("Артикул", ""),
            "name": row.get("Наименование", ""),
            "brand": row.get("Марка", ""),
            "model": row.get("Модель", ""),
            "year": row.get("Год", ""),
            "number": row.get("Номер", ""),
            "price": row.get("Цена", "0"),
            "photo": row.get("Фото", "")
        })

    return data

def load_all():
    cache["parts"] = load_csv(PARTS_CSV)
    cache["wheels"] = load_csv(WHEELS_CSV)
    cache["donors"] = load_csv(DONORS_CSV)
