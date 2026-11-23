
const SHIP_ATTACKS_URL = './data/ship_attacks.json';

function cleanText(value) {
  return String(value ?? '').trim();
}

function normalizeEvent(raw) {
  if (!raw || typeof raw !== 'object') return null;

  if (
    raw.latitude === null ||
    raw.latitude === undefined ||
    raw.longitude === null ||
    raw.longitude === undefined ||
    cleanText(raw.latitude) === '' ||
    cleanText(raw.longitude) === ''
  ) {
    return null;
  }

  const lat = Number(raw.latitude);
  const lng = Number(raw.longitude);

  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng) ||
    lat < -90 ||
    lat > 90 ||
    lng < -180 ||
    lng > 180
  ) {
    return null;
  }

  const purpose = cleanText(raw.vessel_purpose);
  const fleet = cleanText(raw.fleet_classification);

  return {
    eventId: cleanText(raw.event_id),
    date: cleanText(raw.date),

    shipName: cleanText(raw.ship_name),
    shipType: cleanText(raw.ship_type),
    flag: cleanText(raw.flag),
    imo: cleanText(raw.imo),

    russianConnection: cleanText(raw.russian_connection),
    vesselPurpose: purpose,
    fleetClassification: fleet,

    location: cleanText(raw.location),
    lat,
    lng,

    strikeType: cleanText(raw.strike_type),
    attribution: cleanText(raw.attribution),
    outcome: cleanText(raw.outcome),
    confidence: cleanText(raw.confidence),

    sourceUrl: cleanText(raw.source_url),
    notes: cleanText(raw.notes),

    coordinateQuality: cleanText(raw.coordinate_quality),
    coordinateType: cleanText(raw.coordinate_type),
    coordinateIsApproximate:
      raw.coordinate_is_approximate !== false,

    sourceRow: Number(raw.source_row) || null,

    // Az árnyékflotta-státuszt csak
    // kifejezett igazolás esetén fogadjuk el.
    shadowFleetConfirmed:
      /árnyékflotta/i.test(fleet) &&
      !/nem igazolt/i.test(fleet)
  };
}

export async function fetchShipAttacks() {
  try {
    const response = await fetch(SHIP_ATTACKS_URL, {
      cache: 'no-store'
    });

    if (!response.ok) {
      throw new Error(
        `Ship attacks JSON HTTP ${response.status}`
      );
    }

    const payload = await response.json();

    const rawEvents = Array.isArray(payload)
      ? payload
      : Array.isArray(payload.events)
        ? payload.events
        : [];

    return rawEvents
      .map(normalizeEvent)
      .filter(Boolean)
      .sort((a, b) =>
        a.date.localeCompare(b.date) ||
        a.shipName.localeCompare(b.shipName)
      );

  } catch (error) {
    console.error(
      'Ship attacks could not be loaded:',
      error
    );
    return [];
  }
}

export function filterShipAttacks(
  events,
  filters = {}
) {
  const {
    startDate = null,
    endDate = null,
    vesselPurpose = '',
    fleetClassification = '',
    strikeType = '',
    confidence = '',
    approximateOnly = false
  } = filters;

  return (Array.isArray(events) ? events : [])
    .filter(event => {
      if (startDate && event.date < startDate) return false;
      if (endDate && event.date > endDate) return false;

      if (
        vesselPurpose &&
        event.vesselPurpose !== vesselPurpose
      ) return false;

      if (
        fleetClassification &&
        event.fleetClassification !== fleetClassification
      ) return false;

      if (
        strikeType &&
        event.strikeType !== strikeType
      ) return false;

      if (
        confidence &&
        event.confidence !== confidence
      ) return false;

      if (
        approximateOnly &&
        !event.coordinateIsApproximate
      ) return false;

      return true;
    });
}

export function summarizeShipAttacks(events) {
  const items = Array.isArray(events) ? events : [];

  const countBy = key => {
    const counts = {};
    for (const event of items) {
      const value = event[key] || 'Ismeretlen';
      counts[value] = (counts[value] || 0) + 1;
    }
    return counts;
  };

  const dates = items
    .map(event => event.date)
    .filter(Boolean)
    .sort();

  return {
    total: items.length,
    military: items.filter(
      event => event.vesselPurpose === 'Katonai'
    ).length,
    commercial: items.filter(
      event => event.vesselPurpose === 'Kereskedelmi'
    ).length,
    confirmedShadowFleet: items.filter(
      event => event.shadowFleetConfirmed
    ).length,
    approximateCoordinates: items.filter(
      event => event.coordinateIsApproximate
    ).length,
    byYear: items.reduce((result, event) => {
      const year = event.date.slice(0, 4);
      if (year) result[year] = (result[year] || 0) + 1;
      return result;
    }, {}),
    byPurpose: countBy('vesselPurpose'),
    byFleet: countBy('fleetClassification'),
    byAttackType: countBy('strikeType'),
    byConfidence: countBy('confidence'),
    dateStart: dates[0] || null,
    dateEnd: dates[dates.length - 1] || null
  };
}
