import apiClient from '@/utils/axios'

export interface VapidInfo {
  enabled: boolean
  public_key: string | null
}

export const getVapidPublicKey = () =>
  apiClient.get<VapidInfo>('/api/push/vapid-public-key')

export const subscribePush = (subscription: PushSubscription) => {
  const sub = subscription.toJSON()
  return apiClient.post('/api/push/subscribe', {
    endpoint: sub.endpoint,
    keys: sub.keys,
  })
}

export const unsubscribePush = (endpoint: string) =>
  apiClient.delete('/api/push/subscribe', { params: { endpoint } })

export const testPush = (message = '这是一条测试推送') =>
  apiClient.post('/api/push/test', { message })

// 将 base64url 公钥转为 Uint8Array（订阅推送需要）
export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  const outputArray = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}
