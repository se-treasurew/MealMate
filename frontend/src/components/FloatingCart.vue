<template>
  <div class="floating-cart" @click="handleClick" v-if="cartStore.totalCount > 0">
    <van-badge :content="cartStore.totalCount" max="99">
      <van-icon name="shopping-cart-o" size="24" color="#fff" />
    </van-badge>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const cartStore = useCartStore()

const handleClick = () => {
  router.push('/cart')
}
</script>

<style scoped>
.floating-cart {
  position: fixed;
  right: 16px;
  bottom: 80px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff6b35 0%, #ff8c5a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(255, 107, 53, 0.4);
  cursor: pointer;
  z-index: 1000;
  transition: all 0.3s ease;
}

.floating-cart:active {
  transform: scale(0.95);
  box-shadow: 0 2px 8px rgba(255, 107, 53, 0.4);
}

/* 为底部导航栏留出空间 */
@media (max-width: 768px) {
  .floating-cart {
    bottom: 70px;
  }
}
</style>
