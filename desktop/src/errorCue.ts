function soundCue(path: string) {
  let releaseCurrent: (() => void) | undefined;

  function play(enabled = true, volume = 0.6, createAudio = () => new Audio(path)) {
    if (!enabled || !(volume > 0) || releaseCurrent) return;
    try {
      const audio = createAudio();
      const release = () => {
        if (releaseCurrent !== release) return;
        releaseCurrent = undefined;
        clearTimeout(timeout);
        audio.onended = audio.onerror = null;
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
      };
      const timeout = setTimeout(release, 15000);
      releaseCurrent = release;
      audio.volume = Math.min(volume, 1);
      audio.onended = audio.onerror = release;
      void audio.play().catch(release);
    } catch {
      releaseCurrent?.();
    }
  }
  return { play, stop: () => releaseCurrent?.() };
}

export const { play: playErrorCue, stop: stopErrorCue } = soundCue("/assets/sound/error.mp3");
export const { play: playLogonCue } = soundCue("/assets/sound/logon.mp3");
