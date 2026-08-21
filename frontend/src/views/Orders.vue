<template>
  <div class="orders">
    <van-nav-bar title="我的订单" fixed />

    <div class="content" style="padding-top: 46px">
      <!-- 状态筛选 -->
      <van-tabs v-model:active="statusFilter" @change="loadOrders">
        <van-tab title="全部" name="" />
        <van-tab title="待处理" name="pending" />
        <van-tab title="进行中" name="accepted" />
        <van-tab title="已完成" name="done" />
        <van-tab title="已取消" name="cancelled" />
      </van-tabs>

      <!-- 下拉刷新 -->
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <van-loading v-if="loading" type="spinner" class="loading" />

        <template v-else>
          <van-empty v-if="orders.length === 0" description="暂无订单" />

          <div class="order-list" v-else>
            <van-card
              v-for="order in orders"
              :key="order.id"
              class="order-card"
              @click="goDetail(order.id)"
            >
              <template #title>
                <div class="order-title">
                  <span>订单 #{{ order.id }}</span>
                  <van-tag :type="statusColor(order.status)">{{ statusText(order.status) }}</van-tag>
                </div>
              </template>
              <template #desc>
                <div class="order-desc">
                  <div>{{ order.meal_date }} {{ order.meal_type }}</div>
                  <div class="order-items">
                    {{ itemsSummary(order) }}
                  </div>
                  <div v-if="userStore.isFeeder" class="order-user">
                    下单人：{{ order.user_nickname || '未知' }}
                  </div>
                </div>
              </template>
              <template #footer>
                <van-button
                  v-if="order.status === 'pending'"
                  size="small"
                  plain
                  type="danger"
                  @click.stop="onCancel(order)"
                >
                  取消订单
                </van-button>
              </template>
            </van-card>
          </div>
        </template>
      </van-pull-refresh>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import {
  getOrders,
  cancelOrder,
  statusText,
  statusColor,
  type Order,
} from '@/api/order'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const refreshing = ref(false)
const statusFilter = ref('')
const orders = ref<Order[]>([])

const loadOrders = async () => {
  loading.value = true
  try {
    // 饲养员默认看全部，饭团看自己的（后端按权限处理，这里按角色传参）
    const mineOnly = !userStore.isFeeder
    const { data } = await getOrders({
      status_filter: statusFilter.value || undefined,
      mine_only: mineOnly || undefined,
    })
    orders.value = data
  } catch (e: any) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const itemsSummary = (order: Order) => {
  return order.items.map((i) => `${i.dish_name} x${i.quantity}`).join('，')
}

const onRefresh = async () => {
  await loadOrders()
  refreshing.value = false
  showSuccessToast('刷新成功')
}

const goDetail = (id: number) => router.push(`/orders/${id}`)

const onCancel = (order: Order) => {
  showConfirmDialog({ title: '确认取消', message: '确定取消此订单？' })
    .then(async () => {
      try {
        await cancelOrder(order.id)
        showSuccessToast('已取消')
        await loadOrders()
      } catch (e: any) {
        showToast(e.response?.data?.detail || '取消失败')
      }
    })
    .catch(() => {})
}

onMounted(loadOrders)
</script>

<style scoped>
.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.order-list {
  padding: 8px;
}
.order-card {
  margin-bottom: 8px;
}
.order-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.order-desc {
  color: #646566;
  font-size: 13px;
  line-height: 1.8;
}
.order-items {
  color: #323233;
}
.order-user {
  color: #969799;
  font-size: 12px;
}
</style>
