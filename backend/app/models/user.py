from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Date, ForeignKey, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50))
    avatar_url = Column(String(255))
    is_admin = Column(Boolean, default=False)
    is_feeder = Column(Boolean, default=False)
    # 账号可用性：禁用后不能登录，历史数据保留
    is_active = Column(Boolean, default=True, server_default=text("1"))
    # 首次登录强制改密标志（管理员建号/重置密码时置 True）
    must_change_password = Column(Boolean, default=False, server_default=text("0"))
    # 每次改密、重置密码或禁用账号时递增，用于使历史 JWT 立即失效
    token_version = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    orders = relationship("Order", back_populates="user")
    dishes_created = relationship("Dish", back_populates="creator")
    reviews = relationship("DishReview", back_populates="user")


class DishCategory(Base):
    __tablename__ = "dish_category"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    sort_order = Column(Integer, default=0)

    # 关系
    dishes = relationship("Dish", back_populates="category")


class Dish(Base):
    __tablename__ = "dish"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("dish_category.id"), nullable=False)
    description = Column(Text)
    notes = Column(Text)
    status = Column(String(20), default="active", index=True)
    created_by = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    category = relationship("DishCategory", back_populates="dishes")
    creator = relationship("User", back_populates="dishes_created")
    images = relationship("DishImage", back_populates="dish", cascade="all, delete-orphan")
    links = relationship("DishLink", back_populates="dish", cascade="all, delete-orphan")
    history = relationship("DishHistory", back_populates="dish", cascade="all, delete-orphan")
    # tag_links 为关联表行（同步时增删）；tags 为直达 Tag 的只读关系（响应序列化用）
    tag_links = relationship("DishTag", back_populates="dish", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary="dish_tag", viewonly=True)
    reviews = relationship("DishReview", back_populates="dish", cascade="all, delete-orphan")
