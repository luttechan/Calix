import type { MouseEvent } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";

export function dragWindow(event: MouseEvent<HTMLElement>) {
  if (event.button !== 0 || event.defaultPrevented || !isTauri()) return;
  if (!(event.target instanceof Element) ||
      event.target.closest("button, a, input, select, textarea, [contenteditable], [data-no-window-drag]")) return;
  event.preventDefault();
  const window = getCurrentWindow();
  const action = event.detail === 2 ? window.toggleMaximize() : window.startDragging();
  void action.catch(() => {});
}
