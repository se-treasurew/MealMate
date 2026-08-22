<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { RouterView } from 'vue-router'
import AppTabbar from '@/components/AppTabbar.vue'
import { useAppUpdate } from '@/composables/useAppUpdate'

const route = useRoute()
const { updateAvailable, applyUpdate, dismissUpdate } = useAppUpdate()

// 只有主页面（首页/点餐车/订单/我的）显示底部导航
const showTabbar = computed(() =>
  ['Home', 'Cart', 'Orders', 'Profile'].includes(route.name as string)
)
</script>

<template>
  <div id="app">
    <RouterView />
    <AppTabbar v-if="showTabbar" />

    <div v-if="updateAvailable" class="app-update-banner" role="status">
      <span class="app-update-message">发现新版本</span>
      <div class="app-update-actions">
        <van-button size="small" plain type="primary" @click="dismissUpdate">
          稍后
        </van-button>
        <van-button size="small" type="primary" @click="applyUpdate">
          立即更新
        </van-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
#app {
  min-height: 100vh;
  background-color: #f7f8fa;
}

.app-update-banner {
  position: fixed;
  right: 84px;
  bottom: calc(50px + env(safe-area-inset-bottom) + 12px);
  left: 12px;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  color: #8a4b08;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 10px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
}

.app-update-message {
  min-width: 0;
  overflow: hidden;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.app-update-actions {
  display: flex;
  flex: none;
  gap: 8px;
}
</style>
