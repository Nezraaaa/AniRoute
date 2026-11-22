/** Capture the current frame of a playing <video> as a JPEG data URL. */
export function captureVideoFrame(video: HTMLVideoElement | null, maxWidth = 640, quality = 0.7): string | undefined {
  if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return undefined
  // Some browsers briefly (or, headless, permanently) report a 2x2 placeholder; never send it.
  if (video.videoWidth < 32 || video.videoHeight < 32) return undefined
  const scale = Math.min(1, maxWidth / video.videoWidth)
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(video.videoWidth * scale)
  canvas.height = Math.round(video.videoHeight * scale)
  const context = canvas.getContext('2d')
  if (!context) return undefined
  context.drawImage(video, 0, 0, canvas.width, canvas.height)
  try {
    return canvas.toDataURL('image/jpeg', quality)
  } catch {
    // A cross-origin video without CORS headers taints the canvas.
    return undefined
  }
}

export type MediaFit = 'contain' | 'cover'

export interface Rect {
  left: number
  top: number
  width: number
  height: number
}

/**
 * Where a normalised box (0-1, relative to the media's intrinsic size) lands inside a
 * container that shows the media with CSS object-fit `contain` or `cover`.
 */
export function projectBox(
  boxNorm: [number, number, number, number],
  container: { width: number; height: number },
  media: { width: number; height: number },
  fit: MediaFit,
): Rect {
  if (!media.width || !media.height || !container.width || !container.height) return { left: 0, top: 0, width: 0, height: 0 }
  const scale = fit === 'contain'
    ? Math.min(container.width / media.width, container.height / media.height)
    : Math.max(container.width / media.width, container.height / media.height)
  const shownWidth = media.width * scale
  const shownHeight = media.height * scale
  const offsetX = (container.width - shownWidth) / 2
  const offsetY = (container.height - shownHeight) / 2
  const [x1, y1, x2, y2] = boxNorm
  return {
    left: offsetX + x1 * shownWidth,
    top: offsetY + y1 * shownHeight,
    width: (x2 - x1) * shownWidth,
    height: (y2 - y1) * shownHeight,
  }
}
