<template>
  <div class="user-manage">
    <van-nav-bar title="用户管理" fixed left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="plus" size="20" @click="openCreate" />
      </template>
    </van-nav-bar>

    <div class="content" style="padding-top: 46px; padding-bottom: 50px">
      <van-loading v-if="loading" type="spinner" class="loading" />
      <template v-else>
        <p class="hint">共 {{ users.length }} 个账号，店长账号无法在此修改</p>
        <van-cell-group inset v-for="u in users" :key="u.id" class="user-cell-group">
          <van-cell @click="openAction(u)">
            <template #icon>
              <van-image
                round
                width="44"
                height="44"
                :src="u.avatar_url ? imageUrl(u.avatar_url) : defaultAvatar"
                style="margin-right: 12px; flex-shrink: 0"
              />
            </template>
            <template #title>
              <div class="cell-title">
                <span class="nick">{{ u.nickname || u.username }}</span>
                <van-tag v-if="u.is_admin" type="danger" plain>店长</van-tag>
                <van-tag v-else-if="u.is_feeder" type="primary" plain>饲养员</van-tag>
                <van-tag v-else type="success" plain>饭团</van-tag>
                <van-tag v-if="!u.is_active" type="warning">已禁用</van-tag>
              </div>
            </template>
            <template #label>@{{ u.username }}</template>
            <template #value>
              <van-icon name="ellipsis" size="20" />
            </template>
          </van-cell>
        </van-cell-group>
        <van-empty v-if="users.length === 0" description="暂无用户" />
      </template>
    </div>

    <!-- 操作菜单（点击用户行） -->
    <van-action-sheet
      v-model:show="showAction"
      :actions="actionList"
      cancel-text="取消"
      close-on-click-action
      @select="onActionSelect"
    />

    <!-- 新建账号弹层 -->
    <van-popup v-model:show="showCreate" position="bottom" round :style="{ height: '75%' }" closeable>
      <div class="form-popup">
        <h3>新建账号</h3>
        <p class="hint-inline">用户首次登录必须修改初始密码</p>
        <van-cell-group inset>
          <van-field
            v-model="createForm.username"
            label="账号"
            placeholder="4-50 字符"
            maxlength="50"
          />
          <van-field
            v-model="createForm.password"
            type="password"
            label="初始密码"
            placeholder="至少 6 位"
            maxlength="50"
          />
          <van-field
            v-model="createForm.nickname"
            label="昵称"
            placeholder="可选"
            maxlength="50"
          />
          <van-cell title="授予饲养员权限">
            <template #right-icon>
              <van-switch v-model="createForm.is_feeder" />
            </template>
          </van-cell>
        </van-cell-group>
        <div style="margin: 16px">
          <van-button round block type="primary" :loading="creating" @click="onCreate">
            创建
          </van-button>
        </div>
      </div>
    </van-popup>

    <!-- 重置密码弹层 -->
    <van-popup v-model:show="showResetPw" position="bottom" round :style="{ height: '55%' }" closeable>
      <div class="form-popup">
        <h3>重置密码</h3>
        <p class="hint-inline">将为「{{ activeUser?.nickname || activeUser?.username }}」设置新密码，重置后用户需重新登录并修改密码</p>
        <van-cell-group inset>
          <van-field
            v-model="newPassword"
            type="password"
            label="新密码"
            placeholder="至少 6 位"
            maxlength="50"
          />
        </van-cell-group>
        <div style="margin: 16px">
          <van-button round block type="primary" :loading="resetting" @click="onResetPassword">
            确定重置
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import { useUserStore } from '@/stores/user'
import { imageUrl } from '@/api/dish'
import {
  getUsers,
  createUser,
  updateUserFeeder,
  updateUserStatus,
  resetUserPassword,
  type UserListItem,
  type UserFeederPayload,
  type UserStatusPayload,
  type PasswordResetPayload,
} from '@/api/user'

const userStore = useUserStore()
const defaultAvatar = 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'

const loading = ref(false)
const users = ref<UserListItem[]>([])
const activeUser = ref<UserListItem | null>(null)

const loadUsers = async () => {
  loading.value = true
  try {
    const { data } = await getUsers()
    users.value = data
  } catch (e: any) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

// 操作菜单
const showAction = ref(false)
const actionList = computed(() => {
  if (!activeUser.value) return []
  const u = activeUser.value
  const list: { name: string; subname?: string; color?: string; disabled?: boolean; key: string }[] = []
  if (u.is_admin) {
    list.push({ name: '管理员账号', subname: '不可操作', disabled: true, key: 'noop' })
  } else {
    list.push({
      name: u.is_feeder ? '收回饲养员权限' : '授予饲养员权限',
      key: 'feeder',
    })
    list.push({
      name: u.is_active ? '禁用账号' : '启用账号',
      color: u.is_active ? '#ee0a24' : '#07c160',
      key: 'status',
    })
    list.push({ name: '重置密码', key: 'reset' })
  }
  return list
})
const openAction = (u: UserListItem) => {
  activeUser.value = u
  showAction.value = true
}
const onActionSelect = async (action: { key: string }) => {
  if (action.key === 'noop' || !activeUser.value) return
  const u = activeUser.value
  if (action.key === 'feeder') {
    await toggleFeeder(u)
  } else if (action.key === 'status') {
    await toggleStatus(u)
  } else if (action.key === 'reset') {
    showResetPw.value = true
  }
}

const toggleFeeder = async (u: UserListItem) => {
  const payload: UserFeederPayload = { is_feeder: !u.is_feeder }
  try {
    const { data } = await updateUserFeeder(u.id, payload)
    Object.assign(u, data)
    showSuccessToast(data.is_feeder ? '已授予饲养员权限' : '已收回饲养员权限')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '操作失败')
  }
}

const toggleStatus = async (u: UserListItem) => {
  if (u.id === userStore.user?.id) {
    showToast('不能操作自己')
    return
  }
  showConfirmDialog({
    title: u.is_active ? '禁用账号' : '启用账号',
    message: u.is_active
      ? `禁用后「${u.nickname || u.username}」将无法登录`
      : `重新启用「${u.nickname || u.username}」`,
  })
    .then(async () => {
      const payload: UserStatusPayload = { is_active: !u.is_active }
      try {
        const { data } = await updateUserStatus(u.id, payload)
        Object.assign(u, data)
        showSuccessToast(data.is_active ? '已启用' : '已禁用')
      } catch (e: any) {
        showToast(e.response?.data?.detail || '操作失败')
      }
    })
    .catch(() => {})
}

// 新建账号
const showCreate = ref(false)
const creating = ref(false)
const createForm = ref({ username: '', password: '', nickname: '', is_feeder: false })
const openCreate = () => {
  createForm.value = { username: '', password: '', nickname: '', is_feeder: false }
  showCreate.value = true
}
const onCreate = async () => {
  if (createForm.value.username.length < 4) {
    showToast('账号至少 4 字符')
    return
  }
  if (createForm.value.password.length < 6) {
    showToast('初始密码至少 6 位')
    return
  }
  creating.value = true
  try {
    await createUser({
      username: createForm.value.username,
      password: createForm.value.password,
      nickname: createForm.value.nickname.trim() || null,
      is_feeder: createForm.value.is_feeder,
    })
    showSuccessToast('已创建')
    showCreate.value = false
    await loadUsers()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

// 重置密码
const showResetPw = ref(false)
const resetting = ref(false)
const newPassword = ref('')
const onResetPassword = async () => {
  if (newPassword.value.length < 6) {
    showToast('新密码至少 6 位')
    return
  }
  if (!activeUser.value) return
  resetting.value = true
  try {
    const payload: PasswordResetPayload = { password: newPassword.value }
    await resetUserPassword(activeUser.value.id, payload)
    showSuccessToast('密码已重置')
    showResetPw.value = false
    newPassword.value = ''
  } catch (e: any) {
    showToast(e.response?.data?.detail || '重置失败')
  } finally {
    resetting.value = false
  }
}

onMounted(() => {
  if (!userStore.isAdmin) {
    showToast('无权限')
    return
  }
  loadUsers()
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
.hint-inline {
  margin: 0 16px 12px;
  color: #ff8917;
  font-size: 12px;
}
.user-cell-group {
  margin-bottom: 8px;
}
.cell-title {
  display: flex;
  align-items: center;
  gap: 6px;
}
.nick {
  font-weight: 600;
}
.form-popup {
  padding: 16px;
  overflow-y: auto;
  height: 100%;
}
.form-popup h3 {
  text-align: center;
  margin: 8px 0 16px;
}
</style>
