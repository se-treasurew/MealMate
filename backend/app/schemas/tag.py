from pydantic import BaseModel, Field


class TagBase(BaseModel):
    name: str = Field(..., max_length=50)


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    id: int

    class Config:
        from_attributes = True
