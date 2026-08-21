import apiClient from '@/utils/axios'

export interface LoginData {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  // 首次登录/被重置密码后为 true，前端需强制引导改密
  must_change_password?: boolean
}

export interface UserInfo {
  id: number
  username: string
  nickname: string | null
  avatar_url: string | null
  is_admin: boolean
  is_feeder: boolean
  is_active?: boolean
  must_change_password?: boolean
}

export interface UpdateProfilePayload {
  nickname?: string | null
  avatar_url?: string | null
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}

export interface RefreshTokenPayload {
  refresh_token: string
}

// 登录
export const login = (data: LoginData) => {
  return apiClient.post<TokenResponse>('/api/auth/login', data)
}

// 获取当前用户信息
export const getCurrentUser = () => {
  return apiClient.get<UserInfo>('/api/auth/me')
}

// 更新个人资料（昵称 / 头像 URL）
export const updateProfile = (data: UpdateProfilePayload) => {
  return apiClient.put<UserInfo>('/api/auth/profile', data)
}

// 修改自己的密码
export const changePassword = (data: ChangePasswordPayload) => {
  return apiClient.put<TokenResponse>('/api/auth/password', data)
}

// 上传自定义头像（FormData）
export const uploadAvatar = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return apiClient.post<UserInfo>('/api/auth/avatar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
