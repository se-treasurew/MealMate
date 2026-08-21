<template>
  <div class="category-manage">
    <van-nav-bar title="分类管理" fixed left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="plus" size="20" @click="onAdd" />
      </template>
    </van-nav-bar>

    <div class="content" style="padding-top: 46px; padding-bottom: 50px">
      <van-loading v-if="loading" type="spinner" class="loading" />
      <template v-else>
        <van-swipe-cell v-for="cat in categories" :key="cat.id">
          <van-cell
            :title="cat.name"
            :label="`排序 ${cat.sort_order}`"
            :value="`${dishCount(cat.id)} 道菜品`"
            is-link
            @click="onEdit(cat)"
          />
          <template #right>
            <van-button square type="danger" text="删除" @click="onDelete(cat)" />
          </template>
        </van-swipe-cell>
        <van-empty v-if="categories.length === 0" description="暂无分类" />
      </template>
    </div>

    <!-- 新增/编辑弹层 -->
    <van-popup v-model:show="showEdit" position="bottom" round closeable>
      <div class="edit-popup">
        <h3>{{ editing?.id ? '编辑分类' : '新增分类' }}</h3>
        <van-form @submit="onSave">
          <van-cell-group inset>
            <van-field
              v-model="form.name"
              label="名称"
              placeholder="分类名称"
              maxlength="50"
              :rules="[{ required: true, message: '请输入名称' }]"
            />
            <van-field
              v-model="form.sortOrder"
              label="排序值"
              type="digit"
              placeholder="数字越小越靠前"
            />
          </van-cell-group>
          <div style="margin: 16px">
            <van-button round block type="primary" native-type="submit">
              保存
            </van-button>
          </div>
        </van-form>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import {
  getCategories,
  getDishes,
  createCategory,
  updateCategory,
  deleteCategory,
  type Category,
  type Dish,
} from '@/api/dish'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(false)
const categories = ref<Category[]>([])
const dishes = ref<Dish[]>([])

const showEdit = ref(false)
const editing = ref<Category | null>(null)
const form = reactive({ name: '', sortOrder: '0' })

const dishCount = (categoryId: number) =>
  dishes.value.filter((d) => d.category_id === categoryId).length

const load = async () => {
  loading.value = true
  try {
    const [catRes, dishRes] = await Promise.all([getCategories(), getDishes()])
    categories.value = catRes.data
    dishes.value = dishRes.data
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

const onAdd = () => {
  editing.value = null
  form.name = ''
  // 默认排序值取当前最大值 + 1，排到最后
  const maxSort = categories.value.reduce(
    (max, c) => Math.max(max, c.sort_order),
    -1
  )
  form.sortOrder = String(maxSort + 1)
  showEdit.value = true
}

const onEdit = (cat: Category) => {
  editing.value = cat
  form.name = cat.name
  form.sortOrder = String(cat.sort_order)
  showEdit.value = true
}

const onSave = async () => {
  const sort_order = Number(form.sortOrder) || 0
  try {
    if (editing.value) {
      await updateCategory(editing.value.id, { name: form.name, sort_order })
      showSuccessToast('更新成功')
    } else {
      await createCategory({ name: form.name, sort_order })
      showSuccessToast('创建成功')
    }
    showEdit.value = false
    await load()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败')
  }
}

const onDelete = (cat: Category) => {
  showConfirmDialog({ title: '确认删除', message: `删除分类"${cat.name}"？` })
    .then(async () => {
      try {
        await deleteCategory(cat.id)
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
.edit-popup {
  padding: 16px;
}
.edit-popup h3 {
  text-align: center;
  margin: 8px 0 16px;
}
</style>
