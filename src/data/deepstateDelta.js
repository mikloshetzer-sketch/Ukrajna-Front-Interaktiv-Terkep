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

function safeUnionAll(featureCollection) {
  const features = (featureCollection?.features || []).filter(Boolean);

  if (!features.length) return turf.featureCollection([]);

  let merged = features[0];

  for (let i = 1; i < features.length; i += 1) {
    try {
      merged = turf.union(merged, features[i]) || merged;
    } catch (e) {
      // ha egy union hibára fut, nem állítjuk meg az egészet
      console.warn('Union hiba:', e);
    }
  }

  return normalizeFeatureCollection(merged);
}

function safeDifference(a, b) {
  try {
    const diff = turf.difference(a, b);
    return normalizeFeatureCollection(diff);
  } catch (e) {
    console.warn('Difference hiba:', e);
    return turf.featureCollection([]);
  }
}

function splitFeatures(featureCollection) {
  const out = [];
  turf.flattenEach(featureCollection, (feature) => {
    if (feature?.geometry) out.push(feature);
  });
  return out;
}

function getRepresentativePoint(feature) {
  try {
    const point = turf.pointOnFeature(feature);
    return {
      lng: point.geometry.coordinates[0],
      lat: point.geometry.coordinates[1],
    };
  } catch {
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
  } catch {
    return 0;
  }
}

function getRadiusMetersFromAreaKm2(areaKm2) {
  // Egyenértékű kör sugara, de láthatóság miatt korlátozva
  const radius = Math.sqrt((areaKm2 * 1_000_000) / Math.PI);
  return Math.max(1500, Math.min(radius, 30000));
}

function buildChangeItems(featureCollection, changeType) {
  const features = splitFeatures(featureCollection);

  return features
    .map((feature) => {
      const areaKm2 = getAreaKm2(feature);
      if (areaKm2 <= 0.05) return null;

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
  const prevFc = flattenToPolygons(normalizeFeatureCollection(previousGeoJson));
  const currFc = flattenToPolygons(normalizeFeatureCollection(currentGeoJson));

  // Egységesített napi megszállt terület
  const prevMerged = safeUnionAll(prevFc);
  const currMerged = safeUnionAll(currFc);

  // Orosz területszerzés = mai megszállt terület - tegnapi megszállt terület
  const gainedArea = safeDifference(currMerged, prevMerged);

  // Ukrán visszaszerzés = tegnapi megszállt terület - mai megszállt terület
  const lostArea = safeDifference(prevMerged, currMerged);

  const gained = buildChangeItems(gainedArea, 'gain');
  const lost = buildChangeItems(lostArea, 'loss');

  const allChanges = [...gained, ...lost]
    .sort((a, b) => b.areaKm2 - a.areaKm2)
    .slice(0, 5);

  return {
    gained: allChanges.filter((item) => item.type === 'gain'),
    lost: allChanges.filter((item) => item.type === 'loss'),
    all: allChanges,
    totals: {
      gainedKm2: gained.reduce((sum, item) => sum + item.areaKm2, 0),
      lostKm2: lost.reduce((sum, item) => sum + item.areaKm2, 0),
    },
  };
}
