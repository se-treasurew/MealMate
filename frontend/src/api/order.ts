import apiClient from '@/utils/axios'

export interface OrderItemData {
  dish_id: number
  quantity: number
  item_note?: string
}

// 用于提交订单的单项数据
export type CartItem = OrderItemData

export interface OrderItem extends OrderItemData {
  id: number
  dish_name: string
}

export interface Order {
  id: number
  user_id: number
  user_nickname: string | null
  meal_date: string
  meal_type: string
  status: string
  note: string | null
  created_at?: string
  updated_at?: string
  items: OrderItem[]
}

export interface CreateOrderPayload {
  meal_date: string
  meal_type: string
  note?: string
  items: OrderItemData[]
}

export const statusText = (status: string): string => {
  const map: Record<string, string> = {
    pending: '待处理',
    accepted: '已接单',
    cooking: '制作中',
    done: '已完成',
    cancelled: '已取消',
  }
  return map[status] || status
}

// Vant 4 van-tag 的 type 取值
type TagType = 'primary' | 'success' | 'danger' | 'warning' | 'default'

export const statusColor = (status: string): TagType => {
  const map: Record<string, TagType> = {
    pending: 'warning',
    accepted: 'primary',
    cooking: 'primary',
    done: 'success',
    cancelled: 'default',
  }
  return map[status] || 'default'
}

export const getOrders = (params?: { status_filter?: string; mine_only?: boolean }) =>
  apiClient.get<Order[]>('/api/orders', { params })

export const getOrder = (id: number) => apiClient.get<Order>(`/api/orders/${id}`)

export const createOrder = (data: CreateOrderPayload) =>
  apiClient.post<Order>('/api/orders', data)

export const updateOrderStatus = (id: number, status: string, note?: string) =>
  apiClient.patch<Order>(`/api/orders/${id}`, { status, note })

export const cancelOrder = (id: number) => apiClient.delete(`/api/orders/${id}`)
