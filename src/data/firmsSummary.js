import { getSectorForPoint, getNearestPlace } from './placeLookup.js';

function makeGridKey(lat, lng, cellSizeDeg) {
  const latIdx = Math.floor(lat / cellSizeDeg);
  const lngIdx = Math.floor(lng / cellSizeDeg);
  return `${latIdx}:${lngIdx}`;
}

function parseGridKey(key) {
  const [latIdx, lngIdx] = key.split(':').map(Number);
  return { latIdx, lngIdx };
}

function buildBounds(points, paddingDeg = 0.12) {
  const lats = points.map(p => Number(p.lat));
  const lngs = points.map(p => Number(p.lng));

  const minLat = Math.min(...lats) - paddingDeg;
  const maxLat = Math.max(...lats) + paddingDeg;
  const minLng = Math.min(...lngs) - paddingDeg;
  const maxLng = Math.max(...lngs) + paddingDeg;

  return [
    [minLat, minLng],
    [maxLat, maxLng],
  ];
}

function getCentroid(points) {
  const lat = points.reduce((sum, p) => sum + Number(p.lat), 0) / points.length;
  const lng = points.reduce((sum, p) => sum + Number(p.lng), 0) / points.length;
  return { lat, lng };
}

export function summarizeFirmsHotspots(points = [], windowDays = 3) {
  if (!points.length) {
    return {
      topZone: null,
      windowDays,
      totalPoints: 0,
    };
  }

  // kb. 0.35 fokos rács = praktikus első klaszterezés
  const cellSizeDeg = 0.35;
  const buckets = new Map();

  for (const point of points) {
    const lat = Number(point.lat);
    const lng = Number(point.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;

    const key = makeGridKey(lat, lng, cellSizeDeg);

    if (!buckets.has(key)) {
      buckets.set(key, []);
    }

    buckets.get(key).push(point);
  }

  let bestKey = null;
  let bestPoints = [];

  for (const [key, bucketPoints] of buckets.entries()) {
    if (bucketPoints.length > bestPoints.length) {
      bestKey = key;
      bestPoints = bucketPoints;
    }
  }

  if (!bestKey || !bestPoints.length) {
    return {
      topZone: null,
      windowDays,
      totalPoints: points.length,
    };
  }

  const centroid = getCentroid(bestPoints);
  const sector = getSectorForPoint(centroid.lat, centroid.lng);
  const nearest = getNearestPlace(centroid.lat, centroid.lng, sector.id);
  const bounds = buildBounds(bestPoints);

  return {
    windowDays,
    totalPoints: points.length,
    topZone: {
      key: bestKey,
      count: bestPoints.length,
      bounds,
      centroid,
      sectorName: sector.name,
      sectorShortName: sector.shortName,
      nearestPlace: nearest.label,
    },
  };
}
