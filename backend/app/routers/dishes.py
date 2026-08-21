from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_optional
from app.models import (
    User, Dish, DishCategory, DishImage, DishLink, DishTag, Tag,
)
from app.schemas.dish import (
    DishCreate, DishUpdate, DishResponse, DishLinkBase,
)
from app.utils.image import remove_image_files, save_image

router = APIRouter()
MAX_UPLOAD_FILES_PER_REQUEST = 5


def validate_upload_batch(files: list[UploadFile]) -> None:
    """限制单次批量上传数量，使代理层总请求体上限可被严格约束。"""
    if not files:
        raise HTTPException(status_code=400, detail="至少选择一张图片")
    if len(files) > MAX_UPLOAD_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"每次最多上传 {MAX_UPLOAD_FILES_PER_REQUEST} 张图片",
        )


def check_feeder(user: User):
    if not (user.is_feeder or user.is_admin):
        raise HTTPException(status_code=403, detail="无权限")


async def sync_links(db: AsyncSession, dish: Dish, links: list[DishLinkBase]):
    """同步菜品的参考链接（仅用于更新场景）"""
    # 删除旧链接（dish.links 在调用前已通过 selectinload 加载）
    for old_link in list(dish.links):
        await db.delete(old_link)
    # 添加新链接
    for link in links:
        db.add(DishLink(dish_id=dish.id, url=link.url, title=link.title))


async def sync_tags(
    db: AsyncSession, dish: Dish, tag_names: list[str], is_new: bool = False
):
    """同步菜品标签：按名称查找，不存在则自动创建（自由标签）"""
    # 去空白、去重，过滤空名
    names: list[str] = []
    for raw in tag_names:
        name = raw.strip()
        if name and name not in names:
            names.append(name)

    # 仅在更新场景下删除旧关联（新建时 dish 还没有关联）
    if not is_new:
        for old in list(dish.tag_links):
            await db.delete(old)
    for name in names:
        result = await db.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            await db.flush()  # 获取 tag.id
        db.add(DishTag(dish_id=dish.id, tag_id=tag.id))


@router.get("", response_model=list[DishResponse])
async def list_dishes(
    category_id: int | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """获取菜品列表（游客可见上架菜品）"""
    stmt = select(Dish).options(
        selectinload(Dish.images),
        selectinload(Dish.links),
        selectinload(Dish.tags),
        selectinload(Dish.category),
    )

    # 游客/饭团只能看上架菜品；饲养员/店长可看全部
    if not (current_user and (current_user.is_feeder or current_user.is_admin)):
        stmt = stmt.where(Dish.status == "active")
    elif status_filter:
        stmt = stmt.where(Dish.status == status_filter)

    if category_id is not None:
        stmt = stmt.where(Dish.category_id == category_id)

    if search:
        # 关键词同时匹配菜名和标签名
        stmt = stmt.where(
            or_(
                Dish.name.ilike(f"%{search}%"),
                Dish.tags.any(Tag.name.ilike(f"%{search}%")),
            )
        )

    stmt = stmt.order_by(Dish.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().unique().all()


@router.get("/{dish_id}", response_model=DishResponse)
async def get_dish(
    dish_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """获取菜品详情（游客可见上架菜品）"""
    stmt = (
        select(Dish)
        .options(
            selectinload(Dish.images),
            selectinload(Dish.links),
            selectinload(Dish.tags),
        )
        .where(Dish.id == dish_id)
    )
    result = await db.execute(stmt)
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")

    # 游客/饭团不能看下架菜品
    if dish.status != "active" and not (
        current_user and (current_user.is_feeder or current_user.is_admin)
    ):
        raise HTTPException(status_code=404, detail="菜品不存在")

    return dish


@router.post("", response_model=DishResponse, status_code=201)
async def create_dish(
    payload: DishCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建菜品（仅饲养员/店长）"""
    check_feeder(current_user)

    # 校验分类
    result = await db.execute(
        select(DishCategory).where(DishCategory.id == payload.category_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="分类不存在")

    dish = Dish(
        name=payload.name,
        category_id=payload.category_id,
        description=payload.description,
        notes=payload.notes,
        status=payload.status,
        created_by=current_user.id,
    )
    db.add(dish)
    await db.flush()  # 获取 dish.id

    # 关联链接
    for link in payload.links:
        db.add(DishLink(dish_id=dish.id, url=link.url, title=link.title))

    # 关联标签（不存在则自动创建）
    await sync_tags(db, dish, payload.tag_names, is_new=True)

    await db.commit()
    await db.refresh(dish)

    # 重新加载关联关系
    stmt = (
        select(Dish)
        .options(
            selectinload(Dish.images),
            selectinload(Dish.links),
            selectinload(Dish.tags),
        )
        .where(Dish.id == dish.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.put("/{dish_id}", response_model=DishResponse)
async def update_dish(
    dish_id: int,
    payload: DishUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新菜品（仅饲养员/店长）"""
    check_feeder(current_user)

    # tag_links 预加载供 sync_tags 使用，tags 供响应序列化
    stmt = (
        select(Dish)
        .options(
            selectinload(Dish.images),
            selectinload(Dish.links),
            selectinload(Dish.tag_links),
            selectinload(Dish.tags),
        )
        .where(Dish.id == dish_id)
    )
    result = await db.execute(stmt)
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")

    if payload.name is not None:
        dish.name = payload.name
    if payload.category_id is not None:
        # 校验分类
        cat = await db.execute(
            select(DishCategory).where(DishCategory.id == payload.category_id)
        )
        if not cat.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="分类不存在")
        dish.category_id = payload.category_id
    if payload.description is not None:
        dish.description = payload.description
    if payload.notes is not None:
        dish.notes = payload.notes
    if payload.status is not None:
        if payload.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="状态值无效")
        dish.status = payload.status

    if payload.links is not None:
        await sync_links(db, dish, payload.links)

    if payload.tag_names is not None:
        await sync_tags(db, dish, payload.tag_names)

    await db.commit()
    await db.refresh(dish)

    # 重新加载
    stmt = (
        select(Dish)
        .options(
            selectinload(Dish.images),
            selectinload(Dish.links),
            selectinload(Dish.tags),
        )
        .where(Dish.id == dish.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.delete("/{dish_id}", status_code=204)
async def delete_dish(
    dish_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除菜品（仅饲养员/店长）"""
    check_feeder(current_user)

    result = await db.execute(
        select(Dish).options(selectinload(Dish.images)).where(Dish.id == dish_id)
    )
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")

    image_paths = [
        path
        for image in dish.images
        for path in (image.image_path, image.thumbnail_path)
    ]
    await db.delete(dish)
    await db.commit()
    remove_image_files(image_paths)


@router.post("/{dish_id}/images", response_model=list[dict])
async def upload_dish_images(
    dish_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传菜品图片（仅饲养员/店长），返回图片路径列表"""
    check_feeder(current_user)
    validate_upload_batch(files)

    result = await db.execute(select(Dish).where(Dish.id == dish_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")

    saved = []
    try:
        for idx, file in enumerate(files):
            image_path, thumbnail_path = await save_image(file)
            saved.append(
                {"image_path": image_path, "thumbnail_path": thumbnail_path}
            )
            # 查询当前最大 sort_order
            max_result = await db.execute(
                select(DishImage)
                .where(DishImage.dish_id == dish_id)
                .order_by(DishImage.sort_order.desc())
                .limit(1)
            )
            max_img = max_result.scalar_one_or_none()
            max_order = max_img.sort_order if max_img else -1
            image = DishImage(
                dish_id=dish.id,
                image_path=image_path,
                thumbnail_path=thumbnail_path,
                sort_order=max_order + 1 + idx,
            )
            db.add(image)

        await db.commit()
    except Exception:
        try:
            await db.rollback()
        finally:
            remove_image_files(
                [
                    path
                    for item in saved
                    for path in (item["image_path"], item["thumbnail_path"])
                ]
            )
        raise
    return saved


@router.delete("/{dish_id}/images/{image_id}", status_code=204)
async def delete_dish_image(
    dish_id: int,
    image_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除菜品图片（仅饲养员/店长）"""
    check_feeder(current_user)

    result = await db.execute(
        select(DishImage).where(
            DishImage.id == image_id, DishImage.dish_id == dish_id
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")

    image_paths = [image.image_path, image.thumbnail_path]
    await db.delete(image)
    await db.commit()
    remove_image_files(image_paths)
