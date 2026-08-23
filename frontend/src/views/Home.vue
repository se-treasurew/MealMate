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
              <van-empty
                v-if="tab.id === FAVORITES_TAB_ID && userStore.isGuest"
                description="登录后查看收藏"
              >
                <van-button round type="primary" @click="goLogin">
                  登录
                </van-button>
              </van-empty>

              <van-loading
                v-else-if="dishPages[tab.id].loading"
                type="spinner"
                class="page-loading"
              />

              <template v-else>
                <TransitionGroup
                  :name="tab.id === FAVORITES_TAB_ID ? 'favorite-list' : undefined"
                  tag="div"
                  class="dish-list"
                >
                  <DishCard
                    v-for="dish in dishPages[tab.id].dishes"
                    :key="dish.id"
                    :dish="dish"
                    :category-name="getCategoryName(dish.category_id)"
                    :favorite-updating="favoriteUpdatingIds.has(dish.id)"
                    @view="goDishDetail"
                    @toggle-favorite="toggleFavorite"
                    @add-to-cart="quickAddToCart"
                  />
                </TransitionGroup>
                <van-empty
                  v-if="dishPages[tab.id].dishes.length === 0"
                  :description="
                    dishPages[tab.id].error
                      ? '加载失败'
                      : tab.id === FAVORITES_TAB_ID
                        ? '暂无收藏'
                        : '暂无菜品'
                  "
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
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast } from 'vant'
import { useUserStore } from '@/stores/user'
import { useCartStore } from '@/stores/cart'
import {
  favoriteDish,
  getCategories,
  getDishes,
  getFavoriteDishes,
  imageUrl,
  unfavoriteDish,
  type Category,
  type Dish,
} from '@/api/dish'
import FloatingCart from '@/components/FloatingCart.vue'
import DishCard from '@/components/DishCard.vue'
import { useHorizontalSwipe } from '@/composables/useHorizontalSwipe'

const FAVORITES_TAB_ID = -1
const ALL_TAB_ID = 0

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const cartStore = useCartStore()
const searchKeyword = ref('')
const openedFromFavoritesRoute = route.query.tab === 'favorites'
const initialCategory = openedFromFavoritesRoute ? FAVORITES_TAB_ID : ALL_TAB_ID
const activeCategory = ref(initialCategory)
const categories = ref<Category[]>([])
const favoriteUpdatingIds = ref(new Set<number>())
const favoriteOverrides = ref(new Map<number, boolean>())

interface DishPage {
  dishes: Dish[]
  loading: boolean
  error: boolean
  loadedKeyword: string | null
  requestId: number
  resultVersion: number
}

const createDishPage = (): DishPage => ({
  dishes: [],
  loading: false,
  error: false,
  loadedKeyword: null,
  requestId: 0,
  resultVersion: 0,
})

const dishPages = reactive<Record<number, DishPage>>({
  [FAVORITES_TAB_ID]: createDishPage(),
  [ALL_TAB_ID]: createDishPage(),
})

const categoryTabs = computed(() => [
  { id: FAVORITES_TAB_ID, name: '收藏' },
  { id: ALL_TAB_ID, name: '全部' },
  ...categories.value,
])

const ensureDishPage = (categoryId: number) => {
  if (!dishPages[categoryId]) {
    dishPages[categoryId] = createDishPage()
  }
  return dishPages[categoryId]
}

const applyFavoriteOverrides = (dishes: Dish[], categoryId: number) =>
  dishes.filter((dish) => {
    const override = favoriteOverrides.value.get(dish.id)
    if (override === undefined) return true
    dish.is_favorite = override
    return categoryId !== FAVORITES_TAB_ID || override
  })

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

  if (categoryId === FAVORITES_TAB_ID && userStore.isGuest) {
    page.requestId += 1
    if (page.loadedKeyword !== keyword) page.resultVersion += 1
    page.dishes = []
    page.loading = false
    page.error = false
    page.loadedKeyword = keyword
    return
  }

  const requestId = ++page.requestId
  if (page.loadedKeyword !== keyword) {
    page.resultVersion += 1
    page.dishes = []
  }
  page.loading = true
  page.error = false

  try {
    const { data } = categoryId === FAVORITES_TAB_ID
      ? await getFavoriteDishes({ search: keyword || undefined })
      : await getDishes({
          search: keyword || undefined,
          category_id: categoryId === ALL_TAB_ID ? undefined : categoryId,
        })
    if (page.requestId === requestId) {
      page.dishes = applyFavoriteOverrides(data, categoryId)
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
    page.resultVersion += 1
    page.dishes = []
    page.loading = false
    page.error = false
    page.loadedKeyword = null
  })
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

// 获取分类名称
const getCategoryName = (id: number) => {
  return categories.value.find((c) => c.id === id)?.name || ''
}

const goDishDetail = (dish: Dish) => {
  router.push(`/dishes/${dish.id}`)
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

const setFavoriteUpdating = (dishId: number, updating: boolean) => {
  const next = new Set(favoriteUpdatingIds.value)
  if (updating) next.add(dishId)
  else next.delete(dishId)
  favoriteUpdatingIds.value = next
}

const updateCachedFavorite = (dishId: number, isFavorite: boolean) => {
  Object.values(dishPages).forEach((page) => {
    page.dishes.forEach((cachedDish) => {
      if (cachedDish.id === dishId) {
        cachedDish.is_favorite = isFavorite
      }
    })
  })
}

const removeDishFromFavoriteCache = (dishId: number) => {
  const favoritePage = ensureDishPage(FAVORITES_TAB_ID)
  const index = favoritePage.dishes.findIndex((cachedDish) => cachedDish.id === dishId)
  if (index >= 0) favoritePage.dishes.splice(index, 1)
}

const invalidateFavoriteCache = () => {
  const favoritePage = ensureDishPage(FAVORITES_TAB_ID)
  favoritePage.requestId += 1
  favoritePage.resultVersion += 1
  favoritePage.dishes = []
  favoritePage.loading = false
  favoritePage.error = false
  favoritePage.loadedKeyword = null
}

const toggleFavorite = async (dish: Dish) => {
  if (userStore.isGuest) {
    showToast('请先登录后收藏')
    await router.push('/login')
    return
  }
  if (favoriteUpdatingIds.value.has(dish.id)) return

  const previous = dish.is_favorite
  const target = !previous
  const favoritePage = ensureDishPage(FAVORITES_TAB_ID)
  const removedIndex = target
    ? -1
    : favoritePage.dishes.findIndex((cachedDish) => cachedDish.id === dish.id)
  const removedDish = removedIndex >= 0 ? favoritePage.dishes[removedIndex] : null
  const operationResultVersion = favoritePage.resultVersion
  const operationKeyword = favoritePage.loadedKeyword
  setFavoriteUpdating(dish.id, true)
  favoriteOverrides.value.set(dish.id, target)
  updateCachedFavorite(dish.id, target)
  if (!target) removeDishFromFavoriteCache(dish.id)
  try {
    if (target) await favoriteDish(dish.id)
    else await unfavoriteDish(dish.id)
    favoriteOverrides.value.set(dish.id, target)
    updateCachedFavorite(dish.id, target)
    if (target) {
      invalidateFavoriteCache()
    } else {
      removeDishFromFavoriteCache(dish.id)
    }
    showSuccessToast(target ? '已收藏' : '已取消收藏')
  } catch (error: any) {
    favoriteOverrides.value.set(dish.id, previous)
    updateCachedFavorite(dish.id, previous)
    const canRestoreRemovedDish =
      !target &&
      removedDish !== null &&
      favoritePage.resultVersion === operationResultVersion &&
      favoritePage.loadedKeyword === operationKeyword &&
      !favoritePage.dishes.some((cachedDish) => cachedDish.id === dish.id)

    if (!target) {
      if (canRestoreRemovedDish && removedDish) {
        removedDish.is_favorite = true
        favoritePage.dishes.splice(removedIndex, 0, removedDish)
      } else {
        favoritePage.loadedKeyword = null
        if (activeCategory.value === FAVORITES_TAB_ID) {
          void loadDishes(FAVORITES_TAB_ID, true)
        }
      }
    }
    showToast(error.response?.data?.detail || '收藏操作失败')
  } finally {
    setFavoriteUpdating(dish.id, false)
  }
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
  if (openedFromFavoritesRoute) void router.replace('/')
  await loadCategories()
  await loadDishes(activeCategory.value)
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

.dish-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.dish-list:empty {
  padding: 0;
}

.favorite-list-enter-active,
.favorite-list-leave-active,
.favorite-list-move {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.favorite-list-enter-from,
.favorite-list-leave-to {
  opacity: 0;
  transform: translateX(-16px);
}
</style>
