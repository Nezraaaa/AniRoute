import { createRequire } from 'node:module'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require('/Users/zirch/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')

const appUrl = process.env.ANIROUTE_PREVIEW_URL || 'http://127.0.0.1:5173/'
const outputDirectory = path.resolve('artifacts')
const rawVideoPath = path.join(outputDirectory, 'aniroute-preview-10s.webm')

await mkdir(outputDirectory, { recursive: true })

const browser = await chromium.launch({
  headless: true,
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
})
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: outputDirectory, size: { width: 1440, height: 900 } },
  reducedMotion: 'reduce',
})
const page = await context.newPage()

async function moveCursorTo(locator) {
  const box = await locator.boundingBox()
  if (!box) return
  const position = { x: box.x + box.width / 2, y: box.y + box.height / 2 }
  await page.evaluate(({ x, y }) => {
    const cursor = document.querySelector('[data-video-cursor]')
    if (cursor instanceof HTMLElement) cursor.style.transform = `translate(${x}px, ${y}px)`
  }, position)
  await page.waitForTimeout(220)
}

async function clickForVideo(locator) {
  await locator.scrollIntoViewIfNeeded()
  await moveCursorTo(locator)
  await locator.click()
}

try {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' })
  await page.locator('.route-list').waitFor({ state: 'visible' })
  await page.evaluate(() => {
    const cursor = document.createElement('span')
    cursor.dataset.videoCursor = 'true'
    cursor.style.cssText = [
      'position:fixed', 'z-index:9999', 'top:-12px', 'left:-12px',
      'width:24px', 'height:24px', 'border-radius:50%',
      'background:rgba(31,111,78,.9)', 'border:3px solid white',
      'box-shadow:0 3px 14px rgba(10,35,20,.35)',
      'pointer-events:none', 'transition:transform .28s ease',
    ].join(';')
    document.body.append(cursor)
  })
  await page.waitForTimeout(900)

  const fastestRoute = page.locator('.route-select-button').nth(2)
  await clickForVideo(fastestRoute)
  await page.locator('#route-details-fastest').waitFor({ state: 'visible' })
  await page.waitForTimeout(1_650)

  await clickForVideo(page.getByRole('button', { name: 'Use this route' }))
  await page.locator('.active-layout').waitFor({ state: 'visible' })
  const cameraCard = page.locator('.camera-status-card')
  await cameraCard.scrollIntoViewIfNeeded()
  await page.locator('.cv-detection-alert').waitFor({ state: 'visible', timeout: 5_000 })
  await page.waitForTimeout(850)

  await clickForVideo(page.locator('.cv-detection-alert'))
  await page.getByRole('dialog').waitFor({ state: 'visible' })
  await page.waitForTimeout(1_250)

  await clickForVideo(page.getByTestId('hazard-confirm-button'))
  await page.waitForTimeout(1_500)
  const routeChange = page.locator('.route-change-banner')
  if (await routeChange.isVisible()) await routeChange.scrollIntoViewIfNeeded()
  await page.waitForTimeout(2_100)
} finally {
  const video = page.video()
  await context.close()
  if (video) await video.saveAs(rawVideoPath)
  await browser.close()
}

console.log(rawVideoPath)
