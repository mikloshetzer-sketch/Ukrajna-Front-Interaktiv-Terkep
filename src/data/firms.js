export async function fetchFirmsLayer(windowDays = 3) {
  const samples = [
    { lat: 47.10, lng: 37.55, date: 'minta', confidence: 'proxy', windowDays },
    { lat: 48.52, lng: 39.28, date: 'minta', confidence: 'proxy', windowDays },
    { lat: 46.63, lng: 32.61, date: 'minta', confidence: 'proxy', windowDays },
  ];
  return samples;
}
