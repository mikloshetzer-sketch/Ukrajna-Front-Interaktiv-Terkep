function boundsFromRecord(record) {
  const bounds = record?.bounds || record?.imagery?.bounds || null;

  if (bounds) {
    return [
      [Number(bounds.south), Number(bounds.west)],
      [Number(bounds.north), Number(bounds.east)],
    ];
  }

  const bbox = record?.bbox || record?.target_area?.bbox || null;

  if (Array.isArray(bbox) && bbox.length === 4) {
    return [
      [Number(bbox[1]), Number(bbox[0])],
      [Number(bbox[3]), Number(bbox[2])],
    ];
  }

  return null;
}

function imageUrlFromRecord(record) {
  return record?.satellite_image || record?.imagery?.history_image || record?.imagery?.latest_image || null;
}

export class SatelliteImageLayer {
  constructor(map, options = {}) {
    this.map = map;
    this.layer = null;
    this.currentRecord = null;
    this.opacity = Number(options.opacity ?? 0.72);
    this.fitOnLoad = Boolean(options.fitOnLoad ?? false);
  }

  setOpacity(opacity) {
    this.opacity = Math.max(0, Math.min(1, Number(opacity)));

    if (this.layer) {
      this.layer.setOpacity(this.opacity);
    }
  }

  getOpacity() {
    return this.opacity;
  }

  isVisible() {
    return Boolean(this.layer && this.map.hasLayer(this.layer));
  }

  clear() {
    if (this.layer) {
      this.map.removeLayer(this.layer);
      this.layer = null;
    }

    this.currentRecord = null;
  }

  show(record, options = {}) {
    const imageUrl = imageUrlFromRecord(record);
    const bounds = boundsFromRecord(record);

    if (!imageUrl) {
      throw new Error('A Sentinel-2 rekord nem tartalmaz megjeleníthető képet.');
    }

    if (!bounds) {
      throw new Error('A Sentinel-2 rekord nem tartalmaz térképi bounds adatot.');
    }

    this.clear();

    this.currentRecord = record;
    this.layer = L.imageOverlay(imageUrl, bounds, {
      opacity: Number(options.opacity ?? this.opacity),
      interactive: true,
      attribution: 'Sentinel-2 / Copernicus Data Space / Sentinel Hub',
      className: 'sentinel2-image-overlay',
    });

    this.layer.addTo(this.map);

    if (options.fitBounds ?? this.fitOnLoad) {
      this.map.fitBounds(bounds, {
        padding: [24, 24],
        maxZoom: 13,
      });
    }

    return this.layer;
  }

  hide() {
    if (this.layer && this.map.hasLayer(this.layer)) {
      this.map.removeLayer(this.layer);
    }
  }

  restore() {
    if (this.layer && !this.map.hasLayer(this.layer)) {
      this.layer.addTo(this.map);
    }
  }

  toggle(record, visible, options = {}) {
    if (visible) {
      if (record && record !== this.currentRecord) {
        return this.show(record, options);
      }

      if (this.layer) {
        this.restore();
        return this.layer;
      }

      if (record) {
        return this.show(record, options);
      }

      return null;
    }

    this.hide();
    return null;
  }

  getCurrentRecord() {
    return this.currentRecord;
  }
}

export function formatSatelliteBounds(record) {
  const bounds = boundsFromRecord(record);

  if (!bounds) return 'nincs bounds adat';

  const south = bounds[0][0].toFixed(5);
  const west = bounds[0][1].toFixed(5);
  const north = bounds[1][0].toFixed(5);
  const east = bounds[1][1].toFixed(5);

  return `S:${south}, W:${west}, N:${north}, E:${east}`;
}
