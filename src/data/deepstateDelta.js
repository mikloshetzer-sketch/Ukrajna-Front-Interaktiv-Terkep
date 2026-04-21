import { featureRepresentativePoint, roughAreaKm2 } from '../utils/geo.js';

function signatureFromFeature(feature) {
  const geometry = feature?.geometry;
  if (!geometry) return null;
  return JSON.stringify(geometry);
}

export function computeNaiveDailyDelta(previousGeoJson, currentGeoJson) {
  const prevFeatures = previousGeoJson?.features ?? [];
  const currFeatures = currentGeoJson?.features ?? [];

  const prevSet = new Set(prevFeatures.map(signatureFromFeature).filter(Boolean));
  const currSet = new Set(currFeatures.map(signatureFromFeature).filter(Boolean));

  const gained = currFeatures
    .filter(feature => {
      const sig = signatureFromFeature(feature);
      return sig && !prevSet.has(sig);
    })
    .map(feature => ({
      type: 'gain',
      point: featureRepresentativePoint(feature),
      areaKm2: roughAreaKm2(feature),
      feature,
    }))
    .filter(item => item.point);

  const lost = prevFeatures
    .filter(feature => {
      const sig = signatureFromFeature(feature);
      return sig && !currSet.has(sig);
    })
    .map(feature => ({
      type: 'loss',
      point: featureRepresentativePoint(feature),
      areaKm2: roughAreaKm2(feature),
      feature,
    }))
    .filter(item => item.point);

  return { gained, lost };
}
