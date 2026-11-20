let releaseCurrent: (() => void) | undefined;

export function playErrorCue(
  enabled = true,
  volume = 0.6,
  createAudio = () => new Audio("/assets/sound/error.mp3"),
) {
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

export function stopErrorCue() {
  releaseCurrent?.();
}
