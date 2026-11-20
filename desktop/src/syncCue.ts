export const defaultSyncTrack = "1";
const defaultCue = "/assets/sound/notify_1.mp3";

export function syncCuePath(track = defaultSyncTrack) {
  return /^(?:[1-9]|10)$/.test(track) ? `/assets/sound/notify_${track}.mp3` : defaultCue;
}

/** One sync cue, followed by a two-second quiet interval. All resources are bounded. */
export function playSyncCue(
  enabled: boolean,
  volume: number,
  ready: () => void,
  createAudio = () => new Audio(defaultCue),
  fallback?: () => HTMLAudioElement,
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
  const failed = () => {
    if (cancelled || settled) return;
    if (!fallback) return finished();
    const next = fallback;
    fallback = undefined;
    release();
    start(next);
  };
  const start = (create: () => HTMLAudioElement) => {
    try {
      const player = create();
      audio = player;
      player.volume = Math.max(0, Math.min(1, volume));
      player.onended = finished;
      player.onerror = failed;
      deadline = setTimeout(finished, 15000);
      void player.play().catch(() => { if (audio === player) failed(); });
    } catch {
      failed();
    }
  };
  if (enabled && volume > 0) start(createAudio);
  else finished();
  return () => {
    cancelled = true;
    release();
    if (delay) clearTimeout(delay);
  };
}
