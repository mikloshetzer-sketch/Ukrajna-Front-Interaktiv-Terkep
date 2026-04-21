export function createPlayer({ onTick, getMaxIndex, getCurrentIndex, setCurrentIndex }) {
  let timer = null;

  function play(speedMs) {
    stop();
    timer = window.setInterval(() => {
      const current = getCurrentIndex();
      const max = getMaxIndex();
      if (current >= max) {
        stop();
        return;
      }
      const next = current + 1;
      setCurrentIndex(next);
      onTick(next);
    }, speedMs);
  }

  function stop() {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  return { play, stop };
}
