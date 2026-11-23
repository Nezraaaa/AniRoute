// Captures app screenshots for the slides and README.
//
//   1. start the backend (uvicorn backend.main:app) and the frontend (npm run dev)
//   2. node scripts/capture-screenshots.mjs
//
// Uses playwright-core with the locally installed Chrome or Edge (no browser download).
// Override with CHROME_PATH=... and ANIROUTE_APP_URL=http://127.0.0.1:5173
import { existsSync } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright-core'

const appUrl = (process.env.ANIROUTE_APP_URL || 'http://127.0.0.1:5173').replace(/\/$/, '')
const outDir = path.resolve(process.env.ANIROUTE_SCREENSHOT_DIR || '../presentation/screenshots')
const candidates = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
].filter(Boolean)
const executablePath = candidates.find(candidate => existsSync(candidate))
if (!executablePath) throw new Error('No Chrome/Edge found. Set CHROME_PATH.')

await mkdir(outDir, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath, args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const shots = []
const log = []

async function shoot(page, name, options = {}) {
  const file = path.join(outDir, `${name}.png`)
  await page.screenshot({ path: file, fullPage: options.fullPage ?? false })
  shots.push(file)
}

async function pickLocation(page, inputId, query) {
  await page.fill(`#${inputId}`, query)
  const option = page.locator('.location-suggestion').first()
  await option.waitFor({ timeout: 20000 }).catch(() => undefined)
  if (await option.isVisible().catch(() => false)) await option.click()
}

// The app starts with an empty form; fill in an example trip and ask for routes.
async function planExampleTrip(page) {
  await page.fill('#crop-0', 'Tomatoes')
  await page.fill('#crop-quantity-0', '250')
  await page.selectOption('#vehicle', { index: 1 })
  await pickLocation(page, 'origin', 'Baguio City')
  await pickLocation(page, 'destination-0', 'Calamba, Laguna')
  await page.getByRole('button', { name: /find routes/i }).click()
  await page.waitForSelector('.route-select-button', { timeout: 60000 }).catch(() => undefined)
  await page.waitForTimeout(2500)
}

async function run(viewport, suffix) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 })
  const page = await context.newPage()
  page.on('console', message => { if (message.type() === 'error') log.push(`[${suffix}] console: ${message.text()}`) })
  page.on('pageerror', error => log.push(`[${suffix}] pageerror: ${error.message}`))

  await page.goto(`${appUrl}/`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  await shoot(page, `00-plan-empty${suffix}`)
  await planExampleTrip(page)
  await shoot(page, `01-plan${suffix}`)

  await page.goto(`${appUrl}/evaluation`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  await shoot(page, `03-evaluation${suffix}`, { fullPage: true })

  await page.goto(`${appUrl}/about`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  await shoot(page, `04-about${suffix}`, { fullPage: true })

  // Trip: plan (live routes) → use route → active trip, analysing the recorded drive if one exists.
  await page.goto(`${appUrl}/`, { waitUntil: 'networkidle' })
  await planExampleTrip(page)
  let useRoute = page.getByRole('button', { name: /use this route/i }).first()
  if (!(await useRoute.isVisible().catch(() => false))) {
    await page.locator('.route-select-button').first().click()
    await page.waitForTimeout(500)
    useRoute = page.getByRole('button', { name: /use this route/i }).first()
  }
  if (await useRoute.isVisible().catch(() => false)) {
    await useRoute.click()
    await page.waitForURL(/trip\/active/, { timeout: 10000 }).catch(() => undefined)
    const recorded = page.getByRole('button', { name: /analyse recorded drive/i })
    await recorded.waitFor({ timeout: 5000 }).catch(() => undefined)
    if (await recorded.isVisible().catch(() => false)) await recorded.click()
    await page.waitForTimeout(6000)
    await shoot(page, `05-active-trip${suffix}`, { fullPage: true })
    const finding = page.locator('.cv-detection-alert')
    if (await finding.count()) {
      await finding.click()
      await page.waitForTimeout(800)
      await shoot(page, `06-hazard-confirm${suffix}`)
    }
  }
  await context.close()
}

await run({ width: 1440, height: 900 }, '')
await run({ width: 390, height: 844 }, '-mobile')
await browser.close()
console.log(shots.map(file => `saved ${path.relative(process.cwd(), file)}`).join('\n'))
if (log.length) console.log(`\nBrowser errors:\n${log.join('\n')}`)
