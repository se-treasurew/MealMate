<template>
  <div class="login">
    <div class="login-header">
      <h1>饭饭之交</h1>
      <p>MealMate</p>
    </div>

    <van-form @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="username"
          name="username"
          label="账号"
          placeholder="请输入账号"
          :rules="[{ required: true, message: '请输入账号' }]"
        />
        <van-field
          v-model="password"
          type="password"
          name="password"
          label="密码"
          placeholder="请输入密码"
          :rules="[{ required: true, message: '请输入密码' }]"
        />
      </van-cell-group>
      <div style="margin: 16px">
        <van-button round block type="primary" native-type="submit" :loading="loading">
          登录
        </van-button>
      </div>
      <div style="margin: 0 16px 16px; text-align: center">
        <van-button round block plain type="default" @click="onGuestMode">
          先随便逛逛
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showLoadingToast, closeToast } from 'vant'
import { login } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const username = ref('')
const password = ref('')
const loading = ref(false)

const onSubmit = async () => {
  if (loading.value) return
  loading.value = true
  try {
    showLoadingToast({ message: '登录中...', forbidClick: true })
    const { data } = await login({
      username: username.value,
      password: password.value,
    })

    userStore.setToken(
      data.access_token,
      data.refresh_token,
      data.must_change_password ?? false,
    )
    await userStore.fetchUser()
    closeToast()
    showToast({ message: '登录成功', type: 'success' })

    // 强制改密跳 /profile（守卫也会兜底），否则跳首页
    setTimeout(() => {
      if (userStore.mustChangePassword) {
        router.replace('/profile')
      } else {
        router.replace('/')
      }
    }, 500)
  } catch (error: any) {
    closeToast()
    const message = error.response?.data?.detail || '登录失败，请重试'
    showToast({ message, type: 'fail' })
  } finally {
    loading.value = false
  }
}

const onGuestMode = () => {
  // 游客态：清掉可能残留的 token 后跳首页
  userStore.logout()
  router.replace('/')
}
</script>

<style scoped>
.login {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 20px;
  background: linear-gradient(135deg, #ff6b35 0%, #ff9068 100%);
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
  color: white;
}

.login-header h1 {
  font-size: 36px;
  margin-bottom: 8px;
}

.login-header p {
  font-size: 16px;
  opacity: 0.9;
}
</style>
