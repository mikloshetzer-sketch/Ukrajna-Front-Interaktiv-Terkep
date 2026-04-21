function flattenCoordinates(geometry) {
  if (!geometry) return [];
  const { type, coordinates } = geometry;
  if (type === 'Polygon') return coordinates.flat(1);
  if (type === 'MultiPolygon') return coordinates.flat(2);
  return [];
}

function centroidFromFeature(feature) {
  const coords = flattenCoordinates(feature.geometry);
  if (!coords.length) return null;

  let sumLng = 0;
  let sumLat = 0;

  coords.forEach(([lng, lat]) => {
    sumLng += lng;
    sumLat += lat;
  });

  return { lng: sumLng / coords.length, lat: sumLat / coords.length };
}

function pseudoAreaKm2(feature) {
  const coords = flattenCoordinates(feature.geometry);
  return Math.max(0.5, coords.length * 0.2);
}

function keyForFeature(feature) {
  const c = centroidFromFeature(feature);
  if (!c) return null;
  return `${c.lat.toFixed(3)}|${c.lng.toFixed(3)}`;
}

export function computeNaiveDailyDelta(previousGeoJson, currentGeoJson) {
  const prev = new Map();
  const curr = new Map();

  (previousGeoJson?.features || []).forEach(feature => {
    const key = keyForFeature(feature);
    if (key) prev.set(key, feature);
  });

  (currentGeoJson?.features || []).forEach(feature => {
    const key = keyForFeature(feature);
    if (key) curr.set(key, feature);
  });

  const gained = [];
  const lost = [];

  curr.forEach((feature, key) => {
    if (!prev.has(key)) {
      const c = centroidFromFeature(feature);
      if (c) gained.push({ ...c, areaKm2: pseudoAreaKm2(feature) });
    }
  });

  prev.forEach((feature, key) => {
    if (!curr.has(key)) {
      const c = centroidFromFeature(feature);
      if (c) lost.push({ ...c, areaKm2: pseudoAreaKm2(feature) });
    }
  });

  return { gained, lost };
}
