import { t, useLanguage } from "./i18n";
import { Minus, Square, X } from "lucide-react";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
export function WindowControls() {
  useLanguage();
  if (!isTauri()) return null;
  const window = getCurrentWindow();
  return (
    <div className="window-controls">
      <button
        aria-label={t("최소화")}
        title={t("최소화")}
        onClick={() => void window.minimize()}
      >
        <Minus size={15} />
      </button>
      <button
        aria-label={t("최대화")}
        title={t("최대화")}
        onClick={() => void window.toggleMaximize()}
      >
        <Square size={12} />
      </button>
      <button
        aria-label={t("트레이로 이동")}
        title={t("트레이로 이동")}
        onClick={() => void window.close()}
      >
        <X size={17} />
      </button>
    </div>
  );
}
