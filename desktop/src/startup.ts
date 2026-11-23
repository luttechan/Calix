import { isTauri, invoke } from "@tauri-apps/api/core";
import { motionReduced } from "./motion";
let finishing = false;

function waitForSignature(overlay: HTMLElement) {
  const animations = overlay.querySelector(".startup-signature")?.getAnimations({ subtree: true }) ?? [];
  if (animations.length === 0) return Promise.resolve();

  return new Promise<void>(resolve => {
    const timeout = window.setTimeout(resolve, 2150);
    void Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
      window.clearTimeout(timeout);
      resolve();
    });
  });
}

export async function finishStartup() {
  if (finishing) return;
  finishing = true;
  const overlay = document.getElementById("calix-startup");
  if (overlay && !motionReduced()) {
    await waitForSignature(overlay);
    overlay.classList.add("startup-signature-complete");
    if (!motionReduced()) await new Promise(resolve => window.setTimeout(resolve, 140));
  }
  overlay?.classList.add("departing");
  if (isTauri()) void invoke("app_ready").catch(() => {});
  if (overlay && !motionReduced()) await new Promise(resolve => window.setTimeout(resolve, 350));
  overlay?.remove();
  document.getElementById("root")?.removeAttribute("inert");
}
