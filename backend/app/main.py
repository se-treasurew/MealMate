from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
import os

app = FastAPI(title="饭饭之交 API", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
if not os.path.exists(settings.UPLOAD_DIR):
    os.makedirs(settings.UPLOAD_DIR)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
async def root():
    return {"message": "饭饭之交 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


# 注册路由
from app.routers import auth, categories, dishes, tags, orders, push, config, users, reviews

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(dishes.router, prefix="/api/dishes", tags=["dishes"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(push.router, prefix="/api/push", tags=["push"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(reviews.router, prefix="/api", tags=["reviews"])
