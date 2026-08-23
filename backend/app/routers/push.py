"""已停用的 Web Push 兼容接口。

保留一个版本周期，避免旧版 PWA 请求出现 404。所有处理均立即返回，
不读取订阅表、不写数据库，也不访问任何外部推送服务。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User

router = APIRouter()


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


class PushTestRequest(BaseModel):
    message: str = "测试推送"


def disabled_response() -> dict:
    return {
        "success": False,
        "enabled": False,
        "message": "推送功能已停用",
    }


@router.get("/vapid-public-key")
async def get_vapid_public_key(current_user: User = Depends(get_current_user)):
    return {"enabled": False, "public_key": None}


@router.post("/subscribe", status_code=201)
async def subscribe(
    payload: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del payload, db, current_user
    return disabled_response()


@router.delete("/subscribe")
async def unsubscribe(
    endpoint: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del endpoint, db, current_user
    return disabled_response()


@router.post("/test")
async def test_push(
    payload: PushTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del payload, db, current_user
    return disabled_response()


async def notify_user(db: AsyncSession, user_id: int, body: str) -> None:
    del db, user_id, body


async def notify_feeders(db: AsyncSession, body: str) -> None:
    del db, body
