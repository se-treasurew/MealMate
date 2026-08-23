<template>
  <div class="dish-detail">
    <van-nav-bar title="菜品详情" fixed left-arrow @click-left="$router.back()" />

    <div class="content" style="padding-top: 46px; padding-bottom: 80px">
      <van-loading v-if="loading" type="spinner" class="loading" />

      <template v-else-if="dish">
        <!-- 图片轮播 -->
        <div class="swipe-wrapper" v-if="dish.images.length">
          <van-swipe
            ref="swipeRef"
            :autoplay="3000"
            :touchable="isMobile"
            indicator-color="white"
            @change="onSwipeChange"
          >
            <van-swipe-item v-for="img in dish.images" :key="img.id">
              <img :src="imageUrl(img.image_path)" class="dish-image" />
            </van-swipe-item>
          </van-swipe>

          <!-- Web端左右切换按钮 -->
          <div class="swipe-nav" v-if="dish.images.length > 1">
            <button
              class="swipe-btn swipe-btn-prev"
              @click="goPrev"
              :disabled="currentImageIndex === 0"
            >
              <van-icon name="arrow-left" size="20" />
            </button>
            <button
              class="swipe-btn swipe-btn-next"
              @click="goNext"
              :disabled="currentImageIndex === dish.images.length - 1"
            >
              <van-icon name="arrow" size="20" />
            </button>
          </div>
        </div>
        <div v-else class="no-image">
          <van-icon name="photo-o" size="64" />
          <p>暂无图片</p>
        </div>

        <!-- 基本信息 -->
        <div class="info-section">
          <h1 class="dish-name">{{ dish.name }}</h1>
          <div class="dish-tags">
            <van-tag plain type="primary">{{ getCategoryName(dish.category_id) }}</van-tag>
            <van-tag
              v-for="tag in dish.tags"
              :key="tag.id"
              plain
              type="warning"
            >
              {{ tag.name }}
            </van-tag>
          </div>
        </div>

        <!-- 详细做法（Markdown 渲染，默认展示） -->
        <van-cell-group inset title="详细做法" v-if="dish.description">
          <van-cell>
            <template #title>
              <div class="markdown-body" v-html="renderMarkdown(dish.description)"></div>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- 备注 -->
        <van-cell-group inset title="备注" v-if="dish.notes">
          <van-cell :label="dish.notes" />
        </van-cell-group>

        <!-- 参考链接 -->
        <van-cell-group inset title="参考链接" v-if="dish.links.length">
          <van-cell
            v-for="link in dish.links"
            :key="link.id"
            :title="link.title || link.url"
            :label="link.url"
            is-link
            @click="openLink(link.url)"
          />
        </van-cell-group>

        <!-- 用户评价 -->
        <van-cell-group inset title="用户评价">
          <div v-if="reviews.length === 0" class="review-empty">暂无评价</div>
          <template v-else>
            <div class="review-summary">
              <van-rate
                :model-value="Math.round(dish?.avg_rating ?? 0)"
                readonly
                allow-half
                size="14"
                color="#FF6B35"
                void-color="#ddd"
              />
              <span class="review-summary-score">{{ (dish?.avg_rating ?? 0).toFixed(1) }}分</span>
              <span class="review-summary-count">{{ dish?.rating_count ?? 0 }}人评分</span>
            </div>
            <div v-for="review in reviews" :key="review.id" class="review-entry">
              <div class="review-entry-head">
                <span class="review-entry-name">{{ review.user_nickname || '匿名用户' }}</span>
                <van-rate
                  :model-value="review.rating"
                  readonly
                  size="12"
                  color="#FF6B35"
                  void-color="#ddd"
                  :gutter="1"
                />
              </div>
              <div v-if="review.comment" class="review-entry-comment">{{ review.comment }}</div>
              <div class="review-entry-time">{{ formatReviewTime(review.created_at) }}</div>
            </div>
          </template>
        </van-cell-group>

        <!-- 点餐备注 -->
        <van-cell-group inset title="点餐备注">
          <van-field
            v-model="itemNote"
            placeholder="如：少油、不要香菜"
            type="textarea"
            rows="2"
            autosize
          />
        </van-cell-group>
      </template>
    </div>

    <!-- 悬浮购物车 -->
    <FloatingCart />

    <!-- 固定底部操作栏 -->
    <div class="fixed-bottom-bar" v-if="dish">
      <div class="quantity-control">
        <span class="label">数量</span>
        <van-stepper v-model="quantity" min="1" max="99" />
      </div>
      <van-button
        type="primary"
        round
        block
        class="add-cart-btn"
        @click="confirmAddToCart"
      >
        加入购物车
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { showToast, showSuccessToast } from 'vant'
import type { SwipeInstance } from 'vant'
import {
  getDish,
  getCategories,
  imageUrl,
  type Dish,
  type Category,
} from '@/api/dish'
import { useCartStore } from '@/stores/cart'
import { renderMarkdown } from '@/utils/markdown'
import { getDishReviews, type Review } from '@/api/review'
import FloatingCart from '@/components/FloatingCart.vue'

const route = useRoute()
const cartStore = useCartStore()

const loading = ref(true)
const dish = ref<Dish | null>(null)
const categories = ref<Category[]>([])
const reviews = ref<Review[]>([])
const quantity = ref(1)
const itemNote = ref('')
const swipeRef = ref<SwipeInstance>()
const currentImageIndex = ref(0)
const isMobile = ref(window.innerWidth <= 768)

// 监听窗口大小变化
const handleResize = () => {
  isMobile.value = window.innerWidth <= 768
}

const loadDish = async () => {
  const id = Number(route.params.id)
  try {
    const { data } = await getDish(id)
    dish.value = data
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

const loadReviews = async () => {
  const id = Number(route.params.id)
  try {
    const { data } = await getDishReviews(id)
    reviews.value = data
  } catch {
    // 评价加载失败不阻断页面
  }
}

const formatReviewTime = (t?: string) => {
  if (!t) return ''
  return new Date(t).toLocaleDateString('zh-CN')
}

const getCategoryName = (id: number) =>
  categories.value.find((c) => c.id === id)?.name || ''

const getCoverImage = (dish: Dish) => {
  if (dish.images && dish.images.length > 0) {
    return imageUrl(dish.images[0].thumbnail_path || dish.images[0].image_path)
  }
  return ''
}

const openLink = (url: string) => {
  window.open(url, '_blank')
}

// 轮播图控制
const onSwipeChange = (index: number) => {
  currentImageIndex.value = index
}

const goPrev = () => {
  swipeRef.value?.prev()
}

const goNext = () => {
  swipeRef.value?.next()
}

const confirmAddToCart = () => {
  if (!dish.value) return

  cartStore.addItem({
    dish_id: dish.value.id,
    dish_name: dish.value.name,
    unit_image: getCoverImage(dish.value),
    price_label: getCategoryName(dish.value.category_id),
    item_note: itemNote.value,
    quantity: quantity.value,
  })

  showSuccessToast('已加入购物车')

  // 重置表单
  itemNote.value = ''
  quantity.value = 1
}

onMounted(async () => {
  // 监听窗口大小变化
  window.addEventListener('resize', handleResize)

  // 加载数据
  const { data } = await getCategories()
  categories.value = data
  await loadDish()
  void loadReviews()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.dish-image {
  width: 100%;
  height: 300px;
  object-fit: cover;
}

/* 轮播容器 */
.swipe-wrapper {
  position: relative;
}

/* Web端切换按钮 */
.swipe-nav {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  z-index: 10;
}

.swipe-btn {
  pointer-events: auto;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  border: none;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  opacity: 0;
}

.swipe-wrapper:hover .swipe-btn {
  opacity: 1;
}

.swipe-btn:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.7);
  transform: scale(1.1);
}

.swipe-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.swipe-btn:active:not(:disabled) {
  transform: scale(0.95);
}

/* 移动端隐藏按钮（使用触摸滑动） */
@media (max-width: 768px) {
  .swipe-nav {
    display: none;
  }
}

.no-image {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #ddd;
}

.info-section {
  padding: 16px;
  background: #fff;
}

.dish-name {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px;
  color: #262626;
}

.dish-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 用户评价 */
.review-empty {
  padding: 16px;
  color: #bbb;
  font-size: 13px;
  text-align: center;
}

.review-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f5;
}

.review-summary-score {
  font-size: 15px;
  font-weight: 600;
  color: #FF6B35;
}

.review-summary-count {
  font-size: 12px;
  color: #999;
}

.review-entry {
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f5;
}

.review-entry:last-child {
  border-bottom: none;
}

.review-entry-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-entry-name {
  font-size: 13px;
  font-weight: 600;
  color: #262626;
}

.review-entry-comment {
  margin-top: 6px;
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  word-break: break-word;
}

.review-entry-time {
  margin-top: 4px;
  font-size: 11px;
  color: #bbb;
}

/* 固定底部操作栏 */
.fixed-bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #eee;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 999;
}

.quantity-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quantity-control .label {
  font-size: 14px;
  color: #646566;
}

.add-cart-btn {
  flex: 1;
}
</style>
