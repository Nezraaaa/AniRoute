const env = import.meta.env

export const defaultCartoStyleUrl = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json'
const configuredMapStyleUrl = (env.VITE_MAP_STYLE_URL || '').trim()

export const appConfig = {
  apiBaseUrl: (env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, ''),
  mapStyleUrl: /^https?:\/\//i.test(configuredMapStyleUrl) ? configuredMapStyleUrl : defaultCartoStyleUrl,
  cartoBasemapKey: env.VITE_CARTO_BASEMAP_KEY || env.NEXT_PUBLIC_CARTO_BASEMAP_KEY || '',
  demoMode: env.VITE_DEMO_MODE !== 'false',
  paths: {
    routes: env.VITE_API_ROUTES_PATH || '/api/routes/calculate',
    recalculate: env.VITE_API_RECALCULATE_PATH || '/api/routes/recalculate',
    scannerStart: env.VITE_API_SCAN_START_PATH || '/api/hazards/scanning/start',
    scannerStop: env.VITE_API_SCAN_STOP_PATH || '/api/hazards/scanning/stop',
    scannerFrame: env.VITE_API_SCAN_FRAME_PATH || '/api/hazards/scan-frame',
    hazardConfirm: env.VITE_API_HAZARD_CONFIRM_PATH || '/api/hazards/confirm',
    health: env.VITE_API_HEALTH_PATH || '/api/health',
    geocode: env.VITE_API_GEOCODE_PATH || '/api/geocode/search',
  },
}

export function withCartoBasemapKey(url: string): string {
  const key = appConfig.cartoBasemapKey
  if (!key || !/cartocdn\.com/i.test(url)) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}key=${encodeURIComponent(key)}`
}

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return `${appConfig.apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`
}
