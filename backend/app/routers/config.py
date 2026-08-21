from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, SystemConfig

router = APIRouter()

# 角色名称相关的配置 key
ROLE_KEYS = {
    "admin": "role_name_admin",
    "feeder": "role_name_feeder",
    "diner": "role_name_diner",
}

# 前端可公开读取的配置 key 白名单
PUBLIC_KEYS = list(ROLE_KEYS.values())


class ConfigUpdate(BaseModel):
    value: str


@router.get("")
async def get_config(
    db: AsyncSession = Depends(get_db),
):
    """获取公开的系统配置（无需登录，如角色显示名称）"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key.in_(PUBLIC_KEYS))
    )
    configs = result.scalars().all()
    return {c.key: c.value for c in configs}


@router.put("/{key}")
async def update_config(
    key: str,
    payload: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新系统配置（仅店长）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅店长可修改系统配置")

    if key not in PUBLIC_KEYS:
        raise HTTPException(status_code=400, detail="不允许修改此配置项")

    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    if not config:
        config = SystemConfig(key=key, value=payload.value)
        db.add(config)
    else:
        config.value = payload.value

    await db.commit()
    return {"key": key, "value": config.value}
