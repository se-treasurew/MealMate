<template>
  <div class="orders">
    <van-nav-bar title="我的订单" fixed />

    <div
      class="content swipe-surface"
      style="padding-top: 46px"
      @touchstart="onTouchStart"
      @touchmove="onTouchMove"
      @touchend="onTouchEnd"
      @touchcancel="onTouchCancel"
      @click.capture="onClickCapture"
    >
      <!-- 状态筛选 -->
      <van-tabs
        v-model:active="statusFilter"
        animated
        @change="onStatusChange"
      >
        <van-tab
          v-for="tab in ORDER_TABS"
          :key="tab.name || 'all'"
          :title="tab.title"
          :name="tab.name"
        >
          <div class="order-page">
            <van-pull-refresh
              v-model="orderPages[tab.name].refreshing"
              @refresh="onRefresh(tab.name)"
            >
              <van-loading
                v-if="orderPages[tab.name].loading"
                type="spinner"
                class="loading"
              />

              <template v-else>
                <van-empty
                  v-if="orderPages[tab.name].orders.length === 0"
                  :description="orderPages[tab.name].error ? '加载失败，请下拉刷新' : '暂无订单'"
                />

                <div class="order-list" v-else>
                  <van-card
                    v-for="order in orderPages[tab.name].orders"
                    :key="order.id"
                    class="order-card"
                    @click="goDetail(order.id)"
                  >
                    <template #title>
                      <div class="order-title">
                        <span>订单 #{{ order.id }}</span>
                        <van-tag :type="statusColor(order.status)">
                          {{ statusText(order.status) }}
                        </van-tag>
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
                      <div class="order-footer">
                        <van-button
                          v-if="canReview(order)"
                          size="small"
                          plain
                          type="primary"
                          @click.stop="goDetail(order.id)"
                        >
                          去评价
                        </van-button>
                        <van-button
                          v-if="canCancel(order)"
                          size="small"
                          plain
                          type="danger"
                          @click.stop="onCancel(order)"
                        >
                          取消订单
                        </van-button>
                        <van-button
                          v-if="canPermanentlyDelete(order)"
                          size="small"
                          plain
                          type="danger"
                          @click.stop="onPermanentlyDelete(order)"
                        >
                          永久删除
                        </van-button>
                      </div>
                    </template>
                  </van-card>
                </div>
              </template>
            </van-pull-refresh>
          </div>
        </van-tab>
      </van-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import {
  getOrders,
  cancelOrder,
  permanentlyDeleteOrder,
  statusText,
  statusColor,
  type Order,
} from '@/api/order'
import { useUserStore } from '@/stores/user'
import { useHorizontalSwipe } from '@/composables/useHorizontalSwipe'

const router = useRouter()
const userStore = useUserStore()

type OrderStatusFilter = '' | 'pending' | 'accepted' | 'cooking' | 'done' | 'cancelled'

const ORDER_TABS: ReadonlyArray<{ title: string; name: OrderStatusFilter }> = [
  { title: '全部', name: '' },
  { title: '待处理', name: 'pending' },
  { title: '已接单', name: 'accepted' },
  { title: '制作中', name: 'cooking' },
  { title: '已完成', name: 'done' },
  { title: '已取消', name: 'cancelled' },
]

interface OrderPage {
  orders: Order[]
  loading: boolean
  refreshing: boolean
  loaded: boolean
  error: boolean
  requestId: number
}

const createOrderPage = (): OrderPage => ({
  orders: [],
  loading: false,
  refreshing: false,
  loaded: false,
  error: false,
  requestId: 0,
})

const statusFilter = ref<OrderStatusFilter>('')
const orderPages = reactive<Record<OrderStatusFilter, OrderPage>>({
  '': createOrderPage(),
  pending: createOrderPage(),
  accepted: createOrderPage(),
  cooking: createOrderPage(),
  done: createOrderPage(),
  cancelled: createOrderPage(),
})

const loadOrders = async (filter = statusFilter.value, force = false) => {
  const page = orderPages[filter]
  if (!force && page.loaded) return true

  const requestId = ++page.requestId
  if (!page.refreshing) {
    page.loading = true
  }
  page.error = false
  let succeeded = false

  try {
    // 饲养员默认看全部，饭团看自己的（后端按权限处理，这里按角色传参）
    const mineOnly = !userStore.isFeeder
    const { data } = await getOrders({
      status_filter: filter || undefined,
      mine_only: mineOnly || undefined,
    })
    if (page.requestId === requestId) {
      page.orders = data
      page.loaded = true
      succeeded = true
    }
  } catch (e: any) {
    if (page.requestId === requestId) {
      page.error = true
      showToast(e.response?.data?.detail || '加载失败')
    }
  } finally {
    if (page.requestId === requestId) {
      page.loading = false
      page.refreshing = false
    }
  }

  return succeeded
}

const itemsSummary = (order: Order) => {
  return order.items.map((i) => `${i.dish_name} x${i.quantity}`).join('，')
}

// 已完成且是本人订单时可评价（饲养员看全部订单时不显示评价入口）
const canReview = (order: Order) =>
  order.status === 'done' && order.user_id === userStore.user?.id

const canCancel = (order: Order) =>
  order.status === 'pending' && order.user_id === userStore.user?.id

const canPermanentlyDelete = (order: Order) =>
  userStore.isAdmin && (order.status === 'done' || order.status === 'cancelled')

const onStatusChange = (name: string | number) => {
  const filter = String(name) as OrderStatusFilter
  statusFilter.value = filter
  void loadOrders(filter)
}

const statusIndex = () =>
  ORDER_TABS.findIndex((tab) => tab.name === statusFilter.value)

const switchStatus = (step: -1 | 1) => {
  const index = statusIndex()
  const target = ORDER_TABS[index + step]
  if (!target) return

  statusFilter.value = target.name
  void loadOrders(target.name)
}

const { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel, onClickCapture } =
  useHorizontalSwipe({
    onNext: () => switchStatus(1),
    onPrevious: () => switchStatus(-1),
    canNext: () => {
      const index = statusIndex()
      return index >= 0 && index < ORDER_TABS.length - 1
    },
    canPrevious: () => statusIndex() > 0,
    excludeSelector: '.van-nav-bar, .van-tabbar, .van-tabs__wrap',
  })

const onRefresh = async (filter: OrderStatusFilter) => {
  const succeeded = await loadOrders(filter, true)
  if (succeeded) {
    showSuccessToast('刷新成功')
  }
}

const goDetail = (id: number) => router.push(`/orders/${id}`)

const invalidateOrderPage = (filter: OrderStatusFilter) => {
  const page = orderPages[filter]
  page.requestId += 1
  page.orders = []
  page.loading = false
  page.refreshing = false
  page.loaded = false
  page.error = false
}

const onCancel = (order: Order) => {
  showConfirmDialog({ title: '确认取消', message: '确定取消此订单？' })
    .then(async () => {
      try {
        await cancelOrder(order.id)
        showSuccessToast('已取消')
        invalidateOrderPage('')
        invalidateOrderPage('pending')
        invalidateOrderPage('cancelled')
        await loadOrders(statusFilter.value, true)
      } catch (e: any) {
        showToast(e.response?.data?.detail || '取消失败')
      }
    })
    .catch(() => {})
}

const onPermanentlyDelete = (order: Order) => {
  showConfirmDialog({
    title: '永久删除订单',
    message: '订单明细和关联评价将无法恢复，确定继续吗？',
    confirmButtonText: '永久删除',
    confirmButtonColor: '#ee0a24',
  })
    .then(async () => {
      try {
        await permanentlyDeleteOrder(order.id)
        showSuccessToast('订单已永久删除')
        invalidateOrderPage('')
        invalidateOrderPage(order.status as OrderStatusFilter)
        await loadOrders(statusFilter.value, true)
      } catch (error: any) {
        showToast(error.response?.data?.detail || '删除失败')
      }
    })
    .catch(() => {})
}

onMounted(() => {
  void loadOrders('')
})
</script>

<style scoped>
.swipe-surface {
  min-height: calc(100svh - 50px);
  touch-action: pan-y;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.order-page {
  min-height: 240px;
}
.order-list {
  padding: 8px;
}
.order-card {
  margin-bottom: 8px;
}
.order-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
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
