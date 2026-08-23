<template>
  <div class="home">
    <van-nav-bar title="饭饭之交" fixed>
      <template #right>
        <div style="display: flex; align-items: center; gap: 8px;">
          <!-- 游客态：显示「登录」入口 -->
          <van-tag
            v-if="userStore.isGuest"
            type="warning"
            size="medium"
            round
            @click="goLogin"
          >
            👋 游客模式 · 登录
          </van-tag>
          <template v-else>
            <!-- 饲养员模式：显示管理按钮 -->
            <van-icon
              v-if="userStore.isFeeder && userStore.currentMode === 'feeder'"
              name="setting-o"
              size="20"
              @click="goDishManage"
            />
            <!-- 模式标签 -->
            <van-tag
              v-if="userStore.isFeeder"
              type="primary"
              size="medium"
              round
              @click="onSwitchMode"
            >
              {{ userStore.currentMode === 'diner' ? '🍚 饭团模式' : '👨‍🍳 饲养员模式' }}
            </van-tag>
            <van-tag v-else type="success" size="medium" round>
              🍚 {{ userStore.roleName }}
            </van-tag>
          </template>
        </div>
      </template>
    </van-nav-bar>

    <div
      class="content swipe-surface"
      style="padding-top: 46px"
      @touchstart="onTouchStart"
      @touchmove="onTouchMove"
      @touchend="onTouchEnd"
      @touchcancel="onTouchCancel"
      @click.capture="onClickCapture"
    >
      <!-- 搜索栏 -->
      <van-search
        v-model="searchKeyword"
        placeholder="搜索菜品"
        shape="round"
        @search="onSearch"
      />

      <!-- 分类筛选 -->
      <div class="category-tabs">
        <van-tabs
          v-model:active="activeCategory"
          animated
          sticky
          :offset-top="46"
          @change="onCategoryChange"
        >
          <van-tab
            v-for="tab in categoryTabs"
            :key="tab.id"
            :title="tab.name"
            :name="tab.id"
          >
            <div class="dish-page">
              <van-loading
                v-if="dishPages[tab.id].loading"
                type="spinner"
                class="page-loading"
              />

              <template v-else>
                <div class="dish-list" v-if="dishPages[tab.id].dishes.length > 0">
                  <article
                    v-for="dish in dishPages[tab.id].dishes"
                    :key="dish.id"
                    class="dish-card"
                  >
                    <button
                      type="button"
                      class="dish-card-main"
                      :aria-label="`查看菜品：${dish.name}`"
                      @click="goDishDetail(dish.id)"
                    >
                      <div class="dish-card-image">
                        <img
                          v-if="getCoverImage(dish) && !isImageBroken(dish)"
                          :src="getCoverImage(dish)"
                          :alt="dish.name"
                          @error="markImageBroken(dish.id)"
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
                          <van-tag plain v-if="getCategoryName(dish.category_id)">
                            {{ getCategoryName(dish.category_id) }}
                          </van-tag>
                          <van-tag
                            v-for="tag in dish.tags"
                            :key="tag.id"
                            type="warning"
                          >
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
                      @click="quickAddToCart(dish)"
                    />
                  </article>
                </div>
                <van-empty
                  v-else
                  :description="dishPages[tab.id].error ? '加载失败' : '暂无菜品'"
                  image="search"
                >
                  <van-button round type="primary" @click="loadDishes(tab.id, true)">
                    刷新
                  </van-button>
                </van-empty>
              </template>
            </div>
          </van-tab>
        </van-tabs>
      </div>
    </div>

    <!-- 悬浮购物车 -->
    <FloatingCart />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast } from 'vant'
import { useUserStore } from '@/stores/user'
import { useCartStore } from '@/stores/cart'
import { getCategories, getDishes, imageUrl, type Category, type Dish } from '@/api/dish'
import FloatingCart from '@/components/FloatingCart.vue'
import { useHorizontalSwipe } from '@/composables/useHorizontalSwipe'

const router = useRouter()
const userStore = useUserStore()
const cartStore = useCartStore()
const searchKeyword = ref('')
const activeCategory = ref(0)
const categories = ref<Category[]>([])
const brokenImageIds = ref(new Set<number>())

interface DishPage {
  dishes: Dish[]
  loading: boolean
  error: boolean
  loadedKeyword: string | null
  requestId: number
}

const createDishPage = (): DishPage => ({
  dishes: [],
  loading: false,
  error: false,
  loadedKeyword: null,
  requestId: 0,
})

const dishPages = reactive<Record<number, DishPage>>({
  0: createDishPage(),
})

const categoryTabs = computed(() => [
  { id: 0, name: '全部' },
  ...categories.value,
])

const ensureDishPage = (categoryId: number) => {
  if (!dishPages[categoryId]) {
    dishPages[categoryId] = createDishPage()
  }
  return dishPages[categoryId]
}

// 加载分类
const loadCategories = async () => {
  try {
    const { data } = await getCategories()
    categories.value = data
    data.forEach((category) => ensureDishPage(category.id))
  } catch (e) {
    showToast('加载分类失败')
  }
}

// 加载菜品
const loadDishes = async (categoryId = activeCategory.value, force = false) => {
  const page = ensureDishPage(categoryId)
  const keyword = searchKeyword.value.trim()
  if (!force && page.loadedKeyword === keyword) return

  const requestId = ++page.requestId
  if (page.loadedKeyword !== keyword) {
    page.dishes = []
  }
  page.loading = true
  page.error = false

  try {
    const { data } = await getDishes({
      search: keyword || undefined,
      category_id: categoryId || undefined,
    })
    if (page.requestId === requestId) {
      page.dishes = data
      page.loadedKeyword = keyword
    }
  } catch (e) {
    if (page.requestId === requestId) {
      page.error = true
      showToast('加载菜品失败')
    }
  } finally {
    if (page.requestId === requestId) {
      page.loading = false
    }
  }
}

const onSearch = () => {
  Object.values(dishPages).forEach((page) => {
    page.requestId += 1
    page.dishes = []
    page.loading = false
    page.error = false
    page.loadedKeyword = null
  })
  brokenImageIds.value = new Set()
  void loadDishes(activeCategory.value, true)
}

const onCategoryChange = (name: string | number) => {
  const categoryId = Number(name)
  activeCategory.value = categoryId
  void loadDishes(categoryId)
}

const categoryIndex = () =>
  categoryTabs.value.findIndex((category) => category.id === activeCategory.value)

const switchCategory = (step: -1 | 1) => {
  const index = categoryIndex()
  const target = categoryTabs.value[index + step]
  if (!target) return

  activeCategory.value = target.id
  void loadDishes(target.id)
}

const { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel, onClickCapture } =
  useHorizontalSwipe({
    onNext: () => switchCategory(1),
    onPrevious: () => switchCategory(-1),
    canNext: () => {
      const index = categoryIndex()
      return index >= 0 && index < categoryTabs.value.length - 1
    },
    canPrevious: () => categoryIndex() > 0,
    excludeSelector: '.van-nav-bar, .van-tabbar, .van-search, .van-tabs__wrap',
  })

// 获取封面图
const getCoverImage = (dish: Dish) => {
  if (dish.images && dish.images.length > 0) {
    return imageUrl(dish.images[0].thumbnail_path || dish.images[0].image_path)
  }
  return ''
}

const isImageBroken = (dish: Dish) => brokenImageIds.value.has(dish.id)

const markImageBroken = (dishId: number) => {
  brokenImageIds.value = new Set(brokenImageIds.value).add(dishId)
}

// 获取分类名称
const getCategoryName = (id: number) => {
  return categories.value.find((c) => c.id === id)?.name || ''
}

const goDishDetail = (id: number) => {
  router.push(`/dishes/${id}`)
}

const goDishManage = () => {
  router.push('/admin/dishes')
}

const goLogin = () => {
  router.push('/login')
}

const onSwitchMode = () => {
  userStore.switchMode()
  showToast(
    userStore.currentMode === 'feeder' ? '已切换到饲养员模式' : '已切换到饭团模式'
  )
}

// 快捷加购（默认数量 1，备注留空，详细信息可在点餐车调整）
const quickAddToCart = (dish: Dish) => {
  cartStore.addItem({
    dish_id: dish.id,
    dish_name: dish.name,
    unit_image: getCoverImage(dish),
    price_label: '',
    quantity: 1,
    item_note: '',
  })

  showSuccessToast('已加入购物车')
}

onMounted(async () => {
  await loadCategories()
  await loadDishes(0)
})
</script>

<style scoped>
.swipe-surface {
  min-height: calc(100svh - 50px);
  touch-action: pan-y;
}

.category-tabs {
  background: #fff;
}

.page-loading {
  display: flex;
  justify-content: center;
  padding: 48px 0;
}

.dish-card {
  position: relative;
  min-height: 104px;
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s, transform 0.2s;
}

.dish-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.dish-card-main {
  display: flex;
  align-items: stretch;
  width: 100%;
  min-height: 104px;
  padding: 10px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
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
  flex: 0 0 104px;
  width: 104px;
  height: 104px;
  overflow: hidden;
  position: relative;
  background: #f5f5f5;
  border-radius: 8px;
}

.dish-card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dish-card-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #dcdee0;
}

.dish-card-content {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 2px 42px 2px 12px;
}

.dish-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  margin: 0;
  flex: 1;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.dish-card-rating {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.rating-score {
  font-size: 12px;
  color: #FF6B35;
  font-weight: 600;
}

.rating-count {
  font-size: 11px;
  color: #999;
}

.rating-empty {
  font-size: 11px;
  color: #bbb;
}

.quick-add-btn {
  position: absolute;
  top: 14px;
  right: 12px;
  z-index: 1;
}

.dish-card-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

@media (max-width: 420px) {
  .dish-card-image {
    flex-basis: 88px;
    width: 88px;
    height: 88px;
  }
}
</style>
