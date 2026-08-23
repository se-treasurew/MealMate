import apiClient from '@/utils/axios'

export interface ReviewItemPayload {
  dish_id: number
  rating: number
  comment?: string
}

export interface ReviewSubmitPayload {
  items: ReviewItemPayload[]
}

export interface Review {
  id: number
  dish_id: number
  order_id: number
  user_id: number
  user_nickname: string | null
  rating: number
  comment: string | null
  created_at?: string
  updated_at?: string
}

export interface ReviewItemStatus {
  dish_id: number
  review_id: number
  rating: number
  comment: string | null
  updated: boolean
}

export interface ReviewSubmitResult {
  order_id: number
  items: ReviewItemStatus[]
}

// 提交/修改订单评价（订单本人，仅已完成订单）
export const submitOrderReviews = (orderId: number, data: ReviewSubmitPayload) =>
  apiClient.post<ReviewSubmitResult>(`/api/orders/${orderId}/reviews`, data)

// 查询某订单已提交的评价（回显用，订单本人或饲养员）
export const getOrderReviews = (orderId: number) =>
  apiClient.get<Review[]>(`/api/orders/${orderId}/reviews`)

// 查询菜品公开评价列表（游客可读）
export const getDishReviews = (dishId: number) =>
  apiClient.get<Review[]>(`/api/dishes/${dishId}/reviews`)

// 删除评价（饲养员/店长）
export const deleteReview = (reviewId: number) =>
  apiClient.delete(`/api/reviews/${reviewId}`)
