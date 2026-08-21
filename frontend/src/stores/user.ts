import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCurrentUser, type UserInfo } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  // v1 不再支持免密多账号切换，清除旧版本遗留的长期令牌列表。
  localStorage.removeItem('mealmate_accounts')
  const user = ref<UserInfo | null>(null)
  const token = ref<string>(localStorage.getItem('access_token') || '')
  const refreshTk = ref<string>(localStorage.getItem('refresh_token') || '')
  const currentMode = ref<'diner' | 'feeder'>('diner')

  // 首次登录/被重置密码后置 true，前端需强制引导改密
  const mustChangePassword = ref<boolean>(false)

  // 是否饲养员（店长默认是饲养员）
  const isFeeder = computed(
    () => !!user.value && (user.value.is_feeder || user.value.is_admin)
  )
  const isAdmin = computed(() => !!user.value?.is_admin)
  const isLoggedIn = computed(() => !!token.value && !!user.value)
  // 游客：未登录态（无 token 或无 user）
  const isGuest = computed(() => !token.value || !user.value)

  // 当前角色显示名称
  const roleName = computed(() => {
    if (!user.value) return ''
    if (user.value.is_admin) return '店长'
    if (user.value.is_feeder) return '饲养员'
    return '饭团'
  })

  // 设置 token
  const setToken = (
    accessToken: string,
    refreshToken: string,
    mustChange: boolean = false,
  ) => {
    token.value = accessToken
    refreshTk.value = refreshToken
    mustChangePassword.value = mustChange
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken)
  }

  // 设置用户信息
  const setUser = (userData: UserInfo) => {
    user.value = userData
    if (typeof userData.must_change_password === 'boolean') {
      mustChangePassword.value = userData.must_change_password
    }
    // 默认模式：饲养员默认进投喂模式
    if (isFeeder.value) {
      currentMode.value = 'feeder'
    }
  }

  // 获取当前用户信息
  const fetchUser = async () => {
    if (!token.value) return null
    try {
      const { data } = await getCurrentUser()
      setUser(data)
      return data
    } catch (error) {
      logout()
      return null
    }
  }

  // 切换模式
  const switchMode = () => {
    if (isFeeder.value) {
      currentMode.value = currentMode.value === 'diner' ? 'feeder' : 'diner'
    }
  }

  // 退出登录
  const logout = () => {
    user.value = null
    token.value = ''
    refreshTk.value = ''
    currentMode.value = 'diner'
    mustChangePassword.value = false
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  return {
    user,
    token,
    currentMode,
    mustChangePassword,
    isFeeder,
    isAdmin,
    isLoggedIn,
    isGuest,
    roleName,
    setToken,
    setUser,
    fetchUser,
    switchMode,
    logout,
  }
})
