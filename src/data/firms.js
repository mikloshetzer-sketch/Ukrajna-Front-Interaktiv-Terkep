const FIRMS_FILES = {
  3: './data/firms_3.json',
  10: './data/firms_10.json',
  30: './data/firms_30.json',
};

export async function fetchFirmsLayer(windowDays = 3) {
  const file = FIRMS_FILES[windowDays] || FIRMS_FILES[3];

  const response = await fetch(file, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`FIRMS local file HTTP ${response.status}`);
  }

  const json = await response.json();

  return (json.points || []).map((item) => ({
    lat: Number(item.lat),
    lng: Number(item.lng),
    acq_date: item.acq_date || '',
    acq_time: item.acq_time || '',
    confidence: item.confidence ?? '',
    frp: item.frp ?? '',
    source: item.source || '',
    satellite: item.satellite || '',
    daynight: item.daynight || '',
    brightness: item.brightness ?? '',
    windowDays,
  }));
}
