from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DishFavorite(Base):
    __tablename__ = "dish_favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "dish_id", name="uq_favorite_user_dish"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    dish_id = Column(Integer, ForeignKey("dish.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="favorite_dishes")
    dish = relationship("Dish", back_populates="favorited_by")
