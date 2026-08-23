from pydantic import BaseModel, Field
from typing import Annotated, Optional
from datetime import datetime

from app.schemas.tag import TagResponse


class DishImageResponse(BaseModel):
    id: int
    image_path: str
    thumbnail_path: Optional[str] = None
    sort_order: int = 0

    class Config:
        from_attributes = True


class DishLinkBase(BaseModel):
    url: str = Field(..., max_length=500)
    title: Optional[str] = Field(None, max_length=200)


class DishLinkResponse(DishLinkBase):
    id: int

    class Config:
        from_attributes = True


# 标签名：非空由路由层 strip 后过滤，这里限制长度与单个名称一致
TagName = Annotated[str, Field(max_length=50)]


class DishBase(BaseModel):
    name: str = Field(..., max_length=100)
    category_id: int
    description: Optional[str] = None
    notes: Optional[str] = None
    status: str = "active"  # active / inactive


class DishCreate(DishBase):
    links: list[DishLinkBase] = []
    tag_names: list[TagName] = Field(default_factory=list, max_length=10)


class DishUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    category_id: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    links: Optional[list[DishLinkBase]] = None
    # None 表示不动标签；传 [] 表示清空
    tag_names: Optional[list[TagName]] = Field(None, max_length=10)


class DishResponse(DishBase):
    id: int
    created_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    images: list[DishImageResponse] = []
    links: list[DishLinkResponse] = []
    tags: list[TagResponse] = []
    # 聚合评分：无评分时 avg_rating 为 None，前端显示"暂无评分"
    avg_rating: Optional[float] = None
    rating_count: int = 0

    class Config:
        from_attributes = True
