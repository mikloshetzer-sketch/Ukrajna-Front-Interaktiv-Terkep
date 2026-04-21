function signedArea(ring) {
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i += 1) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    sum += (x1 * y2) - (x2 * y1);
  }
  return sum / 2;
}

function centroidOfRing(ring) {
  const area = signedArea(ring);
  if (!area) return ring[0] ?? [0, 0];
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < ring.length - 1; i += 1) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    const factor = (x1 * y2) - (x2 * y1);
    cx += (x1 + x2) * factor;
    cy += (y1 + y2) * factor;
  }
  return [cx / (6 * area), cy / (6 * area)];
}

export function featureRepresentativePoint(feature) {
  const geometry = feature?.geometry;
  if (!geometry) return null;

  if (geometry.type === 'Point') return geometry.coordinates;
  if (geometry.type === 'Polygon') return centroidOfRing(geometry.coordinates[0]);
  if (geometry.type === 'MultiPolygon') return centroidOfRing(geometry.coordinates[0][0]);
  if (geometry.type === 'LineString') return geometry.coordinates[Math.floor(geometry.coordinates.length / 2)];
  return null;
}

export function roughAreaKm2(feature) {
  const geometry = feature?.geometry;
  if (!geometry) return 0;
  const polygon = geometry.type === 'Polygon'
    ? geometry.coordinates[0]
    : geometry.type === 'MultiPolygon'
      ? geometry.coordinates[0][0]
      : null;
  if (!polygon) return 0;

  const areaDeg = Math.abs(signedArea(polygon));
  const [lon, lat] = centroidOfRing(polygon);
  const latFactor = Math.cos((lat * Math.PI) / 180);
  const kmPerDegLat = 111.32;
  const kmPerDegLon = 111.32 * latFactor;
  return areaDeg * kmPerDegLat * kmPerDegLon;
}
