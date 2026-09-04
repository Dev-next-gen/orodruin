// Day/night terminator — GeoJSON polygon of the NIGHT side of Earth for a given
// instant (real UTC). Ported from the classic L.Terminator algorithm.

const RAD = Math.PI / 180, DEG = 180 / Math.PI;

function julian(date) { return date.getTime() / 86400000 + 2440587.5; }
function gmst(j) { const d = j - 2451545.0; let g = (18.697374558 + 24.06570982441908 * d) % 24; return g < 0 ? g + 24 : g; }

function sunEcliptic(j) {
  const n = j - 2451545.0;
  let L = (280.460 + 0.9856474 * n) % 360; if (L < 0) L += 360;
  let g = (357.528 + 0.9856003 * n) % 360; if (g < 0) g += 360;
  const lambda = L + 1.915 * Math.sin(g * RAD) + 0.02 * Math.sin(2 * g * RAD);
  return lambda;
}
function obliquity(j) {
  const T = (j - 2451545.0) / 36525;
  return 23.43929111 - T * (46.836769 / 3600 - T * (0.0001831 / 3600 + T * (0.0020034 / 3600)));
}
function sunEquatorial(lambda, obl) {
  const alpha = Math.atan2(Math.cos(obl * RAD) * Math.sin(lambda * RAD), Math.cos(lambda * RAD)) * DEG;
  const delta = Math.asin(Math.sin(obl * RAD) * Math.sin(lambda * RAD)) * DEG;
  return { alpha, delta };
}

export function subsolarPoint(date = new Date()) {
  const j = julian(date);
  const sun = sunEquatorial(sunEcliptic(j), obliquity(j));
  let lon = -(gmst(j) * 15 - sun.alpha);
  lon = ((lon + 540) % 360) - 180;
  return { lat: sun.delta, lon };
}

export function terminatorLine(date = new Date()) {
  const j = julian(date);
  const sun = sunEquatorial(sunEcliptic(j), obliquity(j));
  const g = gmst(j);
  const coords = [];
  for (let lng = -180; lng <= 180; lng += 1) {
    const ha = g * 15 + lng - sun.alpha;
    coords.push([lng, Math.atan(-Math.cos(ha * RAD) / Math.tan(sun.delta * RAD)) * DEG]);
  }
  return { type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} };
}

export function nightPolygon(date = new Date()) {
  const j = julian(date);
  const sun = sunEquatorial(sunEcliptic(j), obliquity(j));
  const g = gmst(j);
  const coords = [];
  for (let lng = -180; lng <= 180; lng += 1) {
    const ha = g * 15 + lng - sun.alpha; // hour angle in degrees
    const lat = Math.atan(-Math.cos(ha * RAD) / Math.tan(sun.delta * RAD)) * DEG;
    coords.push([lng, lat]);
  }
  // close the ring over the currently-dark pole
  const darkPole = sun.delta > 0 ? -90 : 90;
  coords.push([180, darkPole]);
  coords.push([-180, darkPole]);
  coords.push([-180, coords[0][1]]);
  return {
    type: "Feature",
    geometry: { type: "Polygon", coordinates: [coords] },
    properties: {},
  };
}
