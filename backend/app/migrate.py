"""幂等迁移：创建缺失的表，并为已有表补充缺失的列（SQLite ADD COLUMN）"""
import asyncio
from sqlalchemy import text
from app.core.database import engine, Base
from app.models import PushSubscription  # noqa: F401  确保模型注册到 Base.metadata
from app.models.user import User  # noqa: F401

# (表名, 列名, 建列 SQL)
# SQLite 的 ALTER TABLE ADD COLUMN 仅支持带默认值的简单列
MISSING_COLUMNS = [
    ("user", "is_active", "ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1"),
    (
        "user",
        "must_change_password",
        "ALTER TABLE user ADD COLUMN must_change_password BOOLEAN DEFAULT 0",
    ),
    (
        "user",
        "token_version",
        "ALTER TABLE user ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0",
    ),
]


async def main():
    async with engine.begin() as conn:
        # create_all 幂等，只创建不存在的表
        await conn.run_sync(Base.metadata.create_all)

        # 补充已有表缺失的列
        for table, column, ddl in MISSING_COLUMNS:
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in result.fetchall()}
            if column not in existing:
                await conn.execute(text(ddl))
                print(f"✅ 已为表 {table} 补充列 {column}")
            else:
                print(f"ℹ️ 表 {table} 已有列 {column}，跳过")

        # 将旧版后端预设头像路径迁移到前端静态资源路径。
        await conn.execute(
            text(
                "UPDATE user "
                "SET avatar_url = '/avatars/' || substr(avatar_url, 9) "
                "WHERE avatar_url LIKE 'presets/%.png'"
            )
        )

    print("✅ 迁移完成（表结构已确保最新）")


if __name__ == "__main__":
    asyncio.run(main())
