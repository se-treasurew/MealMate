/// <reference types="vite-plugin-pwa/client" />

import { ref } from 'vue'
import { registerSW } from 'virtual:pwa-register'

export type UpdateCheckResult =
  | 'available'
  | 'current'
  | 'pending'
  | 'unsupported'
  | 'error'

const updateAvailable = ref(false)
const checking = ref(false)

let initialized = false
let updateDeferred = false
let registration: ServiceWorkerRegistration | null = null
let updateServiceWorker: ((reloadPage?: boolean) => Promise<void>) | null = null

const waitForUpdateSignal = async (timeoutMs = 10000) => {
  const startedAt = Date.now()
  while (!updateAvailable.value && Date.now() - startedAt < timeoutMs) {
    await new Promise((resolve) => window.setTimeout(resolve, 50))
  }
  return updateAvailable.value
}

const waitForWorkerActivation = (worker: ServiceWorker, timeoutMs = 5000) =>
  new Promise<void>((resolve) => {
    if (worker.state === 'activated') {
      resolve()
      return
    }

    const timer = window.setTimeout(() => {
      worker.removeEventListener('statechange', onStateChange)
      resolve()
    }, timeoutMs)
    const onStateChange = () => {
      if (worker.state === 'activated' || worker.state === 'redundant') {
        window.clearTimeout(timer)
        worker.removeEventListener('statechange', onStateChange)
        resolve()
      }
    }
    worker.addEventListener('statechange', onStateChange)
  })

const initAppUpdate = () => {
  if (initialized || typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return
  }

  initialized = true
  updateServiceWorker = registerSW({
    immediate: true,
    onNeedReload: () => {
      updateAvailable.value = true
      updateDeferred = false
    },
    onRegisteredSW: (_swUrl, currentRegistration) => {
      registration = currentRegistration ?? null
    },
    onRegisterError: (error) => {
      console.error('Service Worker 注册失败', error)
    },
  })
}

const checkForUpdate = async (): Promise<UpdateCheckResult> => {
  initAppUpdate()

  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) {
    return 'unsupported'
  }

  if (updateAvailable.value) {
    return 'available'
  }

  if (updateDeferred) {
    updateDeferred = false
    updateAvailable.value = true
    return 'available'
  }

  checking.value = true
  try {
    const currentRegistration =
      registration ?? (await navigator.serviceWorker.getRegistration('/'))
    if (!currentRegistration) {
      return 'unsupported'
    }

    registration = currentRegistration
    let updateFound = false
    const onUpdateFound = () => {
      updateFound = true
    }
    currentRegistration.addEventListener('updatefound', onUpdateFound, { once: true })
    try {
      await currentRegistration.update()
      const available = await waitForUpdateSignal()
      if (available) {
        return 'available'
      }
      return updateFound || Boolean(currentRegistration.installing) ? 'pending' : 'current'
    } finally {
      currentRegistration.removeEventListener('updatefound', onUpdateFound)
    }
  } catch (error) {
    console.error('Service Worker 更新检查失败', error)
    return 'error'
  } finally {
    checking.value = false
  }
}

const applyUpdate = async () => {
  if (typeof window === 'undefined') return

  try {
    if (updateServiceWorker) {
      await updateServiceWorker(false)
    }

    const waitingWorker = registration?.waiting
    if (waitingWorker) {
      waitingWorker.postMessage({ type: 'SKIP_WAITING' })
      await waitForWorkerActivation(waitingWorker)
    }
  } catch (error) {
    console.error('Service Worker 更新应用失败', error)
  } finally {
    window.location.reload()
  }
}

const dismissUpdate = () => {
  if (updateAvailable.value) {
    updateAvailable.value = false
    updateDeferred = true
  }
}

export function useAppUpdate() {
  initAppUpdate()

  return {
    updateAvailable,
    checking,
    checkForUpdate,
    applyUpdate,
    dismissUpdate,
  }
}
