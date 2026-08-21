<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { RouterView } from 'vue-router'
import AppTabbar from '@/components/AppTabbar.vue'

const route = useRoute()

// 只有主页面（首页/点餐车/订单/我的）显示底部导航
const showTabbar = computed(() =>
  ['Home', 'Cart', 'Orders', 'Profile'].includes(route.name as string)
)
</script>

<template>
  <div id="app">
    <RouterView />
    <AppTabbar v-if="showTabbar" />
  </div>
</template>

<style scoped>
#app {
  min-height: 100vh;
  background-color: #f7f8fa;
}
</style>
