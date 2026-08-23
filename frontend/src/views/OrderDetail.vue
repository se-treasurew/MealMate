<template>
  <div class="order-detail">
    <van-nav-bar title="订单详情" fixed left-arrow @click-left="$router.back()" />

    <div class="content" style="padding-top: 46px; padding-bottom: 80px">
      <van-loading v-if="loading" type="spinner" class="loading" />

      <template v-else-if="order">
        <!-- 状态卡片 -->
        <div class="status-card">
          <van-tag :type="statusColor(order.status)" size="large" round>
            {{ statusText(order.status) }}
          </van-tag>
          <span class="order-id">订单 #{{ order.id }}</span>
        </div>

        <!-- 用餐信息 -->
        <van-cell-group inset title="用餐信息">
          <van-cell title="期望日期" :value="order.meal_date" />
          <van-cell title="餐次" :value="order.meal_type" />
          <van-cell title="下单人" :value="order.user_nickname || '未知'" />
          <van-cell title="下单时间" :value="formatTime(order.created_at)" />
        </van-cell-group>

        <!-- 菜品明细 -->
        <van-cell-group inset title="菜品明细">
          <button
            v-for="item in order.items"
            :key="item.id"
            type="button"
            class="dish-item"
            :class="{ 'dish-item-disabled': !item.dish_available }"
            :disabled="!item.dish_available"
            @click="goDishDetail(item)"
          >
            <div class="dish-item-image">
              <img
                v-if="item.dish_image_path && !brokenDishImageIds.has(item.dish_id)"
                :src="imageUrl(item.dish_image_path)"
                :alt="item.dish_name"
                @error="markDishImageBroken(item.dish_id)"
              />
              <van-icon v-else name="photo-o" size="28" />
            </div>
            <div class="dish-item-content">
              <div class="dish-row">
                <span class="dish-name">{{ item.dish_name }}</span>
                <span class="dish-qty">x{{ item.quantity }}</span>
              </div>
              <div v-if="item.item_note" class="dish-note">备注：{{ item.item_note }}</div>
              <div v-if="!item.dish_available" class="dish-unavailable">
                菜品已不可查看
              </div>
            </div>
            <van-icon v-if="item.dish_available" name="arrow" class="dish-arrow" />
          </button>
        </van-cell-group>

        <!-- 整单备注 -->
        <van-cell-group inset title="整单备注" v-if="order.note">
          <van-cell :label="order.note" />
        </van-cell-group>

        <!-- 状态操作（饲养员/店长） -->
        <van-cell-group
          inset
          title="订单操作"
          v-if="userStore.isFeeder && order.status !== 'cancelled' && order.status !== 'done'"
        >
          <div class="action-buttons">
            <van-button
              v-if="order.status === 'pending'"
              type="primary"
              size="small"
              @click="changeStatus('accepted')"
            >接单</van-button>
            <van-button
              v-if="order.status === 'accepted'"
              type="primary"
              size="small"
              @click="changeStatus('cooking')"
            >开始制作</van-button>
            <van-button
              v-if="order.status === 'cooking' || order.status === 'accepted'"
              type="success"
              size="small"
              @click="changeStatus('done')"
            >完成</van-button>
          </div>
        </van-cell-group>

        <!-- 取消按钮（饭团，待处理） -->
        <div v-if="order.status === 'pending' && order.user_id === userStore.user?.id" class="cancel-area">
          <van-button plain block type="danger" @click="onCancel">取消订单</van-button>
        </div>

        <div v-if="canPermanentlyDelete" class="permanent-delete-area">
          <van-button plain block type="danger" @click="onPermanentlyDelete">
            永久删除订单
          </van-button>
        </div>

        <!-- 评价区块（订单本人，已完成订单） -->
        <van-cell-group
          inset
          title="评价菜品"
          v-if="canReview"
        >
          <div v-for="item in order.items" :key="item.id" class="review-item">
            <div class="review-dish-name">{{ item.dish_name }}</div>
            <div class="review-rate-row">
              <van-rate
                v-model="reviewForm[item.dish_id].rating"
                size="20"
                color="#FF6B35"
                void-color="#ddd"
              />
              <span class="review-rating-text">{{ ratingText(reviewForm[item.dish_id].rating) }}</span>
            </div>
            <van-field
              v-model="reviewForm[item.dish_id].comment"
              placeholder="说说菜的味道、分量如何～（选填）"
              type="textarea"
              rows="2"
              autosize
              maxlength="500"
              show-word-limit
              class="review-comment-field"
            />
          </div>
          <div class="review-submit-area">
            <van-button
              type="primary"
              round
              block
              :loading="submittingReview"
              @click="onSubmitReviews"
            >
              {{ hasExistingReviews ? '更新评价' : '提交评价' }}
            </van-button>
          </div>
        </van-cell-group>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import {
  getOrder,
  updateOrderStatus,
  cancelOrder,
  permanentlyDeleteOrder,
  statusText,
  statusColor,
  type Order,
  type OrderItem,
} from '@/api/order'
import { imageUrl } from '@/api/dish'
import { submitOrderReviews, getOrderReviews } from '@/api/review'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const order = ref<Order | null>(null)
const brokenDishImageIds = ref(new Set<number>())

// ===== 评价 =====
interface ReviewFormEntry {
  rating: number
  comment: string
}
const reviewForm = reactive<Record<number, ReviewFormEntry>>({})
const submittingReview = ref(false)
const hasExistingReviews = ref(false)

const canReview = computed(
  () =>
    order.value?.status === 'done' &&
    order.value.user_id === userStore.user?.id
)

const canPermanentlyDelete = computed(
  () =>
    userStore.isAdmin &&
    (order.value?.status === 'done' || order.value?.status === 'cancelled')
)

const ratingText = (rating: number): string => {
  const map: Record<number, string> = {
    1: '很差',
    2: '较差',
    3: '一般',
    4: '满意',
    5: '超赞',
  }
  return map[rating] || ''
}

const initReviewForm = () => {
  if (!order.value) return
  for (const item of order.value.items) {
    if (!reviewForm[item.dish_id]) {
      reviewForm[item.dish_id] = { rating: 5, comment: '' }
    }
  }
}

const loadExistingReviews = async () => {
  if (!order.value) return
  try {
    const { data } = await getOrderReviews(order.value.id)
    hasExistingReviews.value = data.length > 0
    for (const review of data) {
      reviewForm[review.dish_id] = {
        rating: review.rating,
        comment: review.comment ?? '',
      }
    }
  } catch {
    // 回显失败不阻断页面
  }
}

const onSubmitReviews = async () => {
  if (!order.value) return
  const items = order.value.items.map((item) => ({
    dish_id: item.dish_id,
    rating: reviewForm[item.dish_id]?.rating ?? 5,
    comment: reviewForm[item.dish_id]?.comment?.trim() || undefined,
  }))
  submittingReview.value = true
  try {
    await submitOrderReviews(order.value.id, { items })
    showSuccessToast(hasExistingReviews.value ? '评价已更新' : '评价成功')
    hasExistingReviews.value = true
  } catch (e: any) {
    showToast(e.response?.data?.detail || '提交评价失败')
  } finally {
    submittingReview.value = false
  }
}

const loadOrder = async () => {
  const id = Number(route.params.id)
  try {
    const { data } = await getOrder(id)
    order.value = data
    initReviewForm()
    if (canReview.value) {
      await loadExistingReviews()
    }
  } catch (e: any) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const formatTime = (t?: string) => {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN')
}

const markDishImageBroken = (dishId: number) => {
  brokenDishImageIds.value = new Set(brokenDishImageIds.value).add(dishId)
}

const goDishDetail = (item: OrderItem) => {
  if (!order.value || !item.dish_available) return
  router.push({
    name: 'DishDetail',
    params: { id: item.dish_id },
    query: { from_order: String(order.value.id) },
  })
}

const changeStatus = (status: string) => {
  updateOrderStatus(order.value!.id, status)
    .then(() => {
      showSuccessToast('状态已更新')
      loadOrder()
    })
    .catch((e: any) => {
      showToast(e.response?.data?.detail || '操作失败')
    })
}

const onCancel = () => {
  showConfirmDialog({ title: '确认取消', message: '确定取消此订单？' })
    .then(async () => {
      try {
        await cancelOrder(order.value!.id)
        showSuccessToast('已取消')
        router.push('/orders')
      } catch (e: any) {
        showToast(e.response?.data?.detail || '取消失败')
      }
    })
    .catch(() => {})
}

const onPermanentlyDelete = () => {
  if (!order.value) return
  showConfirmDialog({
    title: '永久删除订单',
    message: '订单明细和关联评价将无法恢复，确定继续吗？',
    confirmButtonText: '永久删除',
    confirmButtonColor: '#ee0a24',
  })
    .then(async () => {
      try {
        await permanentlyDeleteOrder(order.value!.id)
        showSuccessToast('订单已永久删除')
        await router.push('/orders')
      } catch (error: any) {
        showToast(error.response?.data?.detail || '删除失败')
      }
    })
    .catch(() => {})
}

onMounted(loadOrder)
</script>

<style scoped>
.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.status-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #fff;
  margin: 12px;
  border-radius: 8px;
}
.order-id {
  color: #969799;
  font-size: 14px;
}
.dish-item {
  display: flex;
  gap: 12px;
  align-items: center;
  width: 100%;
  padding: 12px 16px;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  background: #fff;
  border: 0;
  border-bottom: 1px solid #f5f5f5;
}
.dish-item:disabled {
  cursor: default;
}
.dish-item-disabled {
  color: #969799;
}
.dish-item-image {
  display: flex;
  flex: 0 0 64px;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  overflow: hidden;
  color: #c8c9cc;
  background: #f5f5f5;
  border-radius: 8px;
}
.dish-item-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dish-item-content {
  flex: 1;
  min-width: 0;
}
.dish-row {
  display: flex;
  justify-content: space-between;
}
.dish-arrow {
  flex: none;
  color: #969799;
}
.dish-name {
  font-weight: bold;
}
.dish-qty {
  color: #969799;
}
.dish-note {
  color: #ee0a24;
  font-size: 13px;
  margin-top: 4px;
}
.dish-unavailable {
  margin-top: 4px;
  font-size: 12px;
  color: #969799;
}
.action-buttons {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
}
.cancel-area {
  padding: 16px;
}

.permanent-delete-area {
  padding: 0 16px 16px;
}

.review-item {
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f5;
}

.review-dish-name {
  font-weight: bold;
  margin-bottom: 6px;
}

.review-rate-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-rating-text {
  font-size: 12px;
  color: #FF6B35;
}

.review-comment-field {
  margin-top: 6px;
  padding: 0;
  background: #f7f8fa;
  border-radius: 6px;
}

.review-submit-area {
  padding: 12px 16px;
}
</style>
