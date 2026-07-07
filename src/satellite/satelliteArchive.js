const DEFAULT_LATEST_URL = './docs/data/satellite/sentinel2/latest.json';
const DEFAULT_INDEX_URL = './docs/data/satellite/sentinel2/index.json';

function normalizeAssetPath(path) {
  if (!path) return null;

  const value = String(path);

  if (value.startsWith('http://') || value.startsWith('https://')) {
    return value;
  }

  if (value.startsWith('./')) {
    return value;
  }

  if (value.startsWith('/')) {
    return value;
  }

  if (value.startsWith('data/satellite/')) {
    return `./docs/${value}`;
  }

  if (value.startsWith('docs/data/satellite/')) {
    return `./${value}`;
  }

  return value;
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: 'no-store' });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} – ${url}`);
  }

  return response.json();
}

function normalizeRecord(record) {
  if (!record || typeof record !== 'object') return null;

  const locationName = record.location_name || 'Unknown location';
  const locationSlug = record.location_slug || locationName;

  const historyImage =
    record.imagery?.history_image ||
    record.history_image ||
    null;

  const latestImage =
    record.imagery?.latest_image ||
    record.latest_image ||
    null;

  const bounds =
    record.imagery?.bounds ||
    record.target_area?.bounds ||
    null;

  const bbox =
    record.target_area?.bbox ||
    (bounds
      ? [bounds.west, bounds.south, bounds.east, bounds.north]
      : null);

  return {
    ...record,
    location_name: locationName,
    location_slug: locationSlug,
    satellite_image: normalizeAssetPath(historyImage || latestImage),
    bbox,
    bounds: bounds || (
      Array.isArray(bbox) && bbox.length === 4
        ? {
            west: bbox[0],
            south: bbox[1],
            east: bbox[2],
            north: bbox[3],
          }
        : null
    ),
  };
}

export class SatelliteArchive {
  constructor(options = {}) {
    this.latestUrl = options.latestUrl || DEFAULT_LATEST_URL;
    this.indexUrl = options.indexUrl || DEFAULT_INDEX_URL;

    this.latest = null;
    this.records = [];
    this.loaded = false;
    this.error = null;
  }

  async load() {
    this.error = null;

    try {
      const [latestRaw, indexRaw] = await Promise.allSettled([
        fetchJson(this.latestUrl),
        fetchJson(this.indexUrl),
      ]);

      if (latestRaw.status === 'fulfilled') {
        this.latest = normalizeRecord(latestRaw.value);
      }

      if (indexRaw.status === 'fulfilled' && Array.isArray(indexRaw.value)) {
        this.records = indexRaw.value
          .map(normalizeRecord)
          .filter(Boolean);
      }

      if (!this.records.length && this.latest) {
        this.records = [this.latest];
      }

      this.records = this.records
        .filter(record => record.satellite_image && record.bounds)
        .sort((a, b) => String(b.generated_at || '').localeCompare(String(a.generated_at || '')));

      if (!this.latest && this.records.length) {
        this.latest = this.records[0];
      }

      this.loaded = true;
      return this;
    } catch (error) {
      this.error = error;
      this.loaded = false;
      throw error;
    }
  }

  isAvailable() {
    return this.loaded && this.records.length > 0;
  }

  getLatest() {
    return this.latest || this.records[0] || null;
  }

  getRecords() {
    return [...this.records];
  }

  getLocations() {
    const map = new Map();

    this.records.forEach(record => {
      const slug = record.location_slug;
      if (!map.has(slug)) {
        map.set(slug, {
          slug,
          name: record.location_name,
          count: 0,
          latest: record,
        });
      }

      const item = map.get(slug);
      item.count += 1;

      if (String(record.generated_at || '') > String(item.latest?.generated_at || '')) {
        item.latest = record;
      }
    });

    return [...map.values()]
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  getRecordsByLocation(locationSlug) {
    return this.records
      .filter(record => record.location_slug === locationSlug)
      .sort((a, b) => String(b.generated_at || '').localeCompare(String(a.generated_at || '')));
  }

  getRecordById(recordId) {
    return this.records.find(record => record.id === recordId) || null;
  }

  getDefaultRecord() {
    return this.getLatest();
  }
}

export function formatSatelliteRecordLabel(record) {
  if (!record) return 'Nincs elérhető kép';

  const date =
    record.timestamp ||
    record.generated_at ||
    record.imagery?.requested_time_range?.to ||
    'ismeretlen dátum';

  return `${record.location_name} – ${date}`;
}
