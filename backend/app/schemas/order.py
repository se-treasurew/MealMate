from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime


class OrderItemCreate(BaseModel):
    dish_id: int
    quantity: int = Field(..., ge=1)
    item_note: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: int
    dish_id: int
    dish_name: Optional[str] = None
    dish_image_path: Optional[str] = None
    dish_available: bool = False
    quantity: int
    item_note: Optional[str] = None

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    meal_date: date
    meal_type: str  # 早餐/午餐/晚餐/夜宵/自定义
    note: Optional[str] = None
    items: list[OrderItemCreate]


class OrderUpdate(BaseModel):
    status: Optional[str] = None  # pending/accepted/cooking/done/cancelled
    note: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    user_id: int
    user_nickname: Optional[str] = None
    meal_date: date
    meal_type: str
    status: str
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: list[OrderItemResponse] = []

    class Config:
        from_attributes = True
