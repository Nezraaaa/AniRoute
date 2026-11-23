// Captures the real AniRoute UI (2x resolution) and the real route geometry used by the 3D film.
//   Needs the backend (:8000) and frontend (:5173) running.
//   node presentation/video/capture-assets.mjs
import { createRequire } from 'node:module'
import { existsSync } from 'node:fs'
import { mkdir, writeFile, copyFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../..')
const require = createRequire(path.join(root, 'frontend/package.json'))
const { chromium } = require('playwright-core')

const appUrl = process.env.ANIROUTE_APP_URL || 'http://127.0.0.1:5173'
const out = process.env.ANIROUTE_ASSET_DIR ? path.resolve(process.env.ANIROUTE_ASSET_DIR) : path.join(here, 'assets')
await mkdir(out, { recursive: true })
const exe = [process.env.CHROME_PATH, 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].filter(Boolean).find(p => existsSync(p))

const browser = await chromium.launch({ headless: true, executablePath: exe, args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
// A GPS fix on the route (Calamba, Laguna) so the hazard dialog can pin the finding like on a real phone.
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  geolocation: { latitude: 14.2117, longitude: 121.1653, accuracy: 8 },
  permissions: ['geolocation', 'microphone', 'camera'],
})
const page = await context.newPage()
let routesJson = null
page.on('response', async res => {
  if (res.request().method() === 'POST' && /\/routes\/calculate$/.test(new URL(res.url()).pathname)) {
    try { routesJson = await res.json() } catch { /* ignore */ }
  }
})

const shot = (name, target = page) => target.screenshot({ path: path.join(out, `${name}.png`) })

async function pick(id, q) {
  await page.fill(`#${id}`, q)
  const opt = page.locator('.location-suggestion').first()
  await opt.waitFor({ timeout: 20000 }).catch(() => undefined)
  if (await opt.isVisible().catch(() => false)) await opt.click()
}

await page.goto(appUrl, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
await shot('plan-empty')
await shot('form-empty', page.locator('.trip-form-column'))
await page.fill('#crop-0', 'Tomatoes')
await page.fill('#crop-quantity-0', '250')
await page.selectOption('#vehicle', { index: 1 })
await pick('origin', 'Baguio City')
await pick('destination-0', 'Calamba, Laguna')
await page.waitForTimeout(400)
await shot('form-filled', page.locator('.trip-form-column'))
await page.getByRole('button', { name: /find routes/i }).click()
await page.waitForSelector('.route-select-button', { timeout: 90000 })
await page.waitForTimeout(3000)
await shot('plan-routes')
const cards = page.locator('.route-option')
for (let i = 0; i < await cards.count(); i++) await shot(`route-card-${i}`, cards.nth(i))
await shot('route-panel', page.locator('.route-choice-panel'))
await writeFile(path.join(out, 'routes.json'), JSON.stringify(routesJson, null, 1))

// Active trip with the recorded drive, then the hazard confirmation dialog.
let use = page.getByRole('button', { name: /use this route/i }).first()
if (!(await use.isVisible().catch(() => false))) {
  await page.locator('.route-select-button').first().click()
  await page.waitForTimeout(500)
  use = page.getByRole('button', { name: /use this route/i }).first()
}
await use.click()
await page.waitForURL(/trip\/active/, { timeout: 15000 }).catch(() => undefined)
const rec = page.getByRole('button', { name: /analyse recorded drive/i })
await rec.waitFor({ timeout: 8000 }).catch(() => undefined)
if (await rec.isVisible().catch(() => false)) await rec.click()
await page.waitForTimeout(7000)
await shot('trip')
await shot('camera-card', page.locator('.camera-status-card')).catch(() => undefined)
const alertBtn = page.locator('.cv-detection-alert')
await alertBtn.waitFor({ timeout: 30000 }).catch(() => undefined)
if (await alertBtn.count()) {
  await alertBtn.click()
  await page.waitForTimeout(900)
  await shot('hazard-dialog-full')
  await shot('hazard-dialog', page.locator('.dialog-content')).catch(() => undefined)
}
// Phone-sized trip screen (390 x 844 at 3x) with the road camera card in view, for the dashboard phone.
const phone = await browser.newContext({
  viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
  geolocation: { latitude: 14.2117, longitude: 121.1653, accuracy: 8 },
  permissions: ['geolocation', 'microphone', 'camera'],
})
const mp = await phone.newPage()
await mp.goto(appUrl, { waitUntil: 'networkidle' })
await mp.fill('#crop-0', 'Tomatoes')
await mp.fill('#crop-quantity-0', '250')
await mp.selectOption('#vehicle', { index: 1 })
for (const [id, q] of [['origin', 'Baguio City'], ['destination-0', 'Calamba, Laguna']]) {
  await mp.fill(`#${id}`, q)
  const opt = mp.locator('.location-suggestion').first()
  await opt.waitFor({ timeout: 20000 }).catch(() => undefined)
  if (await opt.isVisible().catch(() => false)) await opt.click()
}
await mp.getByRole('button', { name: /find routes/i }).click()
await mp.waitForSelector('.route-select-button', { timeout: 90000 })
await mp.waitForTimeout(1500)
let mUse = mp.getByRole('button', { name: /use this route/i }).first()
if (!(await mUse.isVisible().catch(() => false))) {
  await mp.locator('.route-select-button').first().click()
  await mp.waitForTimeout(500)
  mUse = mp.getByRole('button', { name: /use this route/i }).first()
}
await mUse.click()
await mp.waitForURL(/trip\/active/, { timeout: 15000 }).catch(() => undefined)
const mRec = mp.getByRole('button', { name: /analyse recorded drive/i })
await mRec.waitFor({ timeout: 8000 }).catch(() => undefined)
if (await mRec.isVisible().catch(() => false)) await mRec.click()
await mp.waitForTimeout(6000)
const card = mp.locator('.camera-status-card')
// Bring the whole road-camera card (header, video, alert) into view, just below the top edge.
await card.evaluate(el => { el.style.scrollMarginTop = '48px'; el.scrollIntoView({ block: 'start' }) })
await mp.waitForTimeout(600)
const video = await mp.locator('.camera-status-card video').first().boundingBox().catch(() => null)
const alertRect = await mp.locator('.cv-detection-alert').first().boundingBox().catch(() => null)
await mp.screenshot({ path: path.join(out, 'phone-trip.png') })
await writeFile(path.join(out, 'phone-video-rect.json'), JSON.stringify({ viewport: { width: 390, height: 844 }, scale: 3, video, alert: alertRect }))
await phone.close()
await browser.close()

await copyFile(path.join(root, 'frontend/src/assets/aniroute-logo.png'), path.join(out, 'logo.png'))
await copyFile(path.join(root, 'frontend/public/aniroute-icon.png'), path.join(out, 'icon.png'))
for (const f of ['test_pothole_02.jpg', 'test_severe_road_damage_01.jpg']) {
  await copyFile(path.join(root, 'ml/reports/sample_detections', f), path.join(out, f))
}
console.log('routes captured:', routesJson ? (routesJson.routes ?? routesJson).length ?? 'yes' : 'NO')
