export function createPlayer({ onTick, getMaxIndex, getCurrentIndex, setCurrentIndex }) {
  let timer = null;

  return {
    play(speedMs) {
      if (timer) clearInterval(timer);

      timer = setInterval(async () => {
        const max = getMaxIndex();
        let current = getCurrentIndex();

        if (current >= max) {
          clearInterval(timer);
          timer = null;
          return;
        }

        current += 1;
        setCurrentIndex(current);
        await onTick(current);
      }, speedMs);
    },

    stop() {
      if (timer) clearInterval(timer);
      timer = null;
    }
  };
}
