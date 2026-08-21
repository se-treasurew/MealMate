from pydantic import BaseModel, Field
from datetime import datetime


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=4, max_length=50)
    password: str = Field(..., min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # 首次登录/被重置密码后为 True，前端需强制引导改密
    must_change_password: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    nickname: str | None
    avatar_url: str | None
    is_admin: bool
    is_feeder: bool
    is_active: bool = True
    must_change_password: bool = False

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    """更新个人资料：昵称 + 头像（预设头像相对路径或上传后的路径）"""
    nickname: str | None = Field(None, max_length=50)
    avatar_url: str | None = Field(None, max_length=255)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=50)
