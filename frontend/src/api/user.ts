import apiClient from '@/utils/axios'
import type { UserInfo } from '@/api/auth'

// 列表项与 UserInfo 字段基本一致，独立导出便于后端扩展字段时集中维护
export interface UserListItem {
  id: number
  username: string
  nickname: string | null
  avatar_url: string | null
  is_admin: boolean
  is_feeder: boolean
  is_active: boolean
  created_at?: string | null
}

export interface UserCreatePayload {
  username: string
  password: string
  nickname?: string | null
  is_feeder?: boolean
}

export interface UserFeederPayload {
  is_feeder: boolean
}

export interface UserStatusPayload {
  is_active: boolean
}

export interface PasswordResetPayload {
  password: string
}

// 列出所有用户
export const getUsers = () =>
  apiClient.get<UserListItem[]>('/api/users')

// 创建账号
export const createUser = (data: UserCreatePayload) =>
  apiClient.post<UserListItem>('/api/users', data)

// 切换饲养员权限
export const updateUserFeeder = (id: number, data: UserFeederPayload) =>
  apiClient.put<UserListItem>(`/api/users/${id}/feeder`, data)

// 启用/禁用账号
export const updateUserStatus = (id: number, data: UserStatusPayload) =>
  apiClient.put<UserListItem>(`/api/users/${id}/status`, data)

// 管理员重置密码
export const resetUserPassword = (id: number, data: PasswordResetPayload) =>
  apiClient.put<UserListItem>(`/api/users/${id}/password`, data)

// 重新导出便于上层使用
export type { UserInfo }
