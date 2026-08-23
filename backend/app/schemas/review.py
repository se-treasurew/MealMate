from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReviewItemCreate(BaseModel):
    """单个菜品的评价内容"""

    dish_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=500)


class ReviewCreate(BaseModel):
    """批量提交订单内各菜品的评价"""

    items: list[ReviewItemCreate] = Field(..., min_length=1)


class ReviewResponse(BaseModel):
    id: int
    dish_id: int
    order_id: int
    user_id: int
    user_nickname: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewItemStatus(BaseModel):
    """订单评价提交结果：每个菜品的落库情况"""

    dish_id: int
    review_id: int
    rating: int
    comment: Optional[str] = None
    updated: bool  # False=首次评价，True=修改已有评价


class ReviewSubmitResponse(BaseModel):
    order_id: int
    items: list[ReviewItemStatus]
