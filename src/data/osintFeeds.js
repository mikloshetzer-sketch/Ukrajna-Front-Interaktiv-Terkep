const OSINT_FEED_CANDIDATES = [
  './data/osint_feed.json',
  './data/osint/osint.json',
  './data/osint/latest.json',
  './data/osint/feed.json',
  './data/osint/items.json',
  './data/osint/combined.json',
  './data/osint/latest_osint.json',
  './data/osint.json',
];

const MS_IN_HOUR = 60 * 60 * 1000;

function isFiniteNumber(value) {
  return Number.isFinite(Number(value));
}

function safeDate(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatDateYmd(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return null;
  return date.toISOString().slice(0, 10);
}

function normalizeText(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function normalizeSourceType(raw) {
  const source = String(
    raw?.sourceType ||
    raw?.source_type ||
    raw?.source ||
    raw?.feed ||
    raw?.publisher ||
    raw?.origin ||
    ''
  ).trim();

  const lower = source.toLowerCase();

  if (lower.includes('isw')) return 'ISW';
  if (lower.includes('critical threats')) return 'Critical Threats';
  if (
    lower.includes('ukrainian') ||
    lower.includes('general staff') ||
    lower.includes('mod ukraine') ||
    lower.includes('sbu')
  ) {
    return 'Ukrainian official';
  }
  if (lower.includes('deepstate')) return 'DeepState';
  if (lower.includes('geoconfirmed')) return 'GeoConfirmed';
  if (lower.includes('defmon')) return 'DefMon';
  if (lower.includes('rybar')) return 'Rybar';
  if (lower.includes('wargonzo')) return 'WarGonzo';
  if (lower.includes('russian mod')) return 'Russian MOD';

  return source || 'OSINT';
}

function inferCategory(text) {
  const t = normalizeText(text);

  if (!t) return 'general military update';
  if (t.includes('drone')) return 'drone strike';
  if (t.includes('missile') || t.includes('storm shadow') || t.includes('iskander')) return 'missile strike';
  if (t.includes('air defense') || t.includes('sam') || t.includes('radar')) return 'air defense';
  if (t.includes('artillery') || t.includes('shelling')) return 'artillery';
  if (t.includes('assault') || t.includes('offensive') || t.includes('advance') || t.includes('pushed') || t.includes('attack')) return 'assault';
  if (t.includes('logistics') || t.includes('rail') || t.includes('ammo') || t.includes('depot')) return 'logistics';
  if (t.includes('naval') || t.includes('frigate') || t.includes('fleet') || t.includes('port')) return 'naval';
  if (t.includes('aviation') || t.includes('airbase') || t.includes('air field') || t.includes('airfield') || t.includes('air strike')) return 'aviation';
  if (t.includes('electronic warfare') || t.includes('ew')) return 'electronic warfare';

  return 'general military update';
}

function inferTargetCategory(text) {
  const t = normalizeText(text);

  if (!t) return 'unknown target';
  if (t.includes('refinery') || t.includes('oil') || t.includes('fuel') || t.includes('terminal') || t.includes('pipeline') || t.includes('depot')) {
    return 'oil / energy infrastructure';
  }
  if (t.includes('port') || t.includes('seaport') || t.includes('harbor') || t.includes('naval')) {
    return 'port / naval infrastructure';
  }
  if (t.includes('airbase') || t.includes('air field') || t.includes('airfield') || t.includes('air defense') || t.includes('radar') || t.includes('frigate')) {
    return 'military asset';
  }
  if (t.includes('rail') || t.includes('bridge') || t.includes('logistics')) {
    return 'logistics infrastructure';
  }
  if (t.includes('factory') || t.includes('plant') || t.includes('industrial')) {
    return 'industrial target';
  }

  return 'unknown target';
}

function inferNearestPlace(raw) {
  return (
    raw?.nearestPlace ||
    raw?.nearest_place ||
    raw?.place ||
    raw?.location ||
    raw?.city ||
    raw?.near ||
    raw?.settlement ||
    raw?.name ||
    'Unknown place'
  );
}

function inferSectorName(raw) {
  return (
    raw?.sectorName ||
    raw?.sector_name ||
    raw?.sector ||
    raw?.frontSector ||
    raw?.front_sector ||
    raw?.oblast ||
    'Unknown sector'
  );
}

function extractLatLng(raw) {
  const directLat = raw?.lat ?? raw?.latitude;
  const directLng = raw?.lng ?? raw?.lon ?? raw?.longitude;

  if (isFiniteNumber(directLat) && isFiniteNumber(directLng)) {
    return { lat: Number(directLat), lng: Number(directLng) };
  }

  if (Array.isArray(raw?.coordinates) && raw.coordinates.length >= 2) {
    const [lng, lat] = raw.coordinates;
    if (isFiniteNumber(lat) && isFiniteNumber(lng)) {
      return { lat: Number(lat), lng: Number(lng) };
    }
  }

  if (raw?.geometry?.type === 'Point' && Array.isArray(raw?.geometry?.coordinates)) {
    const [lng, lat] = raw.geometry.coordinates;
    if (isFiniteNumber(lat) && isFiniteNumber(lng)) {
      return { lat: Number(lat), lng: Number(lng) };
    }
  }

  return { lat: null, lng: null };
}

function extractDate(raw) {
  return (
    raw?.date ||
    raw?.pubDate ||
    raw?.published ||
    raw?.publishedAt ||
    raw?.datetime ||
    raw?.timestamp ||
    raw?.created_at ||
    raw?.createdAt ||
    null
  );
}

function extractUrl(raw) {
  return raw?.url || raw?.link || raw?.sourceUrl || raw?.source_url || null;
}

function extractTitle(raw) {
  return (
    raw?.title ||
    raw?.headline ||
    raw?.name ||
    raw?.summary_title ||
    raw?.text ||
    'Untitled'
  );
}

function extractSummary(raw) {
  return raw?.summary || raw?.description || raw?.snippet || raw?.content || '';
}

function toItemsArray(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.entries)) return payload.entries;
  if (Array.isArray(payload?.results)) return payload.results;
  if (payload?.type === 'FeatureCollection' && Array.isArray(payload?.features)) {
    return payload.features.map(feature => ({
      ...(feature.properties || {}),
      geometry: feature.geometry,
    }));
  }
  return [];
}

async function fetchFirstAvailableJson() {
  let lastError = null;

  for (const url of OSINT_FEED_CANDIDATES) {
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) {
        lastError = new Error(`HTTP ${response.status} – ${url}`);
        continue;
      }

      const json = await response.json();
      return {
        ok: true,
        json,
        url,
      };
    } catch (error) {
      lastError = error;
    }
  }

  return {
    ok: false,
    json: null,
    url: null,
    error: lastError || new Error('No OSINT feed source could be loaded.'),
  };
}

function normalizeOsintItem(raw, sourceUrl) {
  const { lat, lng } = extractLatLng(raw);
  const parsedDate = safeDate(extractDate(raw));
  const title = extractTitle(raw);
  const summary = extractSummary(raw);
  const combinedText = `${title} ${summary} ${raw?.category || ''} ${raw?.target || ''}`;

  return {
    id: raw?.id || raw?.guid || raw?.uuid || `${normalizeText(title)}_${formatDateYmd(parsedDate) || 'nodate'}`,
    lat,
    lng,
    date: formatDateYmd(parsedDate) || 'Unknown',
    rawDate: parsedDate,
    title,
    latestTitle: title,
    summary,
    url: extractUrl(raw),
    urls: extractUrl(raw) ? [extractUrl(raw)] : [],
    sourceType: normalizeSourceType(raw),
    sectorName: inferSectorName(raw),
    sectorShortName: raw?.sectorShortName || raw?.sector_short_name || inferSectorName(raw),
    nearestPlace: inferNearestPlace(raw),
    category: raw?.category || inferCategory(combinedText),
    targetCategory: raw?.targetCategory || raw?.target_category || inferTargetCategory(combinedText),
    importance: Number(raw?.importance || 0),
    sourceUrl,
    reportCount: Number(raw?.reportCount || 1),
  };
}

function computeFreshness(item, now) {
  if (!(item.rawDate instanceof Date)) {
    return {
      freshnessHours: 9999,
      freshnessLabel: 'UNKNOWN',
    };
  }

  const diffMs = now.getTime() - item.rawDate.getTime();
  const hours = Math.max(0, diffMs / MS_IN_HOUR);

  let freshnessLabel = 'ARCHIVE';
  if (hours <= 12) freshnessLabel = 'HOT';
  else if (hours <= 24) freshnessLabel = 'ACTIVE';
  else if (hours <= 48) freshnessLabel = 'RECENT';
  else if (hours <= 72) freshnessLabel = 'AGING';

  return {
    freshnessHours: hours,
    freshnessLabel,
  };
}

function dedupeItems(items) {
  const byKey = new Map();

  items.forEach(item => {
    const key = [
      normalizeText(item.title).slice(0, 110),
      normalizeText(item.nearestPlace),
      normalizeText(item.category),
      item.date,
      normalizeText(item.sourceType),
    ].join('|');

    const existing = byKey.get(key);
    if (!existing) {
      byKey.set(key, item);
      return;
    }

    const existingTime = existing.rawDate?.getTime?.() || 0;
    const currentTime = item.rawDate?.getTime?.() || 0;

    if (currentTime > existingTime) {
      byKey.set(key, item);
    }
  });

  return [...byKey.values()];
}

function haversineKm(aLat, aLng, bLat, bLng) {
  const toRad = deg => (deg * Math.PI) / 180;
  const R = 6371;
  const dLat = toRad(bLat - aLat);
  const dLng = toRad(bLng - aLng);
  const lat1 = toRad(aLat);
  const lat2 = toRad(bLat);

  const s1 = Math.sin(dLat / 2);
  const s2 = Math.sin(dLng / 2);

  const h = s1 * s1 + Math.cos(lat1) * Math.cos(lat2) * s2 * s2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function categoryFamily(category) {
  const c = normalizeText(category);
  if (c.includes('drone')) return 'drone';
  if (c.includes('missile')) return 'missile';
  if (c.includes('assault')) return 'assault';
  if (c.includes('artillery')) return 'artillery';
  if (c.includes('logistics')) return 'logistics';
  if (c.includes('naval')) return 'naval';
  if (c.includes('aviation')) return 'aviation';
  if (c.includes('air defense')) return 'air-defense';
  return 'general';
}

function clusterImportance(cluster) {
  const sourceBoost = (() => {
    const s = cluster.sourceType;
    if (s === 'Ukrainian official') return 2.2;
    if (s === 'ISW') return 1.5;
    if (s === 'Critical Threats') return 1.4;
    if (s === 'GeoConfirmed') return 1.7;
    if (s === 'DeepState') return 1.4;
    return 0.9;
  })();

  const recencyBoost =
    cluster.freshnessHours <= 12 ? 3 :
    cluster.freshnessHours <= 24 ? 2.4 :
    cluster.freshnessHours <= 36 ? 1.8 :
    cluster.freshnessHours <= 48 ? 1.1 :
    0.6;

  const reportsBoost = Math.min(cluster.reportCount, 4) * 0.9;

  const categoryBoost = (() => {
    const fam = categoryFamily(cluster.category);
    if (fam === 'assault') return 2.2;
    if (fam === 'missile') return 2.1;
    if (fam === 'drone') return 1.8;
    if (fam === 'artillery') return 1.5;
    return 1.0;
  })();

  return sourceBoost + recencyBoost + reportsBoost + categoryBoost;
}

function clusterItems(items, options = {}) {
  const maxDistanceKm = Number(options.maxDistanceKm || 35);
  const maxTimeHours = Number(options.maxTimeHours || 30);

  const sorted = [...items].sort((a, b) => {
    const bt = b.rawDate?.getTime?.() || 0;
    const at = a.rawDate?.getTime?.() || 0;
    return bt - at;
  });

  const clusters = [];

  sorted.forEach(item => {
    if (!isFiniteNumber(item.lat) || !isFiniteNumber(item.lng)) return;

    let bestCluster = null;
    let bestDistance = Infinity;

    for (const cluster of clusters) {
      const sameFamily = categoryFamily(cluster.category) === categoryFamily(item.category);
      if (!sameFamily) continue;

      const timeDiffHours = Math.abs(
        ((cluster.rawDate?.getTime?.() || 0) - (item.rawDate?.getTime?.() || 0)) / MS_IN_HOUR
      );
      if (timeDiffHours > maxTimeHours) continue;

      const distanceKm = haversineKm(cluster.lat, cluster.lng, item.lat, item.lng);
      if (distanceKm > maxDistanceKm) continue;

      if (distanceKm < bestDistance) {
        bestDistance = distanceKm;
        bestCluster = cluster;
      }
    }

    if (!bestCluster) {
      clusters.push({
        ...item,
        items: [item],
        urls: item.url ? [item.url] : [],
        reportCount: 1,
      });
      return;
    }

    bestCluster.items.push(item);
    bestCluster.reportCount += 1;

    if (item.url && !bestCluster.urls.includes(item.url)) {
      bestCluster.urls.push(item.url);
    }

    const latestTime = bestCluster.rawDate?.getTime?.() || 0;
    const itemTime = item.rawDate?.getTime?.() || 0;
    if (itemTime > latestTime) {
      bestCluster.latestTitle = item.title;
      bestCluster.rawDate = item.rawDate;
      bestCluster.date = item.date;
      bestCluster.freshnessHours = item.freshnessHours;
      bestCluster.freshnessLabel = item.freshnessLabel;
    }

    const avgLat =
      bestCluster.items.reduce((sum, it) => sum + Number(it.lat), 0) / bestCluster.items.length;
    const avgLng =
      bestCluster.items.reduce((sum, it) => sum + Number(it.lng), 0) / bestCluster.items.length;

    bestCluster.lat = avgLat;
    bestCluster.lng = avgLng;

    if (item.sourceType === 'Ukrainian official') {
      bestCluster.sourceType = 'Ukrainian official';
    } else if (item.sourceType === 'ISW' && bestCluster.sourceType !== 'Ukrainian official') {
      bestCluster.sourceType = 'ISW';
    }

    if ((item.importance || 0) > (bestCluster.importance || 0)) {
      bestCluster.importance = item.importance;
      bestCluster.title = item.title;
      bestCluster.nearestPlace = item.nearestPlace;
      bestCluster.sectorName = item.sectorName;
      bestCluster.sectorShortName = item.sectorShortName;
      bestCluster.category = item.category;
      bestCluster.targetCategory = item.targetCategory;
    }
  });

  return clusters.map(cluster => ({
    ...cluster,
    importance: clusterImportance(cluster),
  }));
}

function filterByFreshness(items, now, maxAgeHours, fallbackAgeHours) {
  const enriched = items.map(item => ({
    ...item,
    ...computeFreshness(item, now),
  }));

  const withinFreshWindow = enriched.filter(item => item.freshnessHours <= maxAgeHours);

  if (withinFreshWindow.length) {
    return {
      items: withinFreshWindow,
      mode: 'fresh',
      referenceDate: formatDateYmd(now),
      maxAgeHours,
    };
  }

  const withinFallback = enriched.filter(item => item.freshnessHours <= fallbackAgeHours);
  if (!withinFallback.length) {
    return {
      items: [],
      mode: 'empty',
      referenceDate: null,
      maxAgeHours,
    };
  }

  const latestTime = Math.max(...withinFallback.map(item => item.rawDate?.getTime?.() || 0));
  const latestDate = new Date(latestTime);
  const latestYmd = formatDateYmd(latestDate);

  return {
    items: withinFallback.filter(item => item.date === latestYmd),
    mode: 'fallback',
    referenceDate: latestYmd,
    maxAgeHours,
  };
}

export async function fetchOsintFeed(options = {}) {
  const now = options.now instanceof Date ? options.now : new Date();
  const maxAgeHours = Number(options.maxAgeHours || 36);
  const fallbackAgeHours = Number(options.fallbackAgeHours || 96);

  const result = await fetchFirstAvailableJson();
  if (!result.ok) return [];

  const rawItems = toItemsArray(result.json);

  const normalized = rawItems
    .map(item => normalizeOsintItem(item, result.url))
    .filter(item => isFiniteNumber(item.lat) && isFiniteNumber(item.lng));

  const deduped = dedupeItems(normalized);
  const filtered = filterByFreshness(deduped, now, maxAgeHours, fallbackAgeHours);

  return filtered.items
    .sort((a, b) => {
      const bt = b.rawDate?.getTime?.() || 0;
      const at = a.rawDate?.getTime?.() || 0;
      return bt - at;
    })
    .map(item => ({
      ...item,
      freshnessMode: filtered.mode,
      referenceDate: filtered.referenceDate,
      freshnessWindowHours: filtered.maxAgeHours,
    }));
}

export function summarizeOsintFeed(items) {
  const validItems = Array.isArray(items) ? items : [];
  const clusters = clusterItems(validItems, {
    maxDistanceKm: 35,
    maxTimeHours: 30,
  }).sort((a, b) => {
    const diff = (b.importance || 0) - (a.importance || 0);
    if (diff !== 0) return diff;
    return (b.rawDate?.getTime?.() || 0) - (a.rawDate?.getTime?.() || 0);
  });

  const topFive = clusters.slice(0, 5);

  const countBySource = sourceName =>
    validItems.filter(item => item.sourceType === sourceName).length;

  const mode = validItems[0]?.freshnessMode || 'empty';
  const referenceDate = validItems[0]?.referenceDate || null;
  const freshnessWindowHours = validItems[0]?.freshnessWindowHours || 36;

  return {
    total: validItems.length,
    clusters,
    topFive,
    isw: countBySource('ISW'),
    official: countBySource('Ukrainian official'),
    other: validItems.filter(item => !['ISW', 'Ukrainian official'].includes(item.sourceType)).length,
    mode,
    referenceDate,
    freshnessWindowHours,
  };
}

export function buildDashboardSummary({ currentDate, delta, firmsSummary, osintSummary }) {
  const topGain = (delta?.gained || [])
    .slice()
    .sort((a, b) => Number(b.areaKm2 || 0) - Number(a.areaKm2 || 0))[0] || null;

  const topLoss = (delta?.lost || [])
    .slice()
    .sort((a, b) => Number(b.areaKm2 || 0) - Number(a.areaKm2 || 0))[0] || null;

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
