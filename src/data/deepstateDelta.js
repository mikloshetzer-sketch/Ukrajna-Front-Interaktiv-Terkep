function ensureFeature(input) {
  if (!input) return null;

  if (input.type === 'Feature') return input;

  if (input.type === 'FeatureCollection') {
    const first = input.features?.find(f => f?.geometry);
    return first || null;
  }

  return null;
}

function flattenPolygonFeatures(geojson) {
  const features = [];

  if (!geojson) return features;

  const fc = geojson.type === 'FeatureCollection'
    ? geojson
    : geojson.type === 'Feature'
      ? turf.featureCollection([geojson])
      : turf.featureCollection([]);

  turf.flattenEach(fc, (feature) => {
    if (!feature?.geometry) return;

    const type = feature.geometry.type;
    if (type === 'Polygon' || type === 'MultiPolygon') {
      features.push(feature);
    }
  });

  return features;
}

function mergeAllPolygons(features) {
  if (!features.length) return null;

  let merged = features[0];

  for (let i = 1; i < features.length; i += 1) {
    try {
      const unionResult = turf.union(merged, features[i]);
      if (unionResult) merged = unionResult;
    } catch (error) {
      console.warn('Union hiba:', error);
    }
  }

  return ensureFeature(merged);
}

function differenceSafe(a, b) {
  if (!a || !b) return null;

  try {
    const diff = turf.difference(a, b);
    return ensureFeature(diff);
  } catch (error) {
    console.warn('Difference hiba:', error);
    return null;
  }
}

function explodeToFeatures(feature) {
  if (!feature) return [];

  const result = [];

  turf.flattenEach(turf.featureCollection([feature]), (f) => {
    if (f?.geometry) result.push(f);
  });

  return result;
}

function representativePoint(feature) {
  try {
    const pt = turf.pointOnFeature(feature);
    return {
      lng: pt.geometry.coordinates[0],
      lat: pt.geometry.coordinates[1],
    };
  } catch (error) {
    console.warn('pointOnFeature hiba, center fallback:', error);

    const pt = turf.center(feature);
    return {
      lng: pt.geometry.coordinates[0],
      lat: pt.geometry.coordinates[1],
    };
  }
}

function areaKm2(feature) {
  try {
    return turf.area(feature) / 1_000_000;
  } catch (error) {
    console.warn('Area hiba:', error);
    return 0;
  }
}

function radiusMetersFromKm2(km2) {
  if (km2 <= 0) return 5000;

  const r = Math.sqrt((km2 * 1_000_000) / Math.PI);
  const scaled = r * 2.8;

  return Math.max(5000, Math.min(scaled, 60000));
}

function buildItems(feature, type) {
  return explodeToFeatures(feature)
    .map((f) => {
      const km2 = areaKm2(f);

      if (km2 < 0.03) return null;

      const pt = representativePoint(f);

      return {
        type,
        feature: f,
        areaKm2: km2,
        lat: pt.lat,
        lng: pt.lng,
        radiusMeters: radiusMetersFromKm2(km2),
      };
    })
    .filter(Boolean);
}

export function computeNaiveDailyDelta(previousGeoJson, currentGeoJson) {
  const previousFeatures = flattenPolygonFeatures(previousGeoJson);
  const currentFeatures = flattenPolygonFeatures(currentGeoJson);

  const previousMerged = mergeAllPolygons(previousFeatures);
  const currentMerged = mergeAllPolygons(currentFeatures);

  if (!previousMerged || !currentMerged) {
    return {
      gained: [],
      lost: [],
      all: [],
      totals: {
        gainedKm2: 0,
        lostKm2: 0,
      },
    };
  }

  const gainedFeature = differenceSafe(currentMerged, previousMerged);
  const lostFeature = differenceSafe(previousMerged, currentMerged);

  const gained = buildItems(gainedFeature, 'gain');
  const lost = buildItems(lostFeature, 'loss');

  const all = [...gained, ...lost]
    .sort((a, b) => b.areaKm2 - a.areaKm2)
    .slice(0, 5);

  return {
    gained: all.filter(item => item.type === 'gain'),
    lost: all.filter(item => item.type === 'loss'),
    all,
    totals: {
      gainedKm2: gained.reduce((sum, item) => sum + item.areaKm2, 0),
      lostKm2: lost.reduce((sum, item) => sum + item.areaKm2, 0),
    },
  };
}
