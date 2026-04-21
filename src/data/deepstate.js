import { extractDateFromFilename } from '../utils/date.js';

const API_URL = 'https://api.github.com/repos/cyterat/deepstate-map-data/contents/data';
const RAW_BASE = 'https://cdn.jsdelivr.net/gh/cyterat/deepstate-map-data@main/data/';
const MIN_DATE = '2024-01-01';

export async function fetchDeepStateIndex() {
  const response = await fetch(API_URL);
  if (!response.ok) throw new Error(`DeepState index hiba: ${response.status}`);
  const items = await response.json();

  return items
    .filter(item => /^deepstatemap_data_\d{8}\.geojson$/i.test(item.name))
    .map(item => ({ ...item, date: extractDateFromFilename(item.name) }))
    .filter(item => item.date && item.date >= MIN_DATE)
    .sort((a, b) => a.date.localeCompare(b.date));
}

export async function fetchDeepStateByFilename(filename) {
  const response = await fetch(`${RAW_BASE}${filename}`);
  if (!response.ok) throw new Error(`DeepState napi fájl hiba: ${response.status}`);
  return response.json();
}
