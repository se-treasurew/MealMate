<template>
  <div class="cart">
    <van-nav-bar title="点餐车" fixed />

    <div class="content" style="padding-top: 46px; padding-bottom: 80px">
      <van-empty v-if="cartStore.items.length === 0" description="点餐车空空如也">
        <van-button round type="primary" class="bottom-button" @click="goMenu">
          去点餐
        </van-button>
      </van-empty>

      <template v-else>
        <!-- 菜品列表 -->
        <van-swipe-cell
          v-for="(item, idx) in cartStore.items"
          :key="`${item.dish_id}-${item.item_note}`"
        >
          <van-card
            :title="item.dish_name"
            :thumb="item.unit_image"
            :desc="item.item_note ? `备注: ${item.item_note}` : ''"
          >
            <template #num>
              <van-stepper
                :model-value="item.quantity"
                min="0"
                max="99"
                @change="(v: number) => cartStore.updateQuantity(idx, v)"
              />
            </template>
          </van-card>
          <template #right>
            <van-button
              square
              type="danger"
              text="删除"
              class="delete-btn"
              @click="cartStore.removeItem(idx)"
            />
          </template>
        </van-swipe-cell>

        <!-- 整单备注 -->
        <van-cell-group inset style="margin-top: 12px">
          <van-field
            v-model="orderNote"
            label="整单备注"
            type="textarea"
            placeholder="如：少油、统一不要香菜"
            rows="2"
            autosize
          />
          <van-field label="期望用餐日期" is-link readonly :model-value="mealDateText" @click="showDatePicker = true" />
          <van-field label="餐次" is-link readonly :model-value="mealType" @click="showMealPicker = true" />
        </van-cell-group>

        <!-- 提交按钮 -->
        <div class="submit-bar">
          <div class="total">共 {{ cartStore.totalCount }} 件</div>
          <van-button round type="primary" :loading="submitting" @click="onSubmit">
            提交订单
          </van-button>
        </div>
      </template>
    </div>

    <!-- 日期选择 -->
    <van-popup v-model:show="showDatePicker" position="bottom" round>
      <van-date-picker
        v-model="dateValue"
        title="选择用餐日期"
        :min-date="minDate"
        @confirm="onPickDate"
        @cancel="showDatePicker = false"
      />
    </van-popup>

    <!-- 餐次选择 -->
    <van-popup v-model:show="showMealPicker" position="bottom" round>
      <van-picker
        :columns="mealOptions"
        @confirm="onPickMeal"
        @cancel="showMealPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import { useCartStore } from '@/stores/cart'
import { useUserStore } from '@/stores/user'
import { createOrder, type CartItem } from '@/api/order'

const router = useRouter()
const cartStore = useCartStore()
const userStore = useUserStore()

const orderNote = ref('')
const submitting = ref(false)
const showDatePicker = ref(false)
const showMealPicker = ref(false)
const mealType = ref('午餐')

// 日期：默认今天
const today = new Date()
const dateValue = ref<string[]>([
  String(today.getFullYear()),
  String(today.getMonth() + 1).padStart(2, '0'),
  String(today.getDate()).padStart(2, '0'),
])
const minDate = new Date(today.getFullYear(), today.getMonth(), today.getDate())
const mealDateText = computed(() => dateValue.value.join('-'))

const mealOptions = [
  { text: '早餐', value: '早餐' },
  { text: '午餐', value: '午餐' },
  { text: '晚餐', value: '晚餐' },
  { text: '夜宵', value: '夜宵' },
  { text: '自定义', value: '自定义' },
]

const onPickDate = ({ selectedValues }: { selectedValues: string[] }) => {
  dateValue.value = selectedValues
  showDatePicker.value = false
}

const onPickMeal = ({ selectedOptions }: { selectedOptions: { value: string }[] }) => {
  mealType.value = selectedOptions[0]?.value || '午餐'
  showMealPicker.value = false
}

const goMenu = () => router.push('/')

const onSubmit = () => {
  if (cartStore.items.length === 0) {
    showToast('点餐车为空')
    return
  }
  // 游客必须先登录才能下单（购物车 localStorage 保留，登录后继续）
  if (userStore.isGuest) {
    showConfirmDialog({
      title: '需要登录',
      message: '提交订单前请先登录，购物车会在登录后保留。',
      confirmButtonText: '去登录',
    })
      .then(() => {
        router.push({ path: '/login', query: { redirect: '/cart' } })
      })
      .catch(() => {})
    return
  }
  showConfirmDialog({
    title: '确认提交',
    message: `将提交 ${cartStore.totalCount} 件菜品的订单，期望 ${mealDateText.value} ${mealType.value}`,
  })
    .then(async () => {
      submitting.value = true
      try {
        const items: CartItem[] = cartStore.items.map((i) => ({
          dish_id: i.dish_id,
          quantity: i.quantity,
          item_note: i.item_note || undefined,
        }))
        await createOrder({
          meal_date: mealDateText.value,
          meal_type: mealType.value,
          note: orderNote.value || undefined,
          items,
        })
        cartStore.clear()
        orderNote.value = ''
        showSuccessToast('下单成功')
        setTimeout(() => router.push('/orders'), 800)
      } catch (e: any) {
        showToast(e.response?.data?.detail || '下单失败')
      } finally {
        submitting.value = false
      }
    })
    .catch(() => {})
}
</script>

<style scoped>
.bottom-button {
  width: 160px;
  height: 40px;
}
.delete-btn {
  height: 100%;
}
.submit-bar {
  position: fixed;
  bottom: 50px;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #eee;
}
.total {
  font-size: 16px;
  font-weight: bold;
}
</style>
