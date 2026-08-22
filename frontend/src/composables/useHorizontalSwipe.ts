import { onBeforeUnmount } from 'vue'

export interface HorizontalSwipeOptions {
  onNext: () => void
  onPrevious: () => void
  canNext?: () => boolean
  canPrevious?: () => boolean
  threshold?: number
  directionRatio?: number
}

export interface HorizontalSwipeHandlers {
  onTouchStart: (event: TouchEvent) => void
  onTouchMove: (event: TouchEvent) => void
  onTouchEnd: (event: TouchEvent) => void
  onTouchCancel: () => void
  onClickCapture: (event: MouseEvent) => void
}

const CLICK_SUPPRESSION_MS = 400

export function useHorizontalSwipe({
  onNext,
  onPrevious,
  canNext = () => true,
  canPrevious = () => true,
  threshold = 36,
  directionRatio = 1.25,
}: HorizontalSwipeOptions): HorizontalSwipeHandlers {
  let startX = 0
  let startY = 0
  let tracking = false
  let activeTouchId: number | null = null
  let gestureCancelled = false
  let swipeDirection: 'next' | 'previous' | null = null
  let horizontalMoveCount = 0
  let suppressClickUntil = 0
  let suppressClickTimer: number | undefined

  const resetGesture = () => {
    tracking = false
    activeTouchId = null
    gestureCancelled = false
    swipeDirection = null
    horizontalMoveCount = 0
  }

  const cancelGesture = () => {
    gestureCancelled = true
    swipeDirection = null
    horizontalMoveCount = 0
  }

  const findTouch = (touches: TouchList, identifier: number) => {
    for (let index = 0; index < touches.length; index += 1) {
      const touch = touches.item(index)
      if (touch?.identifier === identifier) return touch
    }
    return undefined
  }

  const scheduleClickSuppressionReset = () => {
    if (typeof window === 'undefined') return
    if (suppressClickTimer !== undefined) {
      window.clearTimeout(suppressClickTimer)
    }
    suppressClickTimer = window.setTimeout(() => {
      suppressClickUntil = 0
      suppressClickTimer = undefined
    }, CLICK_SUPPRESSION_MS)
  }

  const isHorizontal = (deltaX: number, deltaY: number) => {
    const horizontalDistance = Math.abs(deltaX)
    const verticalDistance = Math.abs(deltaY)
    return (
      horizontalDistance >= threshold &&
      horizontalDistance > verticalDistance * directionRatio
    )
  }

  const onTouchStart = (event: TouchEvent) => {
    if (event.touches.length !== 1) {
      resetGesture()
      return
    }

    const touch = event.touches[0]
    startX = touch.clientX
    startY = touch.clientY
    tracking = true
    activeTouchId = touch.identifier
    gestureCancelled = false
    swipeDirection = null
    horizontalMoveCount = 0
  }

  const onTouchMove = (event: TouchEvent) => {
    if (!tracking || gestureCancelled) return
    if (event.touches.length !== 1) {
      cancelGesture()
      return
    }

    if (activeTouchId === null) {
      cancelGesture()
      return
    }

    const touch = findTouch(event.touches, activeTouchId)
    if (!touch) {
      cancelGesture()
      return
    }

    const deltaX = touch.clientX - startX
    const deltaY = touch.clientY - startY

    const verticalDistance = Math.abs(deltaY)
    const horizontalDistance = Math.abs(deltaX)
    const isClearlyVertical =
      verticalDistance >= threshold &&
      verticalDistance > horizontalDistance * directionRatio

    if (isClearlyVertical) {
      cancelGesture()
      return
    }

    if (isHorizontal(deltaX, deltaY)) {
      if (swipeDirection === null) {
        swipeDirection = deltaX < 0 ? 'next' : 'previous'
        horizontalMoveCount = 1
      } else if (
        (deltaX < 0 && swipeDirection === 'next') ||
        (deltaX >= 0 && swipeDirection === 'previous')
      ) {
        horizontalMoveCount += 1
      }
      // Wait for a second horizontal sample before cancelling browser defaults.
      // If the gesture turns vertical immediately, scrolling remains available.
      if (horizontalMoveCount >= 2 && event.cancelable) {
        event.preventDefault()
      }
    }
  }

  const onTouchEnd = (event: TouchEvent) => {
    if (!tracking) return

    // A touchend with another finger still active is a multi-touch gesture;
    // do not turn it into a page switch when the tracked finger lifts first.
    if (event.touches.length !== 0) {
      resetGesture()
      return
    }

    if (activeTouchId === null) {
      resetGesture()
      return
    }

    const touch = findTouch(event.changedTouches, activeTouchId)
    if (!touch) {
      resetGesture()
      return
    }

    const deltaX = touch.clientX - startX
    const deltaY = touch.clientY - startY
    const endIsClearlyVertical =
      Math.abs(deltaY) >= threshold &&
      Math.abs(deltaY) > Math.abs(deltaX) * directionRatio
    const direction = swipeDirection ?? (isHorizontal(deltaX, deltaY)
      ? deltaX < 0
        ? 'next'
        : 'previous'
      : null)
    const wasCancelled = gestureCancelled || endIsClearlyVertical
    resetGesture()

    if (wasCancelled || !direction) return

    if (event.cancelable) {
      event.preventDefault()
    }
    suppressClickUntil = Date.now() + CLICK_SUPPRESSION_MS
    scheduleClickSuppressionReset()

    if (direction === 'next') {
      if (canNext()) onNext()
    } else if (canPrevious()) {
      onPrevious()
    }
  }

  const onTouchCancel = () => {
    resetGesture()
  }

  const onClickCapture = (event: MouseEvent) => {
    if (suppressClickUntil === 0 || Date.now() > suppressClickUntil) return
    suppressClickUntil = 0
    if (suppressClickTimer !== undefined && typeof window !== 'undefined') {
      window.clearTimeout(suppressClickTimer)
      suppressClickTimer = undefined
    }
    event.preventDefault()
    event.stopPropagation()
  }

  onBeforeUnmount(() => {
    resetGesture()
    suppressClickUntil = 0
    if (suppressClickTimer !== undefined && typeof window !== 'undefined') {
      window.clearTimeout(suppressClickTimer)
      suppressClickTimer = undefined
    }
  })

  return {
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    onTouchCancel,
    onClickCapture,
  }
}
