import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models import User, PushSubscription
from app.utils.push_service import send_push

router = APIRouter()


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


class PushTestRequest(BaseModel):
    message: str = "测试推送"


@router.get("/vapid-public-key")
async def get_vapid_public_key(current_user: User = Depends(get_current_user)):
    """获取 VAPID 公钥（前端订阅推送需要）"""
    if not settings.VAPID_PUBLIC_KEY:
        return {"enabled": False, "public_key": None}
    return {"enabled": True, "public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe", status_code=201)
async def subscribe(
    payload: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存推送订阅"""
    # 同一 endpoint 去重
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == payload.endpoint,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # 更新 keys
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    else:
        sub = PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )
        db.add(sub)
    await db.commit()
    return {"success": True}


@router.delete("/subscribe")
async def unsubscribe(
    endpoint: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消推送订阅"""
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == endpoint,
        )
    )
    await db.commit()
    return {"success": True}


@router.post("/test")
async def test_push(
    payload: PushTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """给自己发一条测试推送"""
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == current_user.id)
    )
    subs = result.scalars().all()
    if not subs:
        raise HTTPException(status_code=400, detail="尚未订阅推送")

    sent = 0
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        message = json.dumps({"title": "饭饭之交", "body": payload.message})
        if send_push(subscription_info, message):
            sent += 1

    if sent == 0 and not settings.VAPID_PUBLIC_KEY:
        return {"success": True, "simulated": True, "message": "未配置 VAPID，已模拟推送（见日志）"}

    return {"success": sent > 0, "sent_count": sent}


async def notify_user(db: AsyncSession, user_id: int, body: str):
    """向指定用户的所有订阅发送推送（供订单模块调用）"""
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    subs = result.scalars().all()
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        message = json.dumps({"title": "饭饭之交", "body": body})
        send_push(subscription_info, message)


async def notify_feeders(db: AsyncSession, body: str):
    """向所有饲养员/店长发送推送（新订单时调用）"""
    result = await db.execute(
        select(User).where((User.is_feeder == True) | (User.is_admin == True))
    )
    feeders = result.scalars().all()
    for feeder in feeders:
        await notify_user(db, feeder.id, body)
