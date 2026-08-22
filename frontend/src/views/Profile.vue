<template>
  <div class="profile">
    <van-nav-bar title="个人中心" fixed>
      <template #right>
        <van-icon
          v-if="!forcedChange"
          name="edit"
          size="20"
          @click="openEdit"
        />
      </template>
    </van-nav-bar>
    <div class="content" style="padding-top: 46px">
      <!-- 用户信息卡片 -->
      <div class="user-card">
        <van-image
          round
          width="64"
          height="64"
          :src="userStore.user?.avatar_url ? imageUrl(userStore.user.avatar_url) : defaultAvatar"
          @click="openEdit"
        />
        <div class="user-info">
          <div class="nickname">{{ userStore.user?.nickname || userStore.user?.username }}</div>
          <van-tag
            :type="userStore.isAdmin ? 'danger' : userStore.isFeeder ? 'primary' : 'success'"
            round
          >
            {{ userStore.roleName }}
          </van-tag>
        </div>
        <div class="card-spacer"></div>
        <van-button size="small" plain type="primary" @click="openPassword">改密</van-button>
      </div>

      <!-- 账号信息 -->
      <van-cell-group inset style="margin-top: 16px">
        <van-cell title="账号" :value="userStore.user?.username" />
        <van-cell title="角色" :value="userStore.roleName" />
        <van-cell title="饲养员权限" :value="userStore.isFeeder ? '是' : '否'" />
      </van-cell-group>

      <!-- 管理端入口（仅管理员可见） -->
      <van-cell-group v-if="userStore.isAdmin" inset style="margin-top: 16px">
        <van-cell title="用户管理" is-link to="/admin/users" />
      </van-cell-group>

      <!-- 模式切换 -->
      <van-cell-group
        v-if="userStore.isFeeder"
        inset
        title="身份切换"
        style="margin-top: 16px"
      >
        <van-cell
          title="当前模式"
          :value="userStore.currentMode === 'feeder' ? '饲养员模式' : '饭团模式'"
          is-link
          @click="onSwitchMode"
        />
      </van-cell-group>

      <!-- 推送通知 -->
      <van-cell-group inset title="推送通知" style="margin-top: 16px">
        <van-cell title="开启推送">
          <template #right-icon>
            <van-switch
              :model-value="subscribed"
              :disabled="!pushEnabled"
              @update:model-value="onTogglePush"
            />
          </template>
        </van-cell>
        <van-cell
          v-if="!pushEnabled"
          title="提示"
          label="服务端未配置 VAPID 密钥，推送不可用（可模拟测试）"
        />
        <van-cell title="发送测试推送" is-link @click="sendTestPush" />
      </van-cell-group>

      <van-cell-group inset title="应用更新" style="margin-top: 16px">
        <van-cell
          title="检查更新"
          :value="checking ? '检查中…' : '手动检查'"
          :is-link="!checking"
          @click="onCheckUpdate"
        />
      </van-cell-group>

      <div style="margin: 16px">
        <van-button round block type="danger" @click="onLogout">退出登录</van-button>
      </div>
    </div>

    <!-- 编辑资料弹层 -->
    <van-popup
      v-model:show="showEdit"
      position="bottom"
      round
      :style="{ height: '85%' }"
      closeable
    >
      <div class="edit-popup">
        <h3>编辑资料</h3>
        <div class="edit-current-avatar">
          <van-image
            round
            width="80"
            height="80"
            :src="editForm.avatar_url ? imageUrl(editForm.avatar_url) : defaultAvatar"
          />
        </div>

        <van-cell-group inset>
          <van-field
            v-model="editForm.nickname"
            label="昵称"
            placeholder="给自己起个昵称吧"
            maxlength="50"
          />
        </van-cell-group>

        <div class="section-title">选择预设头像</div>
        <van-grid :column-num="4" :gutter="8" class="avatar-grid">
          <van-grid-item
            v-for="a in PRESET_AVATARS"
            :key="a.key"
            @click="editForm.avatar_url = a.key"
          >
            <van-image
              round
              width="56"
              height="56"
              :src="imageUrl(a.key)"
              :class="['avatar-pick', editForm.avatar_url === a.key ? 'avatar-pick-active' : '']"
            />
            <span class="avatar-label">{{ a.label }}</span>
          </van-grid-item>
        </van-grid>

        <div class="upload-row">
          <span class="upload-tip">或上传自定义头像：</span>
          <van-uploader
            :after-read="onAfterRead"
            :max-size="5 * 1024 * 1024"
            :max-count="1"
            :preview-image="false"
            @oversize="showToast('图片不能超过 5MB')"
          />
        </div>

        <div style="margin: 16px">
          <van-button round block type="primary" :loading="saving" @click="onSaveProfile">
            保存
          </van-button>
        </div>
      </div>
    </van-popup>

    <!-- 修改密码弹层（普通入口 / 强制改密时复用，强制时 closeable=false） -->
    <van-popup
      v-model:show="showPassword"
      position="bottom"
      round
      :style="{ height: '60%' }"
      :closeable="!forcedChange"
      :close-on-click-overlay="!forcedChange"
    >
      <div class="edit-popup">
        <h3>{{ forcedChange ? '请修改你的初始密码' : '修改密码' }}</h3>
        <p v-if="forcedChange" class="forced-hint">
          首次登录必须修改密码后才能继续使用
        </p>
        <van-cell-group inset>
          <van-field
            v-model="pwForm.old_password"
            type="password"
            label="旧密码"
            placeholder="当前密码"
          />
          <van-field
            v-model="pwForm.new_password"
            type="password"
            label="新密码"
            placeholder="至少 6 位"
            maxlength="50"
          />
          <van-field
            v-model="pwForm.confirm"
            type="password"
            label="确认"
            placeholder="再输入一次新密码"
            maxlength="50"
          />
        </van-cell-group>
        <div style="margin: 16px">
          <van-button
            round
            block
            type="primary"
            :loading="savingPw"
            @click="onChangePassword"
          >
            确定
          </van-button>
        </div>
      </div>
    </van-popup>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { showConfirmDialog, showSuccessToast, showToast } from 'vant'
import type { UploaderFileListItem } from 'vant'
import { useUserStore } from '@/stores/user'
import { usePush } from '@/composables/usePush'
import { useAppUpdate } from '@/composables/useAppUpdate'
import { imageUrl } from '@/api/dish'
import { updateProfile, uploadAvatar } from '@/api/auth'
import { changePassword as changePasswordApi } from '@/api/auth'
import { PRESET_AVATARS } from '@/utils/avatars'

const userStore = useUserStore()
const defaultAvatar = 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'
const { subscribed, pushEnabled, initPush, enablePush, disablePush, sendTestPush } = usePush()
const { checking, checkForUpdate } = useAppUpdate()

// 编辑资料
const showEdit = ref(false)
const saving = ref(false)
const editForm = ref<{ nickname: string; avatar_url: string }>({
  nickname: '',
  avatar_url: '',
})
const openEdit = () => {
  editForm.value = {
    nickname: userStore.user?.nickname || '',
    avatar_url: userStore.user?.avatar_url || '',
  }
  showEdit.value = true
}
const onSaveProfile = async () => {
  saving.value = true
  try {
    const { data } = await updateProfile({
      nickname: editForm.value.nickname.trim() || null,
      avatar_url: editForm.value.avatar_url || null,
    })
    userStore.setUser(data)
    showSuccessToast('保存成功')
    showEdit.value = false
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
const onAfterRead = async (item: UploaderFileListItem | UploaderFileListItem[]) => {
  const arr = Array.isArray(item) ? item : [item]
  const file = arr[0]?.file
  if (!file) return
  try {
    const { data } = await uploadAvatar(file)
    userStore.setUser(data)
    editForm.value.avatar_url = data.avatar_url || ''
    showSuccessToast('头像已上传')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '上传失败')
  }
}

// 修改密码
const showPassword = ref(false)
const savingPw = ref(false)
const pwForm = ref({ old_password: '', new_password: '', confirm: '' })
const openPassword = () => {
  pwForm.value = { old_password: '', new_password: '', confirm: '' }
  showPassword.value = true
}
const onChangePassword = async () => {
  if (!pwForm.value.old_password || !pwForm.value.new_password) {
    showToast('请填写完整')
    return
  }
  if (pwForm.value.new_password !== pwForm.value.confirm) {
    showToast('两次新密码输入不一致')
    return
  }
  savingPw.value = true
  try {
    const { data } = await changePasswordApi({
      old_password: pwForm.value.old_password,
      new_password: pwForm.value.new_password,
    })
    userStore.setToken(
      data.access_token,
      data.refresh_token,
      data.must_change_password ?? false,
    )
    await userStore.fetchUser()
    showSuccessToast('密码已修改')
    showPassword.value = false
  } catch (e: any) {
    showToast(e.response?.data?.detail || '改密失败')
  } finally {
    savingPw.value = false
  }
}

// 强制改密
const forcedChange = computed(() => userStore.mustChangePassword)
watch(forcedChange, (v) => {
  if (v) openPassword()
}, { immediate: true })

// 模式切换 / 推送
const onSwitchMode = () => {
  userStore.switchMode()
  showToast(
    userStore.currentMode === 'feeder' ? '已切换到饲养员模式' : '已切换到饭团模式'
  )
}
const onTogglePush = async (val: boolean) => {
  if (val) await enablePush()
  else await disablePush()
}

const onCheckUpdate = async () => {
  if (checking.value) return
  const result = await checkForUpdate()
  if (result === 'current') {
    showSuccessToast('当前已是最新版本')
  } else if (result === 'available') {
    showSuccessToast('发现新版本，请在页面提示中更新')
  } else if (result === 'pending') {
    showToast('新版本正在准备，请稍后查看页面提示')
  } else if (result === 'unsupported') {
    showToast('当前浏览器不支持自动更新')
  } else {
    showToast('检查更新失败，请稍后重试')
  }
}

// 退出登录
const onLogout = () => {
  showConfirmDialog({ title: '提示', message: '确定要退出登录吗？' })
    .then(() => {
      userStore.logout()
      // 退出后跳首页（游客可浏览）
      location.href = '/'
    })
    .catch(() => {})
}

onMounted(() => {
  initPush()
})
</script>

<style scoped>
.user-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px 16px;
  background: #fff;
  margin: 16px;
  border-radius: 12px;
}
.card-spacer {
  flex: 1;
}
.user-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.nickname {
  font-size: 18px;
  font-weight: bold;
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
.edit-current-avatar {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}
.section-title {
  padding: 12px 16px 4px;
  color: #646566;
  font-size: 14px;
}
.avatar-grid {
  padding: 8px 16px;
}
.avatar-pick {
  border: 2px solid transparent;
  transition: border-color 0.2s;
}
.avatar-pick-active {
  border-color: #ee0a24;
}
.avatar-label {
  font-size: 12px;
  color: #646566;
  margin-top: 4px;
  display: block;
  text-align: center;
}
.upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
}
.upload-tip {
  font-size: 13px;
  color: #646566;
}
.forced-hint {
  margin: 0 16px 12px;
  padding: 8px 12px;
  background: #fff7e6;
  border-left: 3px solid #ff8917;
  color: #ff8917;
  font-size: 13px;
  border-radius: 4px;
}
</style>
