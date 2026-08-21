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
          <div v-for="item in order.items" :key="item.id" class="dish-item">
            <div class="dish-row">
              <span class="dish-name">{{ item.dish_name }}</span>
              <span class="dish-qty">x{{ item.quantity }}</span>
            </div>
            <div v-if="item.item_note" class="dish-note">备注：{{ item.item_note }}</div>
          </div>
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
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import {
  getOrder,
  updateOrderStatus,
  cancelOrder,
  statusText,
  statusColor,
  type Order,
} from '@/api/order'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const order = ref<Order | null>(null)

const loadOrder = async () => {
  const id = Number(route.params.id)
  try {
    const { data } = await getOrder(id)
    order.value = data
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
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f5;
}
.dish-row {
  display: flex;
  justify-content: space-between;
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
.action-buttons {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
}
.cancel-area {
  padding: 16px;
}
</style>
