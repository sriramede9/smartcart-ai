# app/search.py
from typing import List
from app.models import Product
from app.loader import load_products
import os

def search_products(products: List[Product], query: str, max_price: float = None) -> List[Product]:
    results = []
    for p in products:
        matches_query = query.lower() in p.name.lower()
        matches_price = max_price is None or p.sale_price <= max_price
        if matches_query and matches_price:
            results.append(p)
    return results


products_list=load_products(os.getcwd()+"/data/flyers.json")

search_products(products=products_list,query='Honeycrisp Apples',max_price=1.45)
