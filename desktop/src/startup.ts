import { isTauri, invoke } from "@tauri-apps/api/core";
let finishing = false;
export function finishStartup() {
  if (finishing) return;
  finishing = true;
  // The animation runs in parallel with engine startup, never after it.
  const minimum = matchMedia("(prefers-reduced-motion: reduce)").matches
    ? 0
    : 2100;
  setTimeout(
    () => {
      const element = document.getElementById("calix-startup");
      element?.classList.add("departing");
      if (isTauri()) void invoke("app_ready").catch(() => {});
      setTimeout(() => {
        element?.remove();
        document.getElementById("root")?.removeAttribute("inert");
      }, 350);
    },
    Math.max(0, minimum - performance.now()),
  );
}
