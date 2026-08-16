import json
from typing import List
from app.models import Product


# Sanitize at the boundary so the rest of SmartCart stays safe
def clean_price(price: str | float | None) -> float:
    if price is None:
        return 0.0
    try:
        return float(str(price).replace("$", "").strip())
    except ValueError:
        return 0.0


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

raw_flyer_data = [
    {"item": "Ground Chicken", "store": "FreshCo", "regular_price": 4.77, "member_price": 3.77, "category": "Meat"},
    {"item": "Raspberries", "store": "FoodBasics", "regular_price": 1.98, "member_price": 1.68, "category": "Produce"},
    {"item": "Pasta Sauce", "store": "Walmart", "regular_price": 3.47, "member_price": None, "category": "Pantry"},
    {"item": "Seedless Watermelon", "store": "FreshCo", "regular_price": 3.77, "member_price": None, "category": "Produce"},
]

import pandas as pd


def clean_flyer_dataframe(raw_data: list[dict]) -> pd.DataFrame:
    df=pd.DataFrame(raw_data)
    df['member_price'] = df['member_price'].fillna(df['regular_price'])
    df['savings'] = df['regular_price'] - df['member_price']
    df['store'] = df['store'].astype('category')
    return df

clean_flyer_dataframe(
    raw_data=raw_flyer_data
)