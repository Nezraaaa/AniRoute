// Renders the AniRoute product film frame by frame on the GPU (headless Chrome) and encodes it with ffmpeg.
//
//   node render.mjs                     → out/AniRoute_ProductFilm_1080p.mp4 (1920 x 1080, 60 fps, with soundtrack)
//   node render.mjs --fps 30            → 30 fps version (faster to render)
//   node render.mjs --4k                → out/AniRoute_ProductFilm_4K.mp4    (3840 x 2160)
//   node render.mjs --stills 2,6,12.5   → out/stills/*.png (quick look at chosen seconds)
//
// Needs Chrome or Edge, and ffmpeg on PATH. Fonts load from Google Fonts (internet required).
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { existsSync, createReadStream, statSync } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(path.join(here, '../../frontend/package.json'))
const { chromium } = require('playwright-core')

const args = process.argv.slice(2)
const is4k = args.includes('--4k')
const stillsArg = args.includes('--stills') ? args[args.indexOf('--stills') + 1] : null
const fromArg = args.includes('--from') ? Number(args[args.indexOf('--from') + 1]) : 0
const toArg = args.includes('--to') ? Number(args[args.indexOf('--to') + 1]) : null
const lang = args.includes('--lang') ? args[args.indexOf('--lang') + 1] : 'en'
const fpsArg = args.includes('--fps') ? Number(args[args.indexOf('--fps') + 1]) : 60
const W = is4k ? 3840 : 1920, H = is4k ? 2160 : 1080, FPS = fpsArg
const SUB = FPS >= 50 ? 4 : 5   // motion-blur sub-frames per output frame

const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.wav': 'audio/wav' }
const server = createServer((req, res) => {
  const p = path.join(here, decodeURIComponent(new URL(req.url, 'http://x').pathname))
  if (!p.startsWith(here) || !existsSync(p) || statSync(p).isDirectory()) { res.writeHead(404); res.end(); return }
  res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' })
  createReadStream(p).pipe(res)
})
await new Promise(r => server.listen(0, '127.0.0.1', r))
const port = server.address().port

const exe = [process.env.CHROME_PATH, 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', '/usr/bin/google-chrome'].filter(Boolean).find(p => existsSync(p))
const browser = await chromium.launch({ headless: true, executablePath: exe, args: ['--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=d3d11', '--enable-gpu-rasterization'] })
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 })
const logs = []
page.on('console', m => { if (['error', 'warning'].includes(m.type())) logs.push(m.text()) })
page.on('pageerror', e => logs.push(`pageerror: ${e.message}`))
await page.goto(`http://127.0.0.1:${port}/scene.html?mode=render&w=${W}&h=${H}&fps=${FPS}&sub=${SUB}&lang=${lang}`)
try {
  await page.waitForFunction('window.__ready === true', null, { timeout: 180000 })
} catch (e) {
  console.error('Scene failed to load:\n' + logs.join('\n')); await browser.close(); server.close(); process.exit(1)
}
const gpu = await page.evaluate(() => { const gl = document.querySelector('canvas').getContext('webgl2'); const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'unknown' })
console.log(`GPU: ${gpu}  ·  ${W}x${H}`)
const canvas = page.locator('canvas')

if (stillsArg) {
  const dir = path.join(here, 'out', 'stills'); await mkdir(dir, { recursive: true })
  for (const s of stillsArg.split(',').map(Number)) {
    await page.evaluate(t => window.__frame(t), s)
    const f = path.join(dir, `${lang === 'tl' ? 'tl_' : ''}t${String(s.toFixed(2)).padStart(5, '0')}.png`)
    await canvas.screenshot({ path: f })
    console.log('still', f)
  }
} else {
  await mkdir(path.join(here, 'out'), { recursive: true })
  const suffix = lang === 'tl' ? '_Tagalog' : ''
  const outFile = path.join(here, 'out', (is4k ? 'AniRoute_ProductFilm_4K' : 'AniRoute_ProductFilm_1080p') + suffix + '.mp4')
  const audio = path.join(here, 'assets', lang === 'tl' ? 'soundtrack_tl.wav' : 'soundtrack.wav')
  const duration = await page.evaluate(() => window.__duration || 30)
  const total = Math.round((toArg ?? duration) * FPS)
  const first = Math.round(fromArg * FPS)
  const ff = spawn('ffmpeg', [
    '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    ...(existsSync(audio) && !toArg && !fromArg ? ['-i', audio, '-c:a', 'aac', '-b:a', '256k', '-shortest'] : []),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', is4k ? '17' : '15', '-pix_fmt', 'yuv420p',
    '-profile:v', 'high', '-tune', 'film', '-movflags', '+faststart', outFile,
  ], { stdio: ['pipe', 'inherit', 'pipe'] })
  let ffErr = ''
  ff.stderr.on('data', d => { ffErr += d })
  const started = Date.now()
  for (let f = first; f < total; f++) {
    await page.evaluate(t => window.__frame(t), f / FPS)
    const buf = await canvas.screenshot({ type: 'png' })
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r))
    if (f % 30 === 0) {
      const done = f - first + 1, rate = done / ((Date.now() - started) / 1000)
      console.log(`frame ${f}/${total}  ${rate.toFixed(1)} fps  eta ${((total - f) / rate).toFixed(0)} s`)
    }
  }
  ff.stdin.end()
  const code = await new Promise(r => ff.on('close', r))
  if (code !== 0) console.error(ffErr.slice(-3000))
  else console.log('wrote', outFile)
}
if (logs.length) console.log('\nBrowser messages:\n' + [...new Set(logs)].slice(0, 30).join('\n'))
await browser.close()
server.close()
