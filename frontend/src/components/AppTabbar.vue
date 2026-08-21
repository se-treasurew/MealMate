<template>
  <van-tabbar v-model="active" route fixed placeholder>
    <van-tabbar-item icon="home-o" to="/">首页</van-tabbar-item>
    <van-tabbar-item icon="cart-o" to="/cart" :badge="badge">点餐车</van-tabbar-item>
    <van-tabbar-item icon="orders-o" to="/orders">订单</van-tabbar-item>
    <van-tabbar-item icon="user-o" to="/profile">我的</van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useCartStore } from '@/stores/cart'

const active = ref(0)
const cartStore = useCartStore()
const badge = computed(() => (cartStore.totalCount > 0 ? cartStore.totalCount : ''))
</script>
