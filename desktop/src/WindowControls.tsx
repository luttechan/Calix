import { Minus, Square, X } from "lucide-react";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
export function WindowControls() {
  if (!isTauri()) return null;
  const window = getCurrentWindow();
  return (
    <div className="window-controls">
      <button
        aria-label="최소화"
        title="최소화"
        onClick={() => void window.minimize()}
      >
        <Minus size={15} />
      </button>
      <button
        aria-label="최대화"
        title="최대화"
        onClick={() => void window.toggleMaximize()}
      >
        <Square size={12} />
      </button>
      <button
        aria-label="트레이로 이동"
        title="트레이로 이동"
        onClick={() => void window.close()}
      >
        <X size={17} />
      </button>
    </div>
  );
}
