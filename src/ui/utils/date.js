export function formatDateLabel(dateString) {
  return dateString ?? '–';
}

export function extractDateFromFilename(filename) {
  const match = String(filename).match(/(\d{4})(\d{2})(\d{2})/);
  if (!match) return null;
  return `${match[1]}-${match[2]}-${match[3]}`;
}

export function addDays(dateString, amount) {
  const date = new Date(`${dateString}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
