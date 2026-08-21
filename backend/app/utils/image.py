import io
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings


FORMAT_BY_EXTENSION = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}
MAX_IMAGE_PIXELS = 40_000_000


def remove_image_files(paths: list[str | None]) -> None:
    """尽力删除上传文件，并拒绝任何逃逸上传根目录的路径。"""
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    for path in paths:
        if not path:
            continue
        candidate = (upload_root / path).resolve()
        try:
            candidate.relative_to(upload_root)
        except ValueError:
            continue
        try:
            candidate.unlink()
        except (FileNotFoundError, OSError):
            pass


def _decode_and_normalize(content: bytes, extension: str) -> Image.Image:
    """完整解码图片并校验扩展名与真实格式一致。"""
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format != FORMAT_BY_EXTENSION[extension]:
                raise HTTPException(status_code=400, detail="图片扩展名与实际格式不一致")
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=400, detail="图片像素尺寸过大")
            source.load()
            image = ImageOps.exif_transpose(source)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "transparency" in source.info else "RGB")
            return image.copy()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="图片文件无效")


def _encode_webp(image: Image.Image, *, thumbnail: bool) -> bytes:
    output_image = image.copy()
    if thumbnail:
        output_image.thumbnail((200, 200))
    output = io.BytesIO()
    try:
        output_image.save(output, format="WEBP", quality=85, method=6)
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="图片处理失败")
    finally:
        output_image.close()
    return output.getvalue()


async def save_image(file: UploadFile) -> tuple[str, str]:
    """校验并保存 WebP 原图和缩略图，失败时不保留部分文件。"""
    filename = file.filename or ""
    extension = os.path.splitext(filename)[1].lower()
    if extension not in settings.ALLOWED_EXTENSIONS or extension not in FORMAT_BY_EXTENSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式，仅支持 {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}",
        )

    # 只读取上限再多一个字节，避免超大请求体被一次性载入应用内存。
    content = await file.read(settings.MAX_UPLOAD_SIZE + 1)
    if not content:
        raise HTTPException(status_code=400, detail="图片文件为空")
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="图片大小不能超过 5MB")

    image = _decode_and_normalize(content, extension)
    try:
        original_bytes = _encode_webp(image, thumbnail=False)
        thumbnail_bytes = _encode_webp(image, thumbnail=True)
    finally:
        image.close()

    now = datetime.now(timezone.utc)
    relative_dir = os.path.join(str(now.year), f"{now.month:02d}")
    absolute_dir = os.path.join(settings.UPLOAD_DIR, relative_dir)
    identifier = uuid.uuid4().hex
    image_name = f"{identifier}.webp"
    thumbnail_name = f"{identifier}_thumb.webp"
    image_absolute_path = os.path.join(absolute_dir, image_name)
    thumbnail_absolute_path = os.path.join(absolute_dir, thumbnail_name)

    os.makedirs(absolute_dir, exist_ok=True)
    try:
        with open(image_absolute_path, "wb") as output:
            output.write(original_bytes)
        with open(thumbnail_absolute_path, "wb") as output:
            output.write(thumbnail_bytes)
    except OSError:
        for path in (image_absolute_path, thumbnail_absolute_path):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
        raise HTTPException(status_code=500, detail="图片保存失败")

    image_relative_path = os.path.join(relative_dir, image_name).replace("\\", "/")
    thumbnail_relative_path = os.path.join(relative_dir, thumbnail_name).replace("\\", "/")
    return image_relative_path, thumbnail_relative_path
