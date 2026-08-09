import json
from typing import List
from app.models import Product


# Sanitize at the boundary so the rest of SmartCart stays safe
def clean_price(price):
    return float(str(price).replace("$", "").strip())


def load_products(file_path: str) -> List[Product]:
    with open(file_path, "r") as f:
        raw_data = json.load(f)
    
    products = []
    for item in raw_data:
        
        products.append(
            Product(
                id=str(item["id"]),
                name=item["name"],
                original_price=clean_price(item["original_price"]),
                sale_price=clean_price(item["sale_price"]),
                store=item["store"],
                category=item["category"]
            )
        )
    return products