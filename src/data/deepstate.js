const apiUrl = 'https://api.github.com/repos/cyterat/deepstate-map-data/contents/data';
const rawBase = 'https://cdn.jsdelivr.net/gh/cyterat/deepstate-map-data@main/data/';

function parseDate(name) {
  const m = name.match(/(\d{4})(\d{2})(\d{2})/);
  if (!m) return null;
  return `${m[1]}-${m[2]}-${m[3]}`;
}

export async function fetchDeepStateIndex() {
  const res = await fetch(apiUrl);
  if (!res.ok) throw new Error(`DeepState index HTTP ${res.status}`);
  const items = await res.json();

  return items
    .filter(item => /^deepstatemap_data_\d{8}\.geojson$/i.test(item.name))
    .map(item => ({ name: item.name, date: parseDate(item.name) }))
    .filter(item => item.date && item.date >= '2024-01-01')
    .sort((a, b) => a.date.localeCompare(b.date));
}

export async function fetchDeepStateByFilename(filename) {
  const res = await fetch(rawBase + filename);
  if (!res.ok) throw new Error(`DeepState daily HTTP ${res.status}`);
  return res.json();
}
