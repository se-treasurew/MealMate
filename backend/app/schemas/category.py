from pydantic import BaseModel, Field
from typing import Optional


class CategoryBase(BaseModel):
    name: str = Field(..., max_length=50)
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    sort_order: Optional[int] = None


class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True
