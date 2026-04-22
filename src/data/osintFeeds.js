import { getSectorForPoint, getNearestPlace } from './placeLookup.js';

const OSINT_FEED_FILE = './data/osint_feed.json';

function sourcePriority(sourceType) {
  if (sourceType === 'Ukrainian official') return 3;
  if (sourceType === 'ISW') return 2;
  return 1;
}

function makeClusterKey(item) {
  const latCell = Math.round(Number(item.lat) * 2) / 2;
  const lngCell = Math.round(Number(item.lng) * 2) / 2;
  return `${item.sourceType || 'OSINT'}|${item.nearestPlace || 'Unknown'}|${latCell}|${lngCell}`;
}

function getTopCategory(items) {
  const counts = new Map();

  items.forEach(item => {
    const category = item.category || 'general military update';
    counts.set(category, (counts.get(category) || 0) + 1);
  });

  let best = 'general military update';
  let bestCount = -1;

  for (const [category, count] of counts.entries()) {
    if (count > bestCount) {
      best = category;
      bestCount = count;
    }
  }

  return best;
}

function buildClusterTitle(items, sourceType) {
  const count = items.length;
  if (count === 1) {
    return items[0].title || 'Untitled event';
  }

  return `${count} ${sourceType || 'OSINT'} reports`;
}

function centroid(items) {
  const lat = items.reduce((sum, item) => sum + Number(item.lat), 0) / items.length;
  const lng = items.reduce((sum, item) => sum + Number(item.lng), 0) / items.length;
  return { lat, lng };
}

function maxImportance(items) {
  return Math.max(...items.map(item => Number(item.importance || 0)), 0);
}

function latestDate(items) {
  return [...items]
    .map(item => item.date || '')
    .sort((a, b) => String(b).localeCompare(String(a)))[0] || '';
}

function latestTitle(items) {
  const sorted = [...items].sort((a, b) =>
    String(b.date || '').localeCompare(String(a.date || ''))
  );
  return sorted[0]?.title || 'Untitled event';
}

function buildClusterFromItems(items) {
  const center = centroid(items);
  const sector = getSectorForPoint(center.lat, center.lng);
  const nearest = getNearestPlace(center.lat, center.lng, sector.id);

  const sourceType = items[0]?.sourceType || 'OSINT';
  const topCategory = getTopCategory(items);

  return {
    id: makeClusterKey(items[0]),
    sourceType,
    title: buildClusterTitle(items, sourceType),
    date: latestDate(items),
    lat: center.lat,
    lng: center.lng,
    sectorName: sector.name,
    sectorShortName: sector.shortName,
    nearestPlace: nearest.label,
    category: topCategory,
    importance: maxImportance(items) + Math.min(items.length, 4),
    reportCount: items.length,
    latestTitle: latestTitle(items),
    urls: items.map(item => item.url).filter(Boolean),
    items,
  };
}

export async function fetchOsintFeed() {
  const response = await fetch(OSINT_FEED_FILE, { cache: 'no-store' });

  if (!response.ok) {
    throw new Error(`OSINT feed HTTP ${response.status}`);
  }

  const json = await response.json();

  const items = Array.isArray(json.items) ? json.items : [];

  return items
    .filter(item =>
      Number.isFinite(Number(item.lat)) &&
      Number.isFinite(Number(item.lng))
    )
    .map(item => {
      const lat = Number(item.lat);
      const lng = Number(item.lng);

      const sector = getSectorForPoint(lat, lng);
      const nearest = getNearestPlace(lat, lng, sector.id);

      return {
        ...item,
        lat,
        lng,
        sectorName: item.sectorName || sector.name,
        sectorShortName: item.sectorShortName || sector.shortName,
        nearestPlace: item.nearestPlace || nearest.label,
        importance: Number(item.importance || 0),
        category: item.category || 'general military update',
      };
    })
    .sort((a, b) => {
      const impDiff = (b.importance || 0) - (a.importance || 0);
      if (impDiff !== 0) return impDiff;

      const srcDiff = sourcePriority(b.sourceType) - sourcePriority(a.sourceType);
      if (srcDiff !== 0) return srcDiff;

      return String(b.date || '').localeCompare(String(a.date || ''));
    });
}

export function clusterOsintFeed(items = []) {
  const buckets = new Map();

  items.forEach(item => {
    const key = makeClusterKey(item);
    if (!buckets.has(key)) {
      buckets.set(key, []);
    }
    buckets.get(key).push(item);
  });

  return [...buckets.values()]
    .map(bucket => buildClusterFromItems(bucket))
    .sort((a, b) => {
      const impDiff = (b.importance || 0) - (a.importance || 0);
      if (impDiff !== 0) return impDiff;

      const countDiff = (b.reportCount || 0) - (a.reportCount || 0);
      if (countDiff !== 0) return countDiff;

      return String(b.date || '').localeCompare(String(a.date || ''));
    });
}

export function summarizeOsintFeed(items = []) {
  const total = items.length;

  const isw = items.filter(i => i.sourceType === 'ISW').length;
  const official = items.filter(i => i.sourceType === 'Ukrainian official').length;
  const other = total - isw - official;

  const latest = items.slice(0, 5);

  const clusters = clusterOsintFeed(items);
  const topFive = clusters.slice(0, 5);

  return {
    total,
    isw,
    official,
    other,
    latest,
    topFive,
    clusters,
  };
}

export function buildDashboardSummary({
  currentDate,
  delta,
  firmsSummary,
  osintSummary,
}) {
  const topGain = (delta?.gained || [])[0] || null;
  const topLoss = (delta?.lost || [])[0] || null;
  const topFirms = firmsSummary?.topZone || null;
  const topOsint = (osintSummary?.topFive || [])[0] || null;

  return {
    currentDate,
    topGain,
    topLoss,
    topFirms,
    topOsint,
    osintSummary,
  };
}
