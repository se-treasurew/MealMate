"""Web Push 推送服务

由于 pywebpush 在 Windows 上可能依赖加密库且家庭环境不一定有 VAPID 密钥，
本模块采用"软降级"策略：
- 若配置了 VAPID 密钥，则真正发送 Web Push 通知
- 若未配置，则仅在日志记录推送意图（不报错）

注意：pywebpush 的 vapid_private_key 若是字符串只走 `Vapid.from_string`（期望裸 base64，
完整 PEM 会解析失败报 header too long），因此配置约定为"私钥文件相对路径"，
本模块统一解析为绝对路径，让 pywebpush 走 `from_file` 分支。
"""
import logging
import os
from typing import Optional
from app.core.config import settings

logger = logging.getLogger("mealmate.push")

_webpush_available = False
try:
    from pywebpush import webpush, WebPushException
    _webpush_available = True
except ImportError:
    pass

# 项目 backend 目录（app/utils/push_service.py -> 上三级）
_BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def _vapid_configured() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def _resolve_vapid_key(key: str) -> str:
    """把 VAPID_PRIVATE_KEY 解析为 pywebpush 可用的值（文件绝对路径优先）"""
    stripped = key.strip()
    # PEM 字符串原样返回（pywebpush 的 from_string 实际不支持完整 PEM，故约定为文件路径）
    if stripped.startswith("-----BEGIN"):
        return key
    # 视为文件路径：解析为绝对路径（相对 backend 目录）
    if not os.path.isabs(stripped):
        candidate = os.path.join(_BACKEND_DIR, stripped)
        if os.path.isfile(candidate):
            return candidate
    return key


def send_push(
    subscription_info: dict,
    payload: str,
    title: str = "饭饭之交",
) -> bool:
    """
    发送 Web Push 通知。
    subscription_info: {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}
    返回是否发送成功。
    """
    if not _vapid_configured():
        logger.info(f"[Push 模拟] 未配置 VAPID，跳过实际推送。消息: {payload}")
        return False

    if not _webpush_available:
        logger.warning("pywebpush 未安装，无法发送推送")
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=_resolve_vapid_key(settings.VAPID_PRIVATE_KEY),
            vapid_claims={"sub": "mailto:admin@mealmate.local"},
        )
        return True
    except WebPushException as e:
        logger.warning(f"推送失败(WebPushException): {e}")
        return False
    except Exception as e:
        # 解析私钥/网络/序列化等任何异常都不应冒泡成 500，统一记日志降级
        logger.warning(f"推送失败(其他异常): {type(e).__name__}: {e}")
        return False
