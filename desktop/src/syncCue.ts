/** One sync cue, followed by a two-second quiet interval. All resources are bounded. */
export function playSyncCue(
  enabled: boolean,
  volume: number,
  ready: () => void,
  createAudio = () => new Audio("/assets/sound/notify.mp3"),
) {
  let audio: HTMLAudioElement | null = null;
  let cancelled = false,
    settled = false;
  let deadline: ReturnType<typeof setTimeout> | undefined;
  let delay: ReturnType<typeof setTimeout> | undefined;
  const release = () => {
    if (deadline) clearTimeout(deadline);
    if (audio) {
      audio.onended = audio.onerror = null;
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      audio = null;
    }
  };
  const finished = () => {
    if (cancelled || settled) return;
    settled = true;
    release();
    delay = setTimeout(() => {
      if (!cancelled) ready();
    }, 2000);
  };
  if (enabled && volume > 0) {
    try {
      audio = createAudio();
      audio.volume = Math.max(0, Math.min(1, volume));
      audio.onended = finished;
      audio.onerror = finished;
      deadline = setTimeout(finished, 15000);
      void audio.play().catch(finished);
    } catch {
      finished();
    }
  } else finished();
  return () => {
    cancelled = true;
    release();
    if (delay) clearTimeout(delay);
  };
}
