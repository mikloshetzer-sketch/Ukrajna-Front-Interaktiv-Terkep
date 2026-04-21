import { FRONT_SECTORS } from './frontSectors.js';

const REFERENCE_PLACES = [
  { name: 'Pokrovsk', lat: 48.281, lng: 37.181, sector: 'donetsk' },
  { name: 'Kostiantynivka', lat: 48.533, lng: 37.706, sector: 'donetsk' },
  { name: 'Chasiv Yar', lat: 48.586, lng: 37.835, sector: 'donetsk' },
  { name: 'Toretsk', lat: 48.397, lng: 37.847, sector: 'donetsk' },
  { name: 'Kurakhove', lat: 47.983, lng: 37.282, sector: 'donetsk' },
  { name: 'Siversk', lat: 48.866, lng: 38.100, sector: 'donetsk' },

  { name: 'Kupiansk', lat: 49.710, lng: 37.615, sector: 'kharkiv' },
  { name: 'Vovchansk', lat: 50.290, lng: 36.941, sector: 'kharkiv' },
  { name: 'Borova', lat: 49.376, lng: 37.621, sector: 'luhansk' },
  { name: 'Svatove', lat: 49.410, lng: 38.150, sector: 'luhansk' },
  { name: 'Kreminna', lat: 49.044, lng: 38.217, sector: 'luhansk' },

  { name: 'Orikhiv', lat: 47.567, lng: 35.785, sector: 'zaporizhzhia' },
  { name: 'Robotyne', lat: 47.443, lng: 35.839, sector: 'zaporizhzhia' },
  { name: 'Tokmak', lat: 47.255, lng: 35.712, sector: 'zaporizhzhia' },

  { name: 'Kherson', lat: 46.635, lng: 32.617, sector: 'kherson' },
  { name: 'Oleshky', lat: 46.644, lng: 32.718, sector: 'kherson' },
  { name: 'Nova Kakhovka', lat: 46.755, lng: 33.348, sector: 'kherson' },
];

function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const toRad = (deg) => deg * Math.PI / 180;

  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
    Math.sin(dLng / 2) ** 2;

  return 2 * R * Math.asin(Math.sqrt(a));
}

export function getSectorForPoint(lat, lng) {
  const point = turf.point([lng, lat]);

  for (const feature of FRONT_SECTORS.features) {
    try {
      if (turf.booleanPointInPolygon(point, feature)) {
        return {
          id: feature.properties.id,
          name: feature.properties.name,
          shortName: feature.properties.shortName,
        };
      }
    } catch (error) {
      console.warn('Sector lookup error:', error);
    }
  }

  return {
    id: 'outside',
    name: 'Outside main named sectors',
    shortName: 'Outside sectors',
  };
}

export function getNearestPlace(lat, lng, sectorId = null) {
  const pool = sectorId
    ? REFERENCE_PLACES.filter(place => place.sector === sectorId)
    : REFERENCE_PLACES;

  const basePool = pool.length ? pool : REFERENCE_PLACES;

  let best = null;
  let bestDistance = Infinity;

  for (const place of basePool) {
    const distanceKm = haversineKm(lat, lng, place.lat, place.lng);
    if (distanceKm < bestDistance) {
      bestDistance = distanceKm;
      best = place;
    }
  }

  if (!best) {
    return {
      name: 'Unknown location',
      distanceKm: null,
      label: 'Unknown location',
    };
  }

  const roundedDistance = Math.round(bestDistance);
  const label =
    roundedDistance <= 3
      ? `${best.name} area`
      : `near ${best.name} (${roundedDistance} km)`;

  return {
    name: best.name,
    distanceKm: bestDistance,
    label,
  };
}

export function enrichDeltaItemsWithPlaceNames(delta) {
  const enrich = (item) => {
    const sector = getSectorForPoint(item.lat, item.lng);
    const nearest = getNearestPlace(item.lat, item.lng, sector.id);

    return {
      ...item,
      sectorName: sector.name,
      sectorShortName: sector.shortName,
      nearestPlace: nearest.label,
      nearestPlaceDistanceKm: nearest.distanceKm,
    };
  };

  const gained = (delta.gained || []).map(enrich);
  const lost = (delta.lost || []).map(enrich);
  const all = (delta.all || []).map(enrich);

  return {
    ...delta,
    gained,
    lost,
    all,
  };
}
