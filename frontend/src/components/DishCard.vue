<template>
  <article class="dish-card">
    <button
      type="button"
      class="dish-card-main"
      :aria-label="`查看菜品：${dish.name}`"
      @click="emit('view', dish)"
    >
      <div class="dish-card-image">
        <img
          v-if="coverImage && !imageBroken"
          :src="coverImage"
          :alt="dish.name"
          @error="imageBroken = true"
        />
        <div v-else class="dish-card-placeholder">
          <van-icon name="photo-o" size="32" />
        </div>
      </div>
      <div class="dish-card-content">
        <h3 class="dish-card-title">{{ dish.name }}</h3>
        <div class="dish-card-rating">
          <template v-if="(dish.rating_count ?? 0) > 0">
            <van-rate
              :model-value="Math.round(dish.avg_rating ?? 0)"
              readonly
              allow-half
              size="12"
              color="#FF6B35"
              void-color="#ddd"
              :gutter="1"
            />
            <span class="rating-score">{{ (dish.avg_rating ?? 0).toFixed(1) }}</span>
            <span class="rating-count">{{ dish.rating_count }}人评分</span>
          </template>
          <span v-else class="rating-empty">暂无评分</span>
        </div>
        <div class="dish-card-tags">
          <van-tag plain v-if="categoryName">{{ categoryName }}</van-tag>
          <van-tag v-for="tag in dish.tags" :key="tag.id" type="warning">
            {{ tag.name }}
          </van-tag>
        </div>
      </div>
    </button>
    <van-button
      round
      size="small"
      icon="plus"
      type="primary"
      class="quick-add-btn"
      aria-label="加入购物车"
      @click.stop="emit('addToCart', dish)"
    />
    <van-button
      round
      size="small"
      :icon="dish.is_favorite ? 'like' : 'like-o'"
      :type="dish.is_favorite ? 'danger' : 'default'"
      class="favorite-btn"
      :loading="favoriteUpdating"
      :aria-label="dish.is_favorite ? '取消收藏' : '收藏菜品'"
      @click.stop="emit('toggleFavorite', dish)"
    />
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { imageUrl, type Dish } from '@/api/dish'

const props = defineProps<{
  dish: Dish
  categoryName: string
  favoriteUpdating?: boolean
}>()

const emit = defineEmits<{
  view: [dish: Dish]
  toggleFavorite: [dish: Dish]
  addToCart: [dish: Dish]
}>()

const imageBroken = ref(false)
const coverImage = computed(() => {
  const image = props.dish.images?.[0]
  return imageUrl(image?.thumbnail_path || image?.image_path)
})
</script>

<style scoped>
.dish-card {
  position: relative;
  min-height: 104px;
  overflow: hidden;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s, transform 0.2s;
}

.dish-card-main {
  display: flex;
  align-items: stretch;
  width: 100%;
  min-height: 104px;
  padding: 10px;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: 0;
}

.dish-card-main:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: -2px;
}

.dish-card:has(.dish-card-main:active) {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  transform: translateY(1px);
}

.dish-card-image {
  position: relative;
  flex: 0 0 104px;
  width: 104px;
  height: 104px;
  overflow: hidden;
  background: #f5f5f5;
  border-radius: 8px;
}

.dish-card-image img,
.dish-card-placeholder {
  width: 100%;
  height: 100%;
}

.dish-card-image img {
  object-fit: cover;
}

.dish-card-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #dcdee0;
}

.dish-card-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  padding: 2px 42px 2px 12px;
}

.dish-card-title {
  display: -webkit-box;
  flex: 1;
  margin: 0;
  overflow: hidden;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.4;
  color: #262626;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.dish-card-rating {
  display: flex;
  gap: 4px;
  align-items: center;
  margin-top: 2px;
}

.rating-score {
  font-size: 12px;
  font-weight: 600;
  color: #ff6b35;
}

.rating-count,
.rating-empty {
  font-size: 11px;
  color: #999;
}

.rating-empty {
  color: #bbb;
}

.dish-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.quick-add-btn,
.favorite-btn {
  position: absolute;
  right: 12px;
  z-index: 1;
}

.quick-add-btn {
  top: 14px;
}

.favorite-btn {
  bottom: 14px;
}

@media (max-width: 420px) {
  .dish-card-image {
    flex-basis: 88px;
    width: 88px;
    height: 88px;
  }
}
</style>
