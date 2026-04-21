function normalizeFeatureCollection(input) {
  if (!input) {
    return turf.featureCollection([]);
  }

  if (input.type === 'FeatureCollection') {
    return input;
  }

  if (input.type === 'Feature') {
    return turf.featureCollection([input]);
  }

  return turf.featureCollection([]);
}

function flattenToPolygons(featureCollection) {
  const result = [];

  turf.flattenEach(featureCollection, (feature) => {
    if (!feature || !feature.geometry) return;

    const type = feature.geometry.type;
    if (type === 'Polygon' || type === 'MultiPolygon') {
      result.push(feature);
    }
  });

  return turf.featureCollection(result);
}

function dissolveSequentially(featureCollection) {
  const features = (featureCollection?.features || []).filter(Boolean);

  if (!features.length) {
    return turf.featureCollection([]);
  }

  let merged = features[0];

  for (let i = 1; i < features.length; i += 1) {
    try {
      const unionResult = turf.union(merged, features[i]);
      if (unionResult) {
        merged = unionResult;
      }
    } catch (error) {
      console.warn('Union hiba, feature kihagyva:', error);
    }
  }

  return normalizeFeatureCollection(merged);
}

function safeDifference(a, b) {
  try {
    const diff = turf.difference(a, b);
    return normalizeFeatureCollection(diff);
  } catch (error) {
    console.warn('Difference hiba:', error);
    return turf.featureCollection([]);
  }
}

function splitToSingleFeatures(featureCollection) {
  const items = [];

  turf.flattenEach(featureCollection, (feature) => {
    if (feature?.geometry) {
      items.push(feature);
    }
  });

  return items;
}

function getRepresentativePoint(feature) {
  try {
    const point = turf.pointOnFeature(feature);
    return {
      lng: point.geometry.coordinates[0],
      lat: point.geometry.coordinates[1],
    };
  } catch (error) {
    console.warn('pointOnFeature hiba, center fallback:', error);
    const center = turf.center(feature);
    return {
      lng: center.geometry.coordinates[0],
      lat: center.geometry.coordinates[1],
    };
  }
}

function getAreaKm2(feature) {
  try {
    return turf.area(feature) / 1_000_000;
  } catch (error) {
    console.warn('Area hiba:', error);
    return 0;
  }
}

function getRadiusMetersFromAreaKm2(areaKm2) {
  if (!areaKm2 || areaKm2 <= 0) {
    return 1500;
  }

  const equivalentCircleRadius = Math.sqrt((areaKm2 * 1_000_000) / Math.PI);

  return Math.max(1500, Math.min(equivalentCircleRadius, 30000));
}

function buildChangeItems(featureCollection, changeType) {
  const features = splitToSingleFeatures(featureCollection);

  return features
    .map((feature) => {
      const areaKm2 = getAreaKm2(feature);

      // kis zajok kiszűrése
      if (areaKm2 < 0.05) {
        return null;
      }

      const point = getRepresentativePoint(feature);

      return {
        type: changeType,
        feature,
        areaKm2,
        lat: point.lat,
        lng: point.lng,
        radiusMeters: getRadiusMetersFromAreaKm2(areaKm2),
      };
    })
    .filter(Boolean);
}

export function computeNaiveDailyDelta(previousGeoJson, currentGeoJson) {
  const previousFc = flattenToPolygons(normalizeFeatureCollection(previousGeoJson));
  const currentFc = flattenToPolygons(normalizeFeatureCollection(currentGeoJson));

  // Egységes napi megszállt terület előállítása
  const previousMerged = dissolveSequentially(previousFc);
  const currentMerged = dissolveSequentially(currentFc);

  // Orosz területszerzés: mai - tegnapi
  const gainedAreas = safeDifference(currentMerged, previousMerged);

  // Ukrán visszaszerzés: tegnapi - mai
  const lostAreas = safeDifference(previousMerged, currentMerged);

  const gained = buildChangeItems(gainedAreas, 'gain');
  const lost = buildChangeItems(lostAreas, 'loss');

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
