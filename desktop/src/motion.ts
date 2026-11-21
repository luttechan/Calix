const preferenceKey = "calix.reduce-motion";

function applyPreference(reduced: boolean) {
  document.documentElement.toggleAttribute("data-reduce-motion", reduced);
}

export function restoreMotionPreference() {
  try {
    applyPreference(localStorage.getItem(preferenceKey) === "true");
  } catch {
    // The engine preference is applied after bootstrap when storage is unavailable.
  }
}

export function saveMotionPreference(reduced: boolean) {
  applyPreference(reduced);
  try {
    if (reduced) localStorage.setItem(preferenceKey, "true");
    else localStorage.removeItem(preferenceKey);
  } catch {
    // The engine remains the source of truth.
  }
}

export function motionReduced() {
  return document.documentElement.hasAttribute("data-reduce-motion") ||
    matchMedia("(prefers-reduced-motion: reduce)").matches;
}

const arrive = "cubic-bezier(.18, 1, .28, 1)";

export function animatePage(container: HTMLElement, direction: number) {
  if (motionReduced()) return;
  const surfaces = Array.from(container.children).flatMap(element =>
    element.classList.contains("stats") || element.classList.contains("home-content")
      ? Array.from(element.children)
      : [element],
  ).filter(element => element.tagName !== "DIALOG" && element.getClientRects().length > 0);

  const animations = surfaces.slice(0, 8).map((element, index) =>
    element.animate(
      [
        { opacity: 0.16, transform: `translate(${direction * 26}px, 15px) scale(.983)` },
        { opacity: 1, transform: "none" },
      ],
      { duration: 365, delay: Math.min(index * 36, 144), easing: arrive, fill: "backwards" },
    ),
  );
  return () => animations.forEach(animation => animation.cancel());
}

export function animateCalendarMonth(grid: HTMLElement, direction: number) {
  if (motionReduced()) return;
  const animation = grid.animate(
    [
      { opacity: .3, transform: `translateX(${direction * 24}px)` },
      { opacity: 1, transform: "none" },
    ],
    { duration: 315, easing: arrive },
  );
  return () => animation.cancel();
}
