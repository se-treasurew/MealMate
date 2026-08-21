from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class DishTag(Base):
    __tablename__ = "dish_tag"

    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dish.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tag.id"), nullable=False)

    # 关系
    dish = relationship("Dish", back_populates="tag_links")
    tag = relationship("Tag", back_populates="dish_associations")
