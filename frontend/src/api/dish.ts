import apiClient from '@/utils/axios'

export interface Category {
  id: number
  name: string
  sort_order: number
}

export interface Tag {
  id: number
  name: string
}

export interface DishImage {
  id: number
  image_path: string
  thumbnail_path: string | null
  sort_order: number
}

export interface DishLink {
  id?: number
  url: string
  title?: string | null
}

export interface Dish {
  id: number
  name: string
  category_id: number
  description?: string | null
  notes?: string | null
  status: string
  created_by: number
  created_at?: string
  updated_at?: string
  images: DishImage[]
  links: DishLink[]
  tags: Tag[]
  // 聚合评分：无评分时 avg_rating 为 null
  avg_rating?: number | null
  rating_count?: number
}

export interface DishCreatePayload {
  name: string
  category_id: number
  description?: string
  notes?: string
  status?: string
  links: DishLink[]
  tag_names: string[]
}

export type DishUpdatePayload = Partial<DishCreatePayload>

// 图片 URL 拼接
export const imageUrl = (path: string | null | undefined): string => {
  if (!path) return ''
  if (path.startsWith('/avatars/')) return path
  if (path.startsWith('http')) return path
  const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
  return `${base}/uploads/${path}`
}

// ===== 分类 =====
export const getCategories = () => apiClient.get<Category[]>('/api/categories')
export const createCategory = (data: { name: string; sort_order?: number }) =>
  apiClient.post<Category>('/api/categories', data)
export const updateCategory = (id: number, data: Partial<Category>) =>
  apiClient.put<Category>(`/api/categories/${id}`, data)
export const deleteCategory = (id: number) =>
  apiClient.delete(`/api/categories/${id}`)

// ===== 标签 =====
export const getTags = () => apiClient.get<Tag[]>('/api/tags')
export const deleteTag = (id: number) => apiClient.delete(`/api/tags/${id}`)

// ===== 菜品 =====
export const getDishes = (params?: {
  category_id?: number
  status_filter?: string
  search?: string
}) => apiClient.get<Dish[]>('/api/dishes', { params })

export const getDish = (id: number) => apiClient.get<Dish>(`/api/dishes/${id}`)

export const createDish = (data: DishCreatePayload) =>
  apiClient.post<Dish>('/api/dishes', data)

export const updateDish = (id: number, data: DishUpdatePayload) =>
  apiClient.put<Dish>(`/api/dishes/${id}`, data)

export const deleteDish = (id: number) =>
  apiClient.delete(`/api/dishes/${id}`)

// ===== 菜品图片 =====
export const uploadDishImages = (dishId: number, files: File[]) => {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  return apiClient.post(`/api/dishes/${dishId}/images`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const deleteDishImage = (dishId: number, imageId: number) =>
  apiClient.delete(`/api/dishes/${dishId}/images/${imageId}`)
