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

    <div class="content" style="padding-top: 46px">
      <!-- 搜索栏 -->
      <van-search
        v-model="searchKeyword"
        placeholder="搜索菜品"
        shape="round"
        @search="onSearch"
      />

      <!-- 分类筛选 -->
      <div class="category-tabs">
        <van-tabs v-model:active="activeCategory" @change="onCategoryChange">
          <van-tab title="全部" :name="0" />
          <van-tab
            v-for="cat in categories"
            :key="cat.id"
            :title="cat.name"
            :name="cat.id"
          />
        </van-tabs>
      </div>

      <!-- 菜品列表 -->
      <div class="dish-list" v-if="dishes.length > 0">
        <article
          v-for="dish in dishes"
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
              <p class="dish-card-desc" v-if="dish.description">
                {{ dish.description.substring(0, 40) }}{{ dish.description.length > 40 ? '...' : '' }}
              </p>
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
      <van-empty v-else description="暂无菜品" image="search">
        <van-button round type="primary" @click="loadDishes">刷新</van-button>
      </van-empty>
    </div>

    <!-- 悬浮购物车 -->
    <FloatingCart />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast } from 'vant'
import { useUserStore } from '@/stores/user'
import { useCartStore } from '@/stores/cart'
import { getCategories, getDishes, imageUrl, type Category, type Dish } from '@/api/dish'
import FloatingCart from '@/components/FloatingCart.vue'

const router = useRouter()
const userStore = useUserStore()
const cartStore = useCartStore()
const searchKeyword = ref('')
const activeCategory = ref(0)
const categories = ref<Category[]>([])
const dishes = ref<Dish[]>([])
const brokenImageIds = ref(new Set<number>())

// 加载分类
const loadCategories = async () => {
  try {
    const { data } = await getCategories()
    categories.value = data
  } catch (e) {
    showToast('加载分类失败')
  }
}

// 加载菜品
const loadDishes = async () => {
  try {
    const { data } = await getDishes({
      search: searchKeyword.value || undefined,
      category_id: activeCategory.value || undefined,
    })
    dishes.value = data
    brokenImageIds.value = new Set()
  } catch (e) {
    showToast('加载菜品失败')
  }
}

const onSearch = () => loadDishes()
const onCategoryChange = () => loadDishes()

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
  await loadDishes()
})
</script>

<style scoped>
.category-tabs {
  background: #fff;
  position: sticky;
  top: 46px;
  z-index: 10;
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

.dish-card-desc {
  font-size: 13px;
  color: #8c8c8c;
  line-height: 1.5;
  margin: auto 0 0;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

@media (max-width: 420px) {
  .dish-card-image {
    flex-basis: 88px;
    width: 88px;
    height: 88px;
  }
}
</style>
