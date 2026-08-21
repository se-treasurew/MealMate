from pydantic import BaseModel, Field
from datetime import datetime


class UserCreate(BaseModel):
    """管理员创建账号（不允许创建管理员）"""
    username: str = Field(..., min_length=4, max_length=50)
    password: str = Field(..., min_length=6, max_length=50)
    nickname: str | None = Field(None, max_length=50)
    is_feeder: bool = False


class UserFeederUpdate(BaseModel):
    """授予/收回饲养员权限"""
    is_feeder: bool


class UserStatusUpdate(BaseModel):
    """启用/禁用账号"""
    is_active: bool


class PasswordReset(BaseModel):
    """管理员重置密码"""
    password: str = Field(..., min_length=6, max_length=50)


class UserListItem(BaseModel):
    id: int
    username: str
    nickname: str | None
    avatar_url: str | None
    is_admin: bool
    is_feeder: bool
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True
