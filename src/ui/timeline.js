export function bindTimeline({ input, onChange }) {
  input.addEventListener('input', () => onChange(Number(input.value)));
}

export function setTimelineBounds(input, max) {
  input.min = '0';
  input.max = String(Math.max(0, max));
  input.value = String(Math.max(0, max));
}

export function setTimelineValue(input, value) {
  input.value = String(value);
}
