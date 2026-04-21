import { FRONT_SECTORS } from './frontSectors.js';
import { getSectorForPoint, getNearestPlace } from './placeLookup.js';

const FRONT_DISTANCE_KM = 35;

const RUSSIAN_REAR_ZONES = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { name: 'Belgorod rear area' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [35.2, 49.7],
          [38.8, 49.7],
          [38.8, 51.8],
          [35.2, 51.8],
          [35.2, 49.7]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Kursk rear area' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [34.0, 50.6],
          [38.5, 50.6],
          [38.5, 52.8],
          [34.0, 52.8],
          [34.0, 50.6]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Rostov rear area' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [37.0, 46.2],
          [41.8, 46.2],
          [41.8, 48.8],
          [37.0, 48.8],
          [37.0, 46.2]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: { name: 'Crimea / south rear area' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [32.0, 44.0],
          [37.8, 44.0],
          [37.8, 46.8],
          [32.0, 46.8],
          [32.0, 44.0]
        ]]
      }
    }
  ]
};

const ROMANIA_ZONE = {
  type: 'Feature',
  properties: { name: 'Romania' },
  geometry: {
    type: 'Polygon',
    coordinates: [[
      [20.5, 43.5],
      [30.5, 43.5],
      [30.5, 48.7],
      [20.5, 48.7],
      [20.5, 43.5]
    ]]
  }
};

const MOLDOVA_ZONE = {
  type: 'Feature',
  properties: { name: 'Moldova' },
  geometry: {
    type: 'Polygon',
    coordinates: [[
      [26.2, 45.3],
      [30.3, 45.3],
      [30.3, 48.8],
      [26.2, 48.8],
      [26.2, 45.3]
    ]]
  }
};

const UKRAINIAN_REAR_ZONE = {
  type: 'Feature',
  properties: { name: 'Ukraine rear area' },
  geometry: {
    type: 'Polygon',
    coordinates: [[
      [22.0, 44.0],
      [41.5, 44.0],
      [41.5, 52.6],
      [22.0, 52.6],
      [22.0, 44.0]
    ]]
  }
};

function makeGridKey(lat, lng, cellSizeDeg) {
  const latIdx = Math.floor(lat / cellSizeDeg);
  const lngIdx = Math.floor(lng / cellSizeDeg);
  return `${latIdx}:${lngIdx}`;
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

function pointInFeatureCollection(point, featureCollection) {
  for (const feature of featureCollection.features || []) {
    try {
      if (turf.booleanPointInPolygon(point, feature)) {
        return feature;
      }
    } catch (error) {
      console.warn('pointInFeatureCollection error:', error);
    }
  }
  return null;
}

function minDistanceToFrontSectorsKm(lat, lng) {
  const point = turf.point([lng, lat]);
  let minDistance = Infinity;

  for (const feature of FRONT_SECTORS.features) {
    try {
      if (turf.booleanPointInPolygon(point, feature)) {
        return 0;
      }

      const line = turf.polygonToLine(feature);
      const distanceKm = turf.pointToLineDistance(point, line, { units: 'kilometers' });

      if (distanceKm < minDistance) {
        minDistance = distanceKm;
      }
    } catch (error) {
      console.warn('Front distance calculation error:', error);
    }
  }

  return minDistance;
}

export function categorizeFirmsPoints(points = []) {
  return points.map((point) => {
    const lat = Number(point.lat);
    const lng = Number(point.lng);
    const turfPoint = turf.point([lng, lat]);

    const sector = getSectorForPoint(lat, lng);
    const nearest = getNearestPlace(lat, lng, sector.id);
    const distanceToFrontKm = minDistanceToFrontSectorsKm(lat, lng);

    const inRomania = turf.booleanPointInPolygon(turfPoint, ROMANIA_ZONE);
    const inMoldova = turf.booleanPointInPolygon(turfPoint, MOLDOVA_ZONE);

    let category = 'other';
    let categoryLabel = 'Other hotspot';

    if (distanceToFrontKm <= FRONT_DISTANCE_KM) {
      category = 'front';
      categoryLabel = 'Front-adjacent hotspot';
    } else if (pointInFeatureCollection(turfPoint, RUSSIAN_REAR_ZONES)) {
      category = 'russian_rear';
      categoryLabel = 'Russian rear-area / possible deep-strike hotspot';
    } else if (inRomania || inMoldova) {
      category = 'other';
      categoryLabel = inRomania
        ? 'Romania / border-region hotspot'
        : 'Moldova / border-region hotspot';
    } else if (turf.booleanPointInPolygon(turfPoint, UKRAINIAN_REAR_ZONE)) {
      category = 'ukrainian_rear';
      categoryLabel = 'Ukrainian rear-area hotspot';
    }

    return {
      ...point,
      sectorName: sector.name,
      sectorShortName: sector.shortName,
      nearestPlace: nearest.label,
      nearestPlaceDistanceKm: nearest.distanceKm,
      distanceToFrontKm,
      category,
      categoryLabel,
    };
  });
}

function summarizeCategory(points, windowDays) {
  if (!points.length) return [];

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

  const zones = [];

  for (const [key, bucketPoints] of buckets.entries()) {
    if (!bucketPoints.length) continue;

    const centroid = getCentroid(bucketPoints);
    const sector = getSectorForPoint(centroid.lat, centroid.lng);
    const nearest = getNearestPlace(centroid.lat, centroid.lng, sector.id);
    const bounds = buildBounds(bucketPoints);

    zones.push({
      key,
      count: bucketPoints.length,
      bounds,
      centroid,
      sectorName: sector.name,
      sectorShortName: sector.shortName,
      nearestPlace: nearest.label,
      category: bucketPoints[0].category,
      categoryLabel: bucketPoints[0].categoryLabel,
      windowDays,
    });
  }

  return zones.sort((a, b) => b.count - a.count);
}

export function summarizeFirmsHotspots(points = [], windowDays = 3) {
  const categorized = points;

  const front = categorized.filter(p => p.category === 'front');
  const ukrainianRear = categorized.filter(p => p.category === 'ukrainian_rear');
  const russianRear = categorized.filter(p => p.category === 'russian_rear');
  const other = categorized.filter(p => p.category === 'other');

  const frontZones = summarizeCategory(front, windowDays);
  const ukrainianRearZones = summarizeCategory(ukrainianRear, windowDays);
  const russianRearZones = summarizeCategory(russianRear, windowDays);
  const otherZones = summarizeCategory(other, windowDays);

  const allZones = [
    ...frontZones,
    ...ukrainianRearZones,
    ...russianRearZones,
    ...otherZones,
  ].sort((a, b) => b.count - a.count);

  return {
    windowDays,
    totalPoints: categorized.length,
    countsByCategory: {
      front: front.length,
      ukrainianRear: ukrainianRear.length,
      russianRear: russianRear.length,
      other: other.length,
    },
    topZone: allZones[0] || null,
    topFront: frontZones[0] || null,
    topUkrainianRear: ukrainianRearZones[0] || null,
    topRussianRear: russianRearZones[0] || null,
    topOther: otherZones[0] || null,
    topThreeZones: allZones.slice(0, 3),
  };
}
