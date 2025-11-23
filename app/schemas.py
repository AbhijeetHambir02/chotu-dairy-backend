from pydantic import BaseModel
from datetime import datetime, date


# ---------- Product Schemas ----------
class ProductBase(BaseModel):
    product_name: str
    price: float

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int

    class Config:
        from_attributes = True


# ---------- Sales Schemas ----------
class SalesBase(BaseModel):
    name: str
    product_id: int
    quantity: int
    date: date
    total_price: float

class SalesCreate(SalesBase):
    pass

class CreateSalesResponse(SalesBase):
    id: int
    
class SalesResponse(SalesBase):
    id: int
    price: float

    class Config:
        from_attributes = True