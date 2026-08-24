<template>
  <div class="dish-manage">
    <van-nav-bar title="菜品管理" fixed left-arrow @click-left="$router.back()">
      <template #right>
        <div style="display: flex; align-items: center; gap: 16px">
          <van-icon name="label-o" size="20" @click="$router.push('/admin/tags')" />
          <van-icon name="bars" size="20" @click="$router.push('/admin/categories')" />
          <van-icon name="plus" size="20" @click="onAdd" />
        </div>
      </template>
    </van-nav-bar>

    <div class="content" style="padding-top: 46px; padding-bottom: 50px">
      <!-- 搜索 -->
      <van-search v-model="search" placeholder="搜索菜品" @search="loadDishes" />

      <!-- 状态筛选 -->
      <van-tabs v-model:active="statusFilter" @change="loadDishes">
        <van-tab title="上架中" name="active" />
        <van-tab title="已下架" name="inactive" />
        <van-tab title="全部" name="" />
      </van-tabs>

      <!-- 菜品列表 -->
      <van-loading v-if="loading" type="spinner" class="loading" />
      <template v-else>
        <van-swipe-cell v-for="dish in dishes" :key="dish.id">
          <van-card
            :title="dish.name"
            :desc="dish.description || '暂无描述'"
            :thumb="getCoverImage(dish)"
            @click="onEdit(dish)"
          >
            <template #tags>
              <van-tag :type="dish.status === 'active' ? 'success' : 'default'">
                {{ dish.status === 'active' ? '上架' : '下架' }}
              </van-tag>
              <van-tag plain type="primary" v-if="getCategoryName(dish.category_id)">
                {{ getCategoryName(dish.category_id) }}
              </van-tag>
            </template>
          </van-card>
          <template #right>
            <van-button
              square
              :type="dish.status === 'active' ? 'warning' : 'primary'"
              :text="dish.status === 'active' ? '下架' : '上架'"
              @click="onToggleStatus(dish)"
            />
            <van-button square type="danger" text="删除" @click="onDelete(dish)" />
          </template>
        </van-swipe-cell>
        <van-empty v-if="dishes.length === 0" description="暂无菜品" />
      </template>
    </div>

    <!-- 编辑弹层 -->
    <van-popup
      v-model:show="showEdit"
      position="bottom"
      :style="{ height: '90%' }"
      round
      closeable
    >
      <div class="edit-popup">
        <h3>{{ editingDish?.id ? '编辑菜品' : '新增菜品' }}</h3>
        <van-form @submit="onSave">
          <van-cell-group inset>
            <van-field
              v-model="form.name"
              label="名称"
              placeholder="菜品名称"
              :rules="[{ required: true, message: '请输入名称' }]"
            />
            <van-field label="分类" is-link :model-value="getCategoryName(form.category_id) || '请选择'" @click="showCategoryPicker = true" readonly />
            <van-field
              v-model="form.description"
              label="做法"
              type="textarea"
              placeholder="详细做法，支持 Markdown：# 标题、1. 步骤、**加粗**"
              rows="3"
              autosize
            />
            <div class="md-preview-toggle" @click="showMdPreview = !showMdPreview">
              {{ showMdPreview ? '收起预览' : '预览 Markdown' }}
            </div>
            <div
              v-if="showMdPreview"
              class="md-preview markdown-body"
              v-html="renderMarkdown(form.description) || '<span style=\'color:#c8c9cc\'>暂无内容</span>'"
            ></div>
            <van-field
              v-model="form.notes"
              label="备注"
              type="textarea"
              placeholder="营养信息、适合人群等"
              rows="2"
              autosize
            />
            <van-field label="标签">
              <template #input>
                <div class="tag-editor">
                  <div class="tag-selected" v-if="selectedTagNames.length">
                    <van-tag
                      v-for="name in selectedTagNames"
                      :key="name"
                      closeable
                      type="primary"
                      @close="removeTag(name)"
                    >
                      {{ name }}
                    </van-tag>
                  </div>
                  <div class="tag-input-row">
                    <van-field
                      v-model="newTagName"
                      placeholder="输入标签名后回车添加"
                      maxlength="50"
                      @keyup.enter="addTag"
                    >
                      <template #button>
                        <van-button size="small" type="primary" plain @click="addTag">
                          添加
                        </van-button>
                      </template>
                    </van-field>
                  </div>
                  <div class="tag-quick-pick" v-if="unselectedTags.length">
                    <van-tag
                      v-for="tag in unselectedTags"
                      :key="tag.id"
                      plain
                      @click="selectedTagNames.push(tag.name)"
                    >
                      {{ tag.name }}
                    </van-tag>
                  </div>
                </div>
              </template>
            </van-field>
          </van-cell-group>

          <!-- 图片上传 -->
          <div class="image-section">
            <div class="section-title">菜品图片</div>
            <van-uploader
              v-model="fileList"
              :after-read="onAfterRead"
              :max-size="5 * 1024 * 1024"
              :disabled="saving"
              @oversize="showToast('图片不能超过 5MB')"
              multiple
              :max-count="5"
            />
            <div v-if="!editingDish" class="upload-hint">
              所选图片将在保存菜品后上传，每次最多 5 张
            </div>
            <div class="image-preview" v-if="editingDish?.images.length">
              <div
                v-for="img in editingDish.images"
                :key="img.id"
                class="image-item"
              >
                <img :src="imageUrl(img.thumbnail_path || img.image_path)" />
                <van-icon name="cross" class="del-icon" @click="onDeleteImage(img.id)" />
              </div>
            </div>
          </div>

          <!-- 参考链接 -->
          <div class="link-section">
            <div class="section-title">参考链接</div>
            <div v-for="(link, idx) in form.links" :key="idx" class="link-row">
              <van-field v-model="link.url" placeholder="URL" />
              <van-field v-model="link.title" placeholder="标题（可选）" />
              <van-button size="small" type="danger" @click="form.links.splice(idx, 1)">
                删除
              </van-button>
            </div>
            <van-button size="small" plain type="primary" @click="form.links.push({ url: '', title: '' })">
              + 添加链接
            </van-button>
          </div>

          <div style="margin: 16px">
            <van-button
              round
              block
              type="primary"
              native-type="submit"
              :loading="saving"
              :disabled="saving"
            >
              保存
            </van-button>
          </div>
        </van-form>
      </div>
    </van-popup>

    <!-- 分类选择 -->
    <van-popup v-model:show="showCategoryPicker" position="bottom" round>
      <van-picker
        :columns="categoryColumns"
        @confirm="onPickCategory"
        @cancel="showCategoryPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { showToast, showConfirmDialog, showSuccessToast } from 'vant'
import type { UploaderFileListItem } from 'vant'
import {
  getDishes,
  getCategories,
  getTags,
  createDish,
  updateDish,
  deleteDish,
  uploadDishImages,
  deleteDishImage,
  imageUrl,
  type Dish,
  type Category,
  type Tag,
} from '@/api/dish'
import { useUserStore } from '@/stores/user'
import { renderMarkdown } from '@/utils/markdown'

const userStore = useUserStore()

const loading = ref(false)
const search = ref('')
const statusFilter = ref('')  // 默认显示全部状态
const showMdPreview = ref(true)  // 默认展开渲染后的 Markdown 预览
const dishes = ref<Dish[]>([])
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])

const showEdit = ref(false)
const editingDish = ref<Dish | null>(null)
const showCategoryPicker = ref(false)
const fileList = ref<UploaderFileListItem[]>([])
const saving = ref(false)

const form = reactive({
  name: '',
  category_id: 0,
  description: '',
  notes: '',
  links: [] as { url: string; title: string }[],
})

const selectedTagNames = ref<string[]>([])
const newTagName = ref('')

const unselectedTags = computed(() =>
  tags.value.filter((t) => !selectedTagNames.value.includes(t.name))
)

const addTag = () => {
  const name = newTagName.value.trim()
  if (!name) {
    showToast('标签名不能为空')
    return
  }
  if (selectedTagNames.value.includes(name)) {
    showToast('标签已添加')
    return
  }
  if (selectedTagNames.value.length >= 10) {
    showToast('最多添加 10 个标签')
    return
  }
  selectedTagNames.value.push(name)
  newTagName.value = ''
}

const removeTag = (name: string) => {
  selectedTagNames.value = selectedTagNames.value.filter((n) => n !== name)
}

const categoryColumns = computed(() =>
  categories.value.map((c) => ({ text: c.name, value: c.id }))
)

const loadDishes = async () => {
  loading.value = true
  try {
    const { data } = await getDishes({
      search: search.value || undefined,
      status_filter: statusFilter.value || undefined,
    })
    dishes.value = data
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

const getCoverImage = (dish: Dish) => {
  if (dish.images && dish.images.length > 0) {
    return imageUrl(dish.images[0].thumbnail_path || dish.images[0].image_path)
  }
  return ''
}

const getCategoryName = (id: number) =>
  categories.value.find((c) => c.id === id)?.name || ''

const resetForm = () => {
  form.name = ''
  form.category_id = categories.value[0]?.id || 0
  form.description = ''
  form.notes = ''
  form.links = []
  fileList.value = []
  selectedTagNames.value = []
  newTagName.value = ''
}

const onAdd = () => {
  editingDish.value = null
  resetForm()
  showEdit.value = true
}

const onEdit = (dish: Dish) => {
  editingDish.value = dish
  form.name = dish.name
  form.category_id = dish.category_id
  form.description = dish.description || ''
  form.notes = dish.notes || ''
  selectedTagNames.value = dish.tags.map((t) => t.name)
  newTagName.value = ''
  form.links = dish.links.map((l) => ({ url: l.url, title: l.title || '' }))
  fileList.value = []
  showEdit.value = true
}

const onPickCategory = ({ selectedOptions }: { selectedOptions: { value: number }[] }) => {
  form.category_id = selectedOptions[0]?.value || 0
  showCategoryPicker.value = false
}

const onSave = async () => {
  if (saving.value) return
  if (!form.category_id) {
    showToast('请选择分类')
    return
  }
  saving.value = true
  try {
    if (editingDish.value) {
      await updateDish(editingDish.value.id, {
        name: form.name,
        category_id: form.category_id,
        description: form.description,
        notes: form.notes,
        tag_names: selectedTagNames.value,
        links: form.links.filter((l) => l.url),
      })
      showSuccessToast('更新成功')
    } else {
      const { data } = await createDish({
        name: form.name,
        category_id: form.category_id,
        description: form.description,
        notes: form.notes,
        status: 'active',
        tag_names: selectedTagNames.value,
        links: form.links.filter((l) => l.url),
      })
      editingDish.value = data
      // 上传图片
      if (fileList.value.length) {
        const files = fileList.value
          .map((f) => f.file)
          .filter(Boolean) as File[]
        if (files.length) {
          try {
            await uploadDishImages(data.id, files)
          } catch (e) {
            fileList.value = []
            await Promise.all([loadDishes(), loadTags()])
            showToast('菜品已创建，但图片上传失败，请重新选择图片')
            return
          }
        }
      }
      showSuccessToast('创建成功')
    }
    showEdit.value = false
    await Promise.all([loadDishes(), loadTags()])
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const onToggleStatus = async (dish: Dish) => {
  try {
    await updateDish(dish.id, {
      status: dish.status === 'active' ? 'inactive' : 'active',
    })
    showSuccessToast(dish.status === 'active' ? '已下架' : '已上架')
    await loadDishes()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '操作失败')
  }
}

const onDelete = (dish: Dish) => {
  showConfirmDialog({ title: '确认删除', message: `删除菜品"${dish.name}"？` })
    .then(async () => {
      try {
        await deleteDish(dish.id)
        showSuccessToast('已删除')
        await loadDishes()
      } catch (e: any) {
        showToast(e.response?.data?.detail || '删除失败')
      }
    })
    .catch(() => {})
}

const onAfterRead = async (items: UploaderFileListItem | UploaderFileListItem[]) => {
  const arr = Array.isArray(items) ? items : [items]
  if (!editingDish.value) return
  const files = arr.map((i) => i.file).filter(Boolean) as File[]
  if (!files.length) return
  try {
    await uploadDishImages(editingDish.value.id, files)
    showSuccessToast('上传成功')
    // 刷新菜品数据
    const { data } = await getDishes()
    const updated = data.find((d) => d.id === editingDish.value!.id)
    if (updated) editingDish.value = updated
    fileList.value = []
  } catch (e: any) {
    showToast(e.response?.data?.detail || '上传失败')
  }
}

const onDeleteImage = (imageId: number) => {
  const dish = editingDish.value
  if (!dish) return
  showConfirmDialog({ title: '确认', message: '删除这张图片？' })
    .then(async () => {
      try {
        await deleteDishImage(dish.id, imageId)
        dish.images = dish.images.filter((i) => i.id !== imageId)
        showSuccessToast('已删除')
      } catch (e: any) {
        showToast(e.response?.data?.detail || '删除失败')
      }
    })
    .catch(() => {})
}

const loadTags = async () => {
  try {
    const { data } = await getTags()
    tags.value = data
  } catch (e) {
    showToast('加载标签失败')
  }
}

onMounted(async () => {
  // 权限校验
  if (!userStore.isFeeder) {
    showToast('无权限')
    return
  }
  try {
    const [catRes, tagRes] = await Promise.all([getCategories(), getTags()])
    categories.value = catRes.data
    tags.value = tagRes.data
    form.category_id = categories.value[0]?.id || 0
  } catch (e) {
    showToast('加载基础数据失败')
  }
  await loadDishes()
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
  overflow-y: auto;
  height: 100%;
}
.edit-popup h3 {
  text-align: center;
  margin: 8px 0 16px;
}
.section-title {
  padding: 12px 16px 8px;
  color: #646566;
  font-size: 14px;
}
.image-section,
.link-section {
  margin: 8px 0;
}
.upload-hint {
  padding: 0 16px 8px;
  color: #969799;
  font-size: 12px;
}
.image-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 16px;
}
.image-item {
  position: relative;
  width: 72px;
  height: 72px;
}
.image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
}
.del-icon {
  position: absolute;
  top: -6px;
  right: -6px;
  background: #ee0a24;
  color: #fff;
  border-radius: 50%;
  padding: 2px;
}
.link-row {
  padding: 0 16px;
  margin-bottom: 8px;
}
.md-preview-toggle {
  padding: 2px 16px 6px;
  color: #1989fa;
  font-size: 13px;
}
.md-preview {
  margin: 0 16px 8px;
  padding: 10px 12px;
  background: #f7f8fa;
  border-radius: 8px;
  min-height: 40px;
}
.tag-editor {
  width: 100%;
}
.tag-selected {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.tag-input-row {
  margin: 0 -16px;
}
.tag-quick-pick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
</style>
