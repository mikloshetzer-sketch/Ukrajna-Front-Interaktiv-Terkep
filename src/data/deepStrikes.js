const DEEP_STRIKES_URL = './data/deep_strikes.json';


function isFiniteNumber(value) {
  return Number.isFinite(Number(value));
}


function cleanText(value) {
  return String(value ?? '').trim();
}


function normalizeDirection(value) {
  const direction = cleanText(value).toUpperCase();

  if (direction === 'UA_RU') {
    return 'UA_RU';
  }

  if (direction === 'RU_UA') {
    return 'RU_UA';
  }

  return '';
}


function normalizeEvent(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }

  const latitude = Number(raw.latitude);
  const longitude = Number(raw.longitude);

  if (
    !isFiniteNumber(latitude) ||
    !isFiniteNumber(longitude)
  ) {
    return null;
  }

  if (
    latitude < -90 ||
    latitude > 90 ||
    longitude < -180 ||
    longitude > 180
  ) {
    return null;
  }

  const direction = normalizeDirection(
    raw.direction
  );

  if (!direction) {
    return null;
  }

  return {
    eventId:
      cleanText(raw.event_id) ||
      `${cleanText(raw.date)}_${direction}_${latitude}_${longitude}`,

    date: cleanText(raw.date),

    direction,

    attacker: cleanText(raw.attacker),

    targetCountry: cleanText(
      raw.target_country
    ),

    region: cleanText(raw.region),

    location: cleanText(raw.location),

    lat: latitude,

    lng: longitude,

    strikeType: cleanText(
      raw.strike_type
    ),

    targetType: cleanText(
      raw.target_type
    ),

    description: cleanText(
      raw.description
    ),

    coordinateAccuracy: cleanText(
      raw.coordinate_accuracy
    ),

    sourceUrl: cleanText(
      raw.source_url
    ),

    sourceSheet: cleanText(
      raw.source_sheet
    ),

    sourceRow:
      Number(raw.source_row) || null,
  };
}


function extractEvents(payload) {
  if (!payload) {
    return [];
  }

  if (Array.isArray(payload)) {
    return payload;
  }

  if (Array.isArray(payload.events)) {
    return payload.events;
  }

  return [];
}


function sortEvents(events) {
  return [...events].sort(
    (a, b) => {
      const dateCompare =
        String(a.date).localeCompare(
          String(b.date)
        );

      if (dateCompare !== 0) {
        return dateCompare;
      }

      const directionCompare =
        String(a.direction).localeCompare(
          String(b.direction)
        );

      if (directionCompare !== 0) {
        return directionCompare;
      }

      return String(
        a.location
      ).localeCompare(
        String(b.location)
      );
    }
  );
}


export async function fetchDeepStrikes() {
  try {
    const response = await fetch(
      DEEP_STRIKES_URL,
      {
        cache: 'no-store',
      }
    );

    if (!response.ok) {
      throw new Error(
        `Deep strike JSON HTTP ${response.status}`
      );
    }

    const payload =
      await response.json();

    const events = extractEvents(
      payload
    )
      .map(normalizeEvent)
      .filter(Boolean);

    return sortEvents(events);

  } catch (error) {
    console.error(
      'Deep strike data could not be loaded:',
      error
    );

    return [];
  }
}


export function filterDeepStrikesByDirection(
  events,
  direction
) {
  const normalizedDirection =
    normalizeDirection(direction);

  if (!normalizedDirection) {
    return Array.isArray(events)
      ? [...events]
      : [];
  }

  return (
    Array.isArray(events)
      ? events
      : []
  ).filter(
    event =>
      event.direction ===
      normalizedDirection
  );
}


export function filterDeepStrikesByDateRange(
  events,
  startDate = null,
  endDate = null
) {
  const items = Array.isArray(events)
    ? events
    : [];

  return items.filter(
    event => {
      if (
        startDate &&
        event.date < startDate
      ) {
        return false;
      }

      if (
        endDate &&
        event.date > endDate
      ) {
        return false;
      }

      return true;
    }
  );
}


export function summarizeDeepStrikes(
  events
) {
  const items = Array.isArray(events)
    ? events
    : [];

  const uaRu = items.filter(
    event =>
      event.direction === 'UA_RU'
  );

  const ruUa = items.filter(
    event =>
      event.direction === 'RU_UA'
  );

  const dates = items
    .map(event => event.date)
    .filter(Boolean)
    .sort();

  return {
    total: items.length,

    uaToRussia: uaRu.length,

    russiaToUkraine: ruUa.length,

    dateStart:
      dates.length
        ? dates[0]
        : null,

    dateEnd:
      dates.length
        ? dates[dates.length - 1]
        : null,
  };
}
