import { useSyncExternalStore } from "react";
import { messages } from "./messages";

export type Language = "ko" | "en" | "ja";
const storageKey = "calix-language";
const listeners = new Set<() => void>();
const locales = { ko: "ko-KR", en: "en-US", ja: "ja-JP" };

function readLanguage(): Language {
  if (typeof window !== "undefined") {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved === "en" || saved === "ja") return saved;
    } catch {
      // The app preference remains available when browser storage is disabled.
    }
  }
  return "ko";
}

let language: Language = readLanguage();
export function currentLanguage() {
  return language;
}

export function setLanguage(value: unknown) {
  const next = value === "en" || value === "ja" ? value : "ko";
  if (typeof document !== "undefined") document.documentElement.lang = next;
  if (language === next) return;
  language = next;
  try {
    localStorage.setItem(storageKey, next);
  } catch {
    // The engine owns the saved setting.
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function useLanguage() {
  return useSyncExternalStore(subscribe, currentLanguage, currentLanguage);
}

export function locale() {
  return locales[language];
}

export function t(key: string, values?: readonly (number | string)[]) {
  const message = language !== "ko" && Object.hasOwn(messages, key)
    ? messages[key][language === "en" ? 0 : 1]
    : key;
  return values ? message.replace(/\{(\d+)\}/g, (match, index) => String(values[Number(index)] ?? match)) : message;
}

export function semesterName(name: string) {
  if (language === "ko") return name;
  const match = /^(\d{4})학년도 (1학기|2학기|여름 계절학기|겨울 계절학기)$/.exec(name);
  if (!match) return name;
  return language === "en" ? `${t(match[2])} ${match[1]}` : `${match[1]}年度 ${t(match[2])}`;
}

setLanguage(language);
