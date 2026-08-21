/// <reference lib="webworker" />
import { precacheAndRoute } from 'workbox-precaching'
import { registerRoute } from 'workbox-routing'
import { NetworkFirst, CacheFirst } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'

declare let self: ServiceWorkerGlobalScope

// 预缓存（vite-plugin-pwa 注入清单）
precacheAndRoute(self.__WB_MANIFEST)

// 菜单 API：NetworkFirst（5 分钟）
registerRoute(
  /\/api\/(dishes|categories|tags)/,
  new NetworkFirst({
    cacheName: 'api-menu-cache',
    plugins: [
      new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 300 }),
    ],
  })
)

// 图片：CacheFirst（1 天）
registerRoute(
  /\/uploads\/.*/,
  new CacheFirst({
    cacheName: 'image-cache',
    plugins: [
      new ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 86400 }),
    ],
  })
)

// ===== Web Push 通知 =====
// 后端推送 payload：{"title": "饭饭之交", "body": "..."}
self.addEventListener('push', (event) => {
  let title = '饭饭之交'
  let body = ''
  try {
    const data = event.data?.json()
    if (data) {
      title = data.title || title
      body = data.body || ''
    }
  } catch {
    // 非 JSON payload，直接显示原文
    body = event.data?.text() || ''
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
    })
  )
})

// 点击通知：关闭并回到首页
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.focus()
          return
        }
      }
      return self.clients.openWindow('/')
    })
  )
})
