"""Landing homepage carousel content.

Public read endpoint powers the Landing page slider. The admin endpoints back the
Admin Console "Homepage Content" (Offers & Messages) section. Content is either a
sprite icon identifier or an uploaded raster image; images are never stored inline
in the database and are served back through a dedicated read-only route.
"""
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import HomepageItem, User
from .dependencies import require_admin

router = APIRouter(prefix="/api", tags=["homepage"])

ITEM_TYPES = {"platform", "announcement", "offer", "update", "partner", "advertisement"}
BADGES = {"new", "offer", "important", "update"}
MEDIA_KINDS = {"icon", "image", "none"}

IMAGE_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
IMAGE_MAX_BYTES = 3 * 1024 * 1024


def _cta_url(value):
    text = (value or "").strip()
    if not text:
        return None
    if text.startswith(("http://", "https://", "/")):
        return text
    raise ValueError("CTA URL must be an http(s) or site-relative link")


def _icon(value):
    text = (value or "").strip()
    if not text:
        return None
    import re
    if not re.fullmatch(r"icon-[a-z0-9-]{1,50}", text):
        raise ValueError("Icon must be an existing icon identifier such as icon-folder")
    return text


def _media_dir() -> Path:
    directory = Path(settings.workspace_root).resolve().parent / "homepage"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class HomepageIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    item_type: str = Field(default="platform")
    badge: str | None = Field(default=None)
    title_en: str = Field(min_length=1, max_length=200)
    title_ar: str = Field(min_length=1, max_length=200)
    body_en: str = Field(default="", max_length=1000)
    body_ar: str = Field(default="", max_length=1000)
    cta_label_en: str | None = Field(default=None, max_length=80)
    cta_label_ar: str | None = Field(default=None, max_length=80)
    cta_url: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, max_length=60)
    media_kind: str = Field(default="icon")
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    enabled: bool = True
    pinned: bool = False
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("item_type")
    @classmethod
    def _type(cls, value):
        if value not in ITEM_TYPES:
            raise ValueError("Unknown content type")
        return value

    @field_validator("badge")
    @classmethod
    def _badge(cls, value):
        if value in (None, ""):
            return None
        if value not in BADGES:
            raise ValueError("Unknown badge")
        return value

    @field_validator("media_kind")
    @classmethod
    def _media(cls, value):
        if value not in MEDIA_KINDS:
            raise ValueError("Unknown media kind")
        return value

    @field_validator("cta_url")
    @classmethod
    def _url(cls, value):
        return _cta_url(value)

    @field_validator("icon")
    @classmethod
    def _icon_id(cls, value):
        return _icon(value)


class HomepagePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    item_type: str | None = None
    badge: str | None = None
    title_en: str | None = Field(default=None, min_length=1, max_length=200)
    title_ar: str | None = Field(default=None, min_length=1, max_length=200)
    body_en: str | None = Field(default=None, max_length=1000)
    body_ar: str | None = Field(default=None, max_length=1000)
    cta_label_en: str | None = Field(default=None, max_length=80)
    cta_label_ar: str | None = Field(default=None, max_length=80)
    cta_url: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, max_length=60)
    media_kind: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    enabled: bool | None = None
    pinned: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("item_type")
    @classmethod
    def _type(cls, value):
        if value is not None and value not in ITEM_TYPES:
            raise ValueError("Unknown content type")
        return value

    @field_validator("badge")
    @classmethod
    def _badge(cls, value):
        if value in (None, "null", ""):
            return None
        if value not in BADGES:
            raise ValueError("Unknown badge")
        return value

    @field_validator("media_kind")
    @classmethod
    def _media(cls, value):
        if value is not None and value not in MEDIA_KINDS:
            raise ValueError("Unknown media kind")
        return value

    @field_validator("cta_url")
    @classmethod
    def _url(cls, value):
        return _cta_url(value)

    @field_validator("icon")
    @classmethod
    def _icon_id(cls, value):
        return _icon(value)


def _live(row: HomepageItem, now: datetime) -> bool:
    if not row.enabled:
        return False
    if row.starts_at and row.starts_at > now:
        return False
    if row.ends_at and row.ends_at < now:
        return False
    return True


@router.get("/homepage")
def public_homepage(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(HomepageItem).order_by(HomepageItem.pinned.desc(), HomepageItem.sort_order, HomepageItem.id)
    )
    return [row.as_payload() for row in rows if _live(row, now)]


@router.get("/homepage/media/{item_id}")
def homepage_media(item_id: int, db: Session = Depends(get_db)):
    row = db.get(HomepageItem, item_id)
    if row is None or row.media_kind != "image" or not row.media_path:
        raise HTTPException(404, "Image not found")
    path = Path(row.media_path)
    if not path.is_file():
        raise HTTPException(404, "Image not found")
    media_type = IMAGE_EXTENSIONS.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)


@router.get("/admin/homepage")
def admin_list(_: object = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(HomepageItem).order_by(HomepageItem.pinned.desc(), HomepageItem.sort_order, HomepageItem.id)
    )
    return [row.as_payload() for row in rows]


@router.post("/admin/homepage", status_code=201)
def admin_create(data: HomepageIn, _: object = Depends(require_admin), db: Session = Depends(get_db)):
    values = data.model_dump()
    if values.get("sort_order") is None:
        values["sort_order"] = (db.scalar(select(func.max(HomepageItem.sort_order))) or 0) + 1
    row = HomepageItem(**values)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.as_payload()


@router.patch("/admin/homepage/{item_id}")
def admin_update(item_id: int, data: HomepagePatch, _: object = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(HomepageItem, item_id)
    if row is None:
        raise HTTPException(404, "Item not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row.as_payload()


@router.delete("/admin/homepage/{item_id}", status_code=200)
def admin_delete(item_id: int, _: object = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(HomepageItem, item_id)
    if row is None:
        raise HTTPException(404, "Item not found")
    if row.media_path:
        try:
            Path(row.media_path).unlink(missing_ok=True)
        except OSError:
            pass
    db.delete(row)
    db.commit()
    return {"deleted": item_id}


@router.post("/admin/homepage/{item_id}/image")
def admin_upload_image(item_id: int, file: UploadFile = File(...), _: object = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(HomepageItem, item_id)
    if row is None:
        raise HTTPException(404, "Item not found")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(422, "Image must be a PNG, JPEG or WebP file")
    if file.content_type != IMAGE_EXTENSIONS[suffix]:
        raise HTTPException(422, "Image type does not match its extension")
    content = file.file.read(IMAGE_MAX_BYTES + 1)
    if len(content) > IMAGE_MAX_BYTES:
        raise HTTPException(422, "Image must be 3 MB or smaller")
    directory = _media_dir()
    target = directory / f"item-{row.id}{suffix}"
    for existing in directory.glob(f"item-{row.id}.*"):
        if existing != target:
            try:
                existing.unlink()
            except OSError:
                pass
    target.write_bytes(content)
    row.media_path = str(target)
    row.media_kind = "image"
    db.commit()
    db.refresh(row)
    return row.as_payload()


@router.delete("/admin/homepage/{item_id}/image")
def admin_remove_image(item_id: int, _: object = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(HomepageItem, item_id)
    if row is None:
        raise HTTPException(404, "Item not found")
    if row.media_path:
        try:
            Path(row.media_path).unlink(missing_ok=True)
        except OSError:
            pass
    row.media_path = None
    if row.media_kind == "image":
        row.media_kind = "icon"
    db.commit()
    db.refresh(row)
    return row.as_payload()
