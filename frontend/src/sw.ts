/// <reference lib="webworker" />
import { precacheAndRoute } from 'workbox-precaching'
import { registerRoute } from 'workbox-routing'
import { NetworkFirst, CacheFirst } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'

declare let self: ServiceWorkerGlobalScope

// 新版本安装完成后立即激活；由前端提示用户确认刷新当前页面。
self.skipWaiting()
self.addEventListener('message', (event: ExtendableMessageEvent) => {
  if (event.data?.type === 'SKIP_WAITING') {
    event.waitUntil(self.skipWaiting())
  }
})

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
