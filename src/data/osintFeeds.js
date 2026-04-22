import { getSectorForPoint, getNearestPlace } from './placeLookup.js';

const OSINT_FEED_FILE = './data/osint_feed.json';

export async function fetchOsintFeed() {
  const response = await fetch(OSINT_FEED_FILE, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`OSINT feed HTTP ${response.status}`);
  }

  const json = await response.json();
  const items = Array.isArray(json.items) ? json.items : [];

  return items
    .filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lng)))
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
      };
    })
    .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
}

export function summarizeOsintFeed(items = []) {
  const total = items.length;
  const isw = items.filter(i => i.sourceType === 'ISW').length;
  const official = items.filter(i => i.sourceType === 'Ukrainian official').length;
  const other = total - isw - official;

  const latest = items.slice(0, 5);

  return {
    total,
    isw,
    official,
    other,
    latest,
  };
}

export function buildDashboardSummary({ currentDate, delta, firmsSummary, osintSummary }) {
  const topGain = (delta?.gained || [])[0] || null;
  const topLoss = (delta?.lost || [])[0] || null;
  const topFirms = firmsSummary?.topZone || null;

  return {
    currentDate,
    topGain,
    topLoss,
    topFirms,
    osintSummary,
  };
}
