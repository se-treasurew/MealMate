<template>
  <div class="tag-manage">
    <van-nav-bar title="标签管理" fixed left-arrow @click-left="$router.back()" />

    <div class="content" style="padding-top: 46px; padding-bottom: 50px">
      <van-loading v-if="loading" type="spinner" class="loading" />
      <template v-else>
        <p class="hint">标签在菜品编辑页自由输入创建，这里仅用于查看和清理。</p>
        <van-swipe-cell v-for="tag in tags" :key="tag.id">
          <van-cell :title="tag.name" :value="`${dishCount(tag.id)} 道菜品`" />
          <template #right>
            <van-button square type="danger" text="删除" @click="onDelete(tag)" />
          </template>
        </van-swipe-cell>
        <van-empty v-if="tags.length === 0" description="暂无标签" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import { getTags, getDishes, deleteTag, type Tag, type Dish } from '@/api/dish'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(false)
const tags = ref<Tag[]>([])
const dishes = ref<Dish[]>([])

const dishCount = (tagId: number) =>
  dishes.value.filter((d) => d.tags.some((t) => t.id === tagId)).length

const load = async () => {
  loading.value = true
  try {
    const [tagRes, dishRes] = await Promise.all([getTags(), getDishes()])
    tags.value = tagRes.data
    dishes.value = dishRes.data
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

const onDelete = (tag: Tag) => {
  showConfirmDialog({ title: '确认删除', message: `删除标签"${tag.name}"？` })
    .then(async () => {
      try {
        await deleteTag(tag.id)
        showSuccessToast('已删除')
        await load()
      } catch (e: any) {
        showToast(e.response?.data?.detail || '删除失败')
      }
    })
    .catch(() => {})
}

onMounted(() => {
  if (!userStore.isFeeder) {
    showToast('无权限')
    return
  }
  load()
})
</script>

<style scoped>
.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.hint {
  padding: 8px 16px;
  color: #969799;
  font-size: 13px;
}
</style>
