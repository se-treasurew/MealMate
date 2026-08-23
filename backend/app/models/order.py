from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Date,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Order(Base):
    __tablename__ = "order"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    meal_date = Column(Date, nullable=False, index=True)
    meal_type = Column(String(20), nullable=False)
    status = Column(String(20), default="pending", index=True)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    reviews = relationship("DishReview", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_item"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("order.id"), nullable=False)
    dish_id = Column(Integer, ForeignKey("dish.id"), nullable=False)
    quantity = Column(Integer, default=1)
    item_note = Column(Text)

    # 关系
    order = relationship("Order", back_populates="items")


class DishReview(Base):
    """菜品评价：订单完成后由下单人对单个菜品打分（1-5 星）并写评语。

    每个订单的每个菜品只允许一条评价，重复提交视为修改。
    """

    __tablename__ = "dish_review"
    __table_args__ = (
        UniqueConstraint("order_id", "dish_id", name="uq_review_order_dish"),
    )

    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dish.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("order.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    dish = relationship("Dish", back_populates="reviews")
    order = relationship("Order", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
