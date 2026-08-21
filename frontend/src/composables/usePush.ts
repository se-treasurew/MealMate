import { ref } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import {
  getVapidPublicKey,
  subscribePush,
  unsubscribePush,
  testPush,
  urlBase64ToUint8Array,
} from '@/api/push'

const subscribed = ref(false)
const pushEnabled = ref(false) // 后端是否配置了 VAPID

// 初始化推送状态
async function initPush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    pushEnabled.value = false
    return
  }
  try {
    const { data } = await getVapidPublicKey()
    pushEnabled.value = data.enabled
    if (!data.enabled) {
      subscribed.value = false
      return
    }
    const reg = await navigator.serviceWorker.ready
    const existing = await reg.pushManager.getSubscription()
    subscribed.value = !!existing
  } catch {
    pushEnabled.value = false
  }
}

// 订阅推送
async function enablePush() {
  if (!pushEnabled.value) {
    showToast('服务端未配置 VAPID，推送功能不可用')
    return false
  }
  try {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') {
      showToast('未获得通知权限')
      return false
    }
    const { data } = await getVapidPublicKey()
    const reg = await navigator.serviceWorker.ready
    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(data.public_key!),
    })
    await subscribePush(subscription)
    subscribed.value = true
    showSuccessToast('已开启推送')
    return true
  } catch (e) {
    showToast('开启推送失败')
    return false
  }
}

// 取消订阅
async function disablePush() {
  try {
    const reg = await navigator.serviceWorker.ready
    const existing = await reg.pushManager.getSubscription()
    if (existing) {
      await unsubscribePush(existing.endpoint)
      await existing.unsubscribe()
    }
    subscribed.value = false
    showSuccessToast('已关闭推送')
  } catch {
    showToast('关闭推送失败')
  }
}

// 发送测试推送
async function sendTestPush() {
  try {
    const { data } = await testPush('这是一条测试推送 🍚')
    if (data.simulated) {
      showSuccessToast('已模拟推送（未配置 VAPID）')
    } else if (data.success) {
      showSuccessToast('测试推送已发送')
    } else {
      showToast('推送发送失败，请查看后端日志')
    }
  } catch (e: any) {
    showToast(e.response?.data?.detail || '测试失败')
  }
}

export function usePush() {
  return {
    subscribed,
    pushEnabled,
    initPush,
    enablePush,
    disablePush,
    sendTestPush,
  }
}
