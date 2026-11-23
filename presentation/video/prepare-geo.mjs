// Extracts the Philippine coastline (Natural Earth 1:10m via world-atlas) for the 3D relief map.
import { readFile, writeFile } from 'node:fs/promises'
import { feature } from 'topojson-client'
const topo = JSON.parse(await readFile(new URL('./node_modules/world-atlas/countries-10m.json', import.meta.url)))
const ph = feature(topo, topo.objects.countries).features.find(f => f.properties.name === 'Philippines')
const polys = ph.geometry.type === 'Polygon' ? [ph.geometry.coordinates] : ph.geometry.coordinates
// Keep islands that touch Luzon and the nearby islands the camera sees; drop tiny islets.
const keep = polys.map(p => p[0]).filter(ring => {
  const lats = ring.map(c => c[1]); const lons = ring.map(c => c[0])
  const big = ring.length > 12
  return big && Math.max(...lats) > 11.5 && Math.min(...lons) < 125
})
await writeFile(new URL('./assets/philippines.json', import.meta.url), JSON.stringify(keep.map(r => r.map(([x, y]) => [+x.toFixed(4), +y.toFixed(4)]))))
console.log('rings', keep.length, 'points', keep.reduce((a, r) => a + r.length, 0))
