export function bindTimeline({ input, onChange }) {
  input.addEventListener('input', () => {
    onChange(Number(input.value));
  });
}

export function setTimelineBounds(input, max) {
  input.max = String(max);
}

export function setTimelineValue(input, value) {
  input.value = String(value);
}
