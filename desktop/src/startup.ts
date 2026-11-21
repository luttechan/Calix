import { isTauri, invoke } from "@tauri-apps/api/core";
import { motionReduced } from "./motion";
let finishing = false;
export function finishStartup() {
  if (finishing) return;
  finishing = true;
  // The animation runs in parallel with engine startup, never after it.
  const minimum = motionReduced() ? 0 : 2100;
  setTimeout(
    () => {
      const element = document.getElementById("calix-startup");
      element?.classList.add("departing");
      if (isTauri()) void invoke("app_ready").catch(() => {});
      setTimeout(() => {
        element?.remove();
        document.getElementById("root")?.removeAttribute("inert");
      }, motionReduced() ? 0 : 350);
    },
    Math.max(0, minimum - performance.now()),
  );
}
