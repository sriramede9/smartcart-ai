from dataclasses import dataclass

@dataclass
class Product:
    id: str
    name: str
    original_price: float
    sale_price: float
    store: str
    category: str

    @property
    def discount_percentage(self) -> float:
        if self.original_price <= 0:
            return 0.0
        discount = ((self.original_price - self.sale_price) / self.original_price) * 100
        return round(discount, 2)