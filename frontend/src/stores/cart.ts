import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface CartItem {
  dish_id: number
  dish_name: string
  unit_image: string
  price_label: string
  quantity: number
  item_note: string
}

const STORAGE_KEY = 'mealmate_cart'

function loadCart(): CartItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveCart(items: CartItem[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
}

export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>(loadCart())

  const totalCount = computed(() =>
    items.value.reduce((sum, i) => sum + i.quantity, 0)
  )

  // 生成 cart key（同菜品+同备注视为一项）
  const itemKey = (i: { dish_id: number; item_note: string }) =>
    `${i.dish_id}|${i.item_note}`

  const persist = () => saveCart(items.value)

  const addItem = (item: Omit<CartItem, 'quantity'> & { quantity?: number }) => {
    const qty = item.quantity ?? 1
    const key = itemKey(item)
    const existing = items.value.find((i) => itemKey(i) === key)
    if (existing) {
      existing.quantity += qty
    } else {
      items.value.push({ ...item, quantity: qty })
    }
    persist()
  }

  const updateQuantity = (idx: number, quantity: number) => {
    if (idx < 0 || idx >= items.value.length) return
    if (quantity <= 0) {
      items.value.splice(idx, 1)
    } else {
      items.value[idx].quantity = quantity
    }
    persist()
  }

  const removeItem = (idx: number) => {
    items.value.splice(idx, 1)
    persist()
  }

  const clear = () => {
    items.value = []
    persist()
  }

  return {
    items,
    totalCount,
    addItem,
    updateQuantity,
    removeItem,
    clear,
  }
})
