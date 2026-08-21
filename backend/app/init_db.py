import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine, Base
from app.models import User, DishCategory, Tag, SystemConfig
from app.core.security import get_password_hash
from app.core.config import settings


def get_initial_admin_password() -> str:
    """读取初始管理员密码；禁止使用缺失或过短的启动口令。"""
    password = settings.ADMIN_INITIAL_PASSWORD
    if not password or len(password) < 6:
        raise RuntimeError("必须设置至少 6 位的 ADMIN_INITIAL_PASSWORD")
    return password


async def init_db():
    """创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表已创建")


async def create_seed_data():
    """创建种子数据"""
    async with AsyncSessionLocal() as session:
        # 1. 创建初始店长账号
        existing_admin = await session.execute(
            select(User).where(User.username == "admin")
        )
        if not existing_admin.scalar_one_or_none():
            initial_admin_password = get_initial_admin_password()
            admin = User(
                username="admin",
                password_hash=get_password_hash(initial_admin_password),
                nickname="店长",
                is_admin=True,
                is_feeder=True,
                must_change_password=True,
            )
            session.add(admin)
            print("✅ 已创建初始店长账号: admin（密码来自环境变量）")

        # 2. 创建预设分类
        categories = ["荤菜", "素菜", "汤", "主食", "凉菜", "其他"]
        for idx, name in enumerate(categories):
            existing = await session.execute(
                select(DishCategory).where(DishCategory.name == name)
            )
            if not existing.scalar_one_or_none():
                category = DishCategory(name=name, sort_order=idx)
                session.add(category)
        print(f"✅ 创建预设分类: {', '.join(categories)}")

        # 3. 创建预设标签
        tag_names = ["辣", "素食", "快手菜", "家常菜", "凉菜"]
        for name in tag_names:
            existing = await session.execute(
                select(Tag).where(Tag.name == name)
            )
            if not existing.scalar_one_or_none():
                session.add(Tag(name=name))
        print(f"✅ 创建预设标签: {', '.join(tag_names)}")

        # 4. 创建系统配置
        configs = [
            {"key": "role_name_admin", "value": "店长"},
            {"key": "role_name_feeder", "value": "饲养员"},
            {"key": "role_name_diner", "value": "饭团"},
        ]
        for cfg in configs:
            existing = await session.execute(
                select(SystemConfig).where(SystemConfig.key == cfg["key"])
            )
            if not existing.scalar_one_or_none():
                config = SystemConfig(key=cfg["key"], value=cfg["value"])
                session.add(config)
        print("✅ 创建系统配置: 角色显示名称")

        await session.commit()
        print("\n🎉 种子数据创建完成！")


async def main():
    print("开始初始化数据库...\n")
    await init_db()
    await create_seed_data()


if __name__ == "__main__":
    asyncio.run(main())
