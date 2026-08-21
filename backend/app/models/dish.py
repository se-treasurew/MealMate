from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class DishImage(Base):
    __tablename__ = "dish_image"

    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dish.id"), nullable=False)
    image_path = Column(String(255), nullable=False)
    thumbnail_path = Column(String(255))
    sort_order = Column(Integer, default=0)

    # 关系
    dish = relationship("Dish", back_populates="images")


class DishLink(Base):
    __tablename__ = "dish_link"

    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dish.id"), nullable=False)
    url = Column(String(500), nullable=False)
    title = Column(String(200))

    # 关系
    dish = relationship("Dish", back_populates="links")


class DishHistory(Base):
    __tablename__ = "dish_history"

    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dish.id"), nullable=False)
    change_description = Column(Text, nullable=False)
    changed_by = Column(Integer, ForeignKey("user.id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    dish = relationship("Dish", back_populates="history")


class Tag(Base):
    __tablename__ = "tag"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)

    # 关系
    dish_associations = relationship("DishTag", back_populates="tag")
