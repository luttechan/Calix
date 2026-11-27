import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
  memo,
  lazy,
  Suspense,
  type ReactNode,
  type RefObject,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal, flushSync } from "react-dom";
import {
  Home,
  CalendarDays,
  Calculator,
  ClipboardCheck,
  ListChecks,
  ListTodo,
  ChartNoAxesColumn,
  NotebookPen,
  LayoutGrid,
  BookOpen,
  Settings,
  Video,
  FileText,
  Search,
  Plus,
  RefreshCw,
  ArrowUpRight,
  X,
  ChevronLeft,
  ChevronRight,
  Check,
  LogIn,
  LogOut,
  Sun,
  Power,
  LockKeyhole,
  UserRound,
  Square,
  Pencil,
  Trash2,
} from "lucide-react";
import { getVersion } from "@tauri-apps/api/app";
import { matchesEventFilter, type EventFilter } from "./eventFilters";
import { groupByCourse } from "./eventGroups";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { AttendancePage } from "./Attendance";
import { StudyPage, FocusDock } from "./Study";
import { SyncNotice } from "./SyncNotice";
import { animateCalendarMonth, motionReduced, saveMotionPreference } from "./motion";
import { PageHeading } from "./PageHeading";
import { ChangedNumber } from "./ChangedNumber";
import { invalidateMenuReads, peekMenuRead, readMenu } from "./menuReads";
import { playErrorCue, stopErrorCue } from "./errorCue";
import { applyThemePalette } from "./themePalette";
import { defaultTheme } from "./ThemePicker";
import { defaultSyncTrack } from "./syncCue";
import { DeadlinePage, CourseOverviewPage } from "./Overview";
import { GradesPage } from "./Grades";
import { PrivateDiaryMigration, ProtectedSection, SecurityMonitor, UnlockView } from "./Security";
import { UpdateDialog } from "./UpdateDialog";
import { WindowControls } from "./WindowControls";
import { dragWindow } from "./windowDrag";
import { currentLanguage, locale, setLanguage, t, useLanguage } from "./i18n";
import { rpc, subscribe, stopEngine } from "./bridge";
import { DateField } from "./ChecklistDeadline";
import {
  dateKey,
  dueText,
  localInput,
  monthGrid,
  monthName,
  remaining,
  shiftMonth,
  status,
  isExcusedMovie,
  weekdays,
} from "./dates";
import { calendarPeriod, dayDistance, layoutCalendarWeek, orderedRange, shiftCalendarDay, type CalendarPeriod, type CalendarRange } from "./calendarRanges";
import type { Snapshot, EventItem, Page, SecurityState } from "./types";
import { ChecklistPage, TimetablePage, SettingsPage } from "./Workspaces";
import type { TimetableViewState } from "./Timetable";
import { MainSemesterControl } from "./SemesterSettings";
import { DeveloperConsole } from "./DeveloperConsole";
import { HomeProfilePhoto, Onboarding } from "./Profile";
import { formatFullDate } from "./dateEra";
import { finishStartup } from "./startup";
const CachedDiary = lazy(() => import("./Diary").then(({ DiaryPage }) => ({ default: memo(DiaryPage) })));
const CachedChecklist = memo(ChecklistPage);
type ContextValue = {
  data: Snapshot;
  mutate: (
    method: string,
    params?: Record<string, unknown>,
    options?: { inlineError?: boolean },
  ) => Promise<unknown>;
  notify: (message: string, error?: boolean) => void;
  soundError: () => void;
  openEvent: (key: string) => void;
  leave: RefObject<(() => Promise<void>) | null>;
  draft: RefObject<(() => Promise<void>) | null>;
  requestInstall: () => void;
  requestRestart: () => void;
  resetView: () => void;
  openCredits: () => void;
};
const Context = createContext<ContextValue | null>(null);
export function useCalix() {
  return useContext(Context)!;
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
  closeLabel = "닫기",
  className = "",
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  closeLabel?: string;
  className?: string;
}) {
  useLanguage();
  const ref = useRef<HTMLDialogElement>(null);
  const closing = useRef<Animation | null>(null);
  const latestClose = useRef(onClose);
  latestClose.current = onClose;
  useLayoutEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      closing.current?.cancel();
      closing.current = null;
    };
  }, []);
  const requestClose = () => {
    const dialog = ref.current;
    if (closing.current) return;
    if (!dialog || motionReduced()) {
      onClose();
      return;
    }
    const style = getComputedStyle(dialog);
    const animation = dialog.animate(
      [
        { opacity: Number(style.opacity), transform: style.transform },
        { opacity: 0, transform: "translateY(17px) scale(.96)" },
      ],
      { duration: 180, easing: "cubic-bezier(.32, 0, .67, 0)", fill: "forwards" },
    );
    closing.current = animation;
    dialog.dataset.motionClosing = "";
    void animation.finished.then(() => {
      // Keep the dialog faded out until React commits its removal.
      flushSync(() => latestClose.current());
      if (ref.current === dialog) {
        closing.current = null;
        delete dialog.dataset.motionClosing;
        animation.cancel();
      }
    }, () => {});
  };
  return (
    <dialog
      ref={ref}
      aria-label={title}
      className={["modal", wide && "wide", className].filter(Boolean).join(" ")}
      onCancel={(e) => {
        e.preventDefault();
        e.stopPropagation();
        requestClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button
          className="icon-button"
          title={t(closeLabel)}
          aria-label={t(closeLabel)}
          onClick={requestClose}
        >
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
export function TypeBadge({ event }: { event: EventItem }) {
  useLanguage();
  return (
    <span
      className={`type-badge ${event.type_id ? "custom" : event.kind}`}
      style={
        event.type_color
          ? {
              color: event.type_color,
              borderColor: `${event.type_color}55`,
              background: `${event.type_color}12`,
            }
          : undefined
      }
    >
      {event.type_name ||
        (event.kind === "movie"
          ? t("영상")
          : event.kind === "assignment"
            ? t("과제")
            : t("일정"))}
    </span>
  );
}
export function EventRows({
  events,
  limit = 50,
}: {
  events: EventItem[];
  limit?: number;
}) {
  useLanguage();
  const { openEvent } = useCalix(),
    [index, setIndex] = useState(0);
  const count = Math.ceil(events.length / limit),
    page = Math.min(index, Math.max(0, count - 1)),
    start = limit < 50 ? 0 : page * limit;
  return (
    <div className="event-table">
      <div className="event-table-head">
        <span>{t("유형")}</span>
        <span>{t("과목")}</span>
        <span>{t("일정")}</span>
        <span>{t("기한")}</span>
        <span>{t("남은 시간")}</span>
      </div>
      {events.slice(start, start + limit).map((e) => (
        <button
          key={e.key}
          className={`event-row ${e.completed && !isExcusedMovie(e) ? "completed" : ""}`}
          onClick={() => openEvent(e.key)}
        >
          <TypeBadge event={e} />
          <span className="muted">{e.course_name || t("개인 일정")}</span>
          <span className="event-name">{e.title}</span>
          <span className="muted">{dueText(e.due_at)}</span>
          <span
            className={
              isExcusedMovie(e)
                ? "attendance-status excused"
                : !e.completed &&
              e.due_at &&
              new Date(e.due_at).getTime() < Date.now()
                ? "danger"
                : "muted"
            }
          >
            {status(e)}
          </span>
        </button>
      ))}
      {!events.length && <div className="empty">{t("일정 없음")}</div>}
      {limit >= 50 && count > 1 && (
        <div className="pagination">
          <span>
            {start + 1}–{Math.min(start + limit, events.length)} /{" "}
            {events.length}
          </span>
          <button
            className="icon-button"
            aria-label={t("이전 목록")}
            disabled={!page}
            onClick={() => setIndex(page - 1)}
          >
            <ChevronLeft size={17} />
          </button>
          <button
            className="icon-button"
            aria-label={t("다음 목록")}
            disabled={page >= count - 1}
            onClick={() => setIndex(page + 1)}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      )}
    </div>
  );
}
const navigation: [Page, string, typeof Home][] = [
  ["home", "홈", Home],
  ["calendar", "달력", CalendarDays],
  ["assignments", "과제", FileText],
  ["videos", "영상", Video],
  ["timetable", "시간표", LayoutGrid],
  ["grades", "학점", Calculator],
  ["attendance", "출결", ClipboardCheck],
  ["study", "학습", BookOpen],
  ["checklist", "체크리스트", ListChecks],
  ["diary", "일기장", NotebookPen],
  ["deadlines", "마감 보드", ListTodo],
  ["courses", "과목별 현황", ChartNoAxesColumn],
];
const pageLabel = (id: Page, title: string) =>
  id === "grades" && currentLanguage() !== "ko" ? "GPA" : t(title);
export function App() {
  useLanguage();
  const [appVersion, setAppVersion] = useState(__CALIX_VERSION__);
  useEffect(() => {
    let active = true;
    if (isTauri())
      void getVersion()
        .then((value) => {
          if (active && typeof value === "string" && value)
            setAppVersion(value);
        })
        .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  const developerClicks = useRef({ count: 0, time: 0 });
  const privacyLocked = useRef(false);
  const lockScreenShown = useRef(false);
  const navigationRequest = useRef(0);
  const refreshRequest = useRef(0);
  const lockRequest = useRef(false);
  const [locking, setLocking] = useState(false);
  const [data, setData] = useState<Snapshot | null>(null),
    [error, setError] = useState(""),
    [page, setPage] = useState<Page>("home"),
    [shortcuts, setShortcuts] = useState(false),
    [selected, setSelected] = useState<string | null>(null),
    [addDate, setAddDate] = useState<{ end: string; start?: string } | null>(null),
    [toast, setToast] = useState<{message: string; error: boolean} | null>(null),
    [query, setQuery] = useState(""),
    [busy, setBusy] = useState(false),
    [loggedIn, setLoggedIn] = useState(false),
    [credits, setCredits] = useState(false),
    [startupUpdate, setStartupUpdate] = useState(false),
    [exit, setExit] = useState(false),
    [exitError, setExitError] = useState(""),
    [install, setInstall] = useState(false),
    [restart, setRestart] = useState(false),
    [exiting, setExiting] = useState(false);
  const exitLock = useRef(false);
  const [openedChecklist, setOpenedChecklist] = useState(false);
  const [openedDiary, setOpenedDiary] = useState(false);
  const [diaryMigrationDismissed, setDiaryMigrationDismissed] = useState(false);
  const [stateGeneration, setStateGeneration] = useState(0);
  const timetableView = useRef<TimetableViewState | null>(null);
  const draft = useRef<(() => Promise<void>) | null>(null),
    leave = useRef<(() => Promise<void>) | null>(null),
    searchRef = useRef<HTMLInputElement>(null),
    toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reminders = data?.preferences.reminders;
  const errorSound = useRef({ enabled: true, volume: 0.6 });
  errorSound.current = {
    enabled: reminders?.enabled !== false && reminders?.sound !== false,
    volume: reminders?.volume ?? 0.6,
  };
  const soundError = useCallback(() => {
    playErrorCue(errorSound.current.enabled, errorSound.current.volume);
  }, []);
  useEffect(() => {
    if (data || error) finishStartup();
  }, [data, error]);
  useEffect(() => {
    if (error) soundError();
  }, [error, soundError]);
  useEffect(() => {
    if (!errorSound.current.enabled || reminders?.volume === 0) stopErrorCue();
  }, [reminders?.enabled, reminders?.sound, reminders?.volume]);
  const notify = useCallback((message: string, error = false) => {
    setToast({message: t(message), error});
    if (error) {
      soundError();
      window.dispatchEvent(new CustomEvent("calix:ui-error", { detail: message }));
    }
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  }, [soundError]);
  const consoleOpenError = useCallback(() => notify("Calix Console을 열지 못했습니다.", true), [notify]);
  const finishEditing = async () => {
    if (draft.current) await draft.current();
    if (leave.current) await leave.current();
  };
  const openLogin = async () => {
    if (!isTauri()) {
      notify("로그인은 Windows 앱에서 진행합니다.");
      return;
    }
    await rpc("session.prepare");
    await invoke("campus_cancel").catch(() => {});
    try {
      await invoke("auth_open", {
        theme: document.documentElement.dataset.theme || defaultTheme,
        font: document.documentElement.dataset.font || "pretendard",
        language: currentLanguage(),
      });
    } catch (error) {
      await rpc("session.cancel").catch(() => {});
      throw error;
    }
  };
  privacyLocked.current = !!data?.security?.locked;
  const refresh = useCallback(async () => {
    const request = ++refreshRequest.current;
    const snapshot = await rpc<Snapshot>("bootstrap");
    if (request !== refreshRequest.current) return;
    if (snapshot.security?.locked) invalidateMenuReads();
    setData(snapshot);
    setError("");
  }, []);
  const mutate = useCallback(
    async (method: string, params: Record<string, unknown> = {}, options?: { inlineError?: boolean }) => {
      let result;
      try {
        result = await rpc(method, params);
      } catch (e) {
        if (options?.inlineError) soundError();
        else notify((e as Error).message, true);
        throw e;
      }
      if (method === "data.reset" || method === "backup.restore" || method === "security.setup" ||
          method === "security.configure") invalidateMenuReads();
      else if (method.startsWith("semester.") || method.startsWith("timetable.term."))
        invalidateMenuReads("grades.read", "semester.roster");
      else if (method === "holiday.save" || method === "special.save") invalidateMenuReads("calendar.year");
      if (method === "data.reset" || method === "backup.restore") timetableView.current = null;
      try {
        await refresh();
      } catch {
        notify("저장됨 / 목록을 다시 불러오지 못했습니다.", true);
      }
      return result;
    },
    [refresh, notify, soundError],
  );
  useEffect(() => {
    let alive = true;
    rpc<Snapshot>("bootstrap")
      .then((value) => {
        if (alive) setData(value);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    rpc<{ loggedIn: boolean }>("engine.state")
      .then((value) => {
        if (alive) setLoggedIn(value.loggedIn);
      })
      .catch(() => {});
    const unsubscribe = subscribe((message) => {
      if (message.event === "reminder" && isTauri() && !privacyLocked.current) {
        void invoke("reminder_show", { payload: { ...message.payload as object,
          language: currentLanguage(), reduce_motion: document.documentElement.hasAttribute("data-reduce-motion") } }).catch(
          (error) => notify(String(error), true),
        );
      }
      if (message.event === "data-changed") {
        invalidateMenuReads();
        void refresh().catch((e) => notify(e.message, true));
      }
      if (message.event === "auth-required" && !privacyLocked.current)
        void openLogin().catch((error) => notify(String(error), true));
      if (message.event === "sync-state") setBusy(Boolean(message.busy));
      if (message.event === "session-error" && isTauri())
        void invoke("auth_status", {
          success: false,
          message: String(message.message),
        }).catch(() => {});
      if (
        message.event === "authentication" &&
        message.loggedIn &&
        message.interactive &&
        isTauri()
      )
        void invoke("auth_status", { success: true, message: "" }).catch(
          () => {},
        );
      if (message.event === "notice") notify(String(message.message), message.level === "error");
      if (
        message.event === "update-state" &&
        message.automatic === true &&
        ["available", "manual"].includes(String(message.phase))
      )
        setStartupUpdate(true);
      if (message.event === "update-ready") {
        setStartupUpdate(false);
        setInstall(true);
        setExit(true);
      }
      if (message.event === "authentication")
        setLoggedIn(Boolean(message.loggedIn));
    });
    if (isTauri()) void rpc("update.startup").catch(() => {});
    return () => {
      alive = false;
      unsubscribe();
      if (toastTimer.current) clearTimeout(toastTimer.current);
      stopErrorCue();
    };
  }, []);
  useEffect(() => {
    if (!data || data.security?.locked) return;
    if (isTauri())
      void rpc<string>("browser.restore.begin")
        .then(async (token) => {
          try {
            const identity =
              await invoke<Record<string, unknown>>("campus_identity");
            await rpc("browser.identity", {
              ...identity,
              interactive: false,
              token,
            });
          } catch {
            await rpc("browser.restore.failed", { token }).catch(() => {});
          }
        })
        .catch(() => {});
  }, [Boolean(data), data?.security?.locked]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === "Escape") setQuery("");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  useEffect(() => {
    if (!isTauri()) return;
    let active = true;
    const cleanups: (() => void)[] = [];
    for (const [event, handler] of [
      ["app:exit-request", () => setExit(true)],
      ["app:launch", () => { void rpc("update.startup", { reopened: true }).catch(() => {}); }],
      ["auth:error-cue", soundError],
      [
        "app:hidden",
        () => {
          void finishEditing().catch((e) => notify(e.message, true));
        },
      ],
      [
        "auth:identity",
        (message: { payload: unknown }) => {
          void rpc("browser.identity", {
            ...(message.payload as Record<string, unknown>),
            interactive: true,
          }).catch((error) =>
            invoke("auth_status", {
              success: false,
              message: error.message,
            }).catch(() => {}),
          );
        },
      ],
      [
        "auth:dismissed",
        () => {
          void rpc("session.cancel").catch(() => {});
        },
      ],
    ] as const) {
      void listen(event, handler).then((cleanup) => {
        if (active) cleanups.push(cleanup);
        else cleanup();
      });
    }
    return () => {
      active = false;
      cleanups.forEach((cleanup) => cleanup());
    };
  }, []);
  useEffect(() => {
    if (!data) return;
    document.documentElement.dataset.theme = data.preferences.theme;
    document.documentElement.dataset.glass = String(data.preferences.glass);
    document.documentElement.dataset.font = data.preferences.font_mode;
    applyThemePalette(document.documentElement, data.preferences.theme_palette);
  }, [
    data?.preferences.theme,
    data?.preferences.glass,
    data?.preferences.font_mode,
    data?.preferences.theme_palette,
  ]);
  const reduceMotion = data?.preferences.reduce_motion;
  const language = data?.preferences.language;
  useLayoutEffect(() => {
    if (data) setLanguage(language ?? "ko");
  }, [Boolean(data), language]);
  const pageReady = Boolean(data && !data.security?.locked);
  const sidebarNav = useRef<HTMLElement>(null);
  const main = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    if (reduceMotion !== undefined) saveMotionPreference(reduceMotion);
  }, [reduceMotion]);
  useLayoutEffect(() => {
    main.current?.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [page]);
  const attendanceVisible = data?.preferences.attendance_visible === true;
  useLayoutEffect(() => {
    const menu = sidebarNav.current;
    if (!menu) return;
    const alignMarker = () => {
      const active = menu.querySelector<HTMLButtonElement>("button[aria-current='page']");
      menu.toggleAttribute("data-marked", Boolean(active));
      if (active) {
        menu.style.setProperty("--nav-marker-y", `${active.offsetTop + 8}px`);
        menu.style.setProperty("--nav-marker-height", `${active.offsetHeight - 16}px`);
      }
    };
    alignMarker();
    const observer = new ResizeObserver(alignMarker);
    observer.observe(menu);
    return () => observer.disconnect();
  }, [page, attendanceVisible, pageReady]);
  useEffect(() => {
    if (isTauri() && data?.preferences.onboarding_complete && !data.security?.locked)
      void rpc("reminders.ready").catch(() => {});
  }, [data?.preferences.onboarding_complete, data?.security?.locked]);
  useEffect(() => {
    if (!isTauri()) return;
    let active = true;
    let stop: (() => void) | undefined;
    void listen<{ key: string }>("reminder:open", (event) => {
      if (active && !privacyLocked.current) {
        setQuery("");
        if (event.payload.key) setSelected(event.payload.key);
        else
          void finishEditing()
            .then(() => {
              if (!active) return;
              setSelected(null);
              setAddDate(null);
              setPage("calendar");
            })
            .catch((error) => notify(error.message, true));
      }
    }).then((clean) => {
      if (active) stop = clean;
      else clean();
    });
    return () => {
      active = false;
      stop?.();
    };
  }, []);
  const navigate = async (next: Page) => {
    if (lockRequest.current) return;
    const request = ++navigationRequest.current;
    try {
      await finishEditing();
      if (request !== navigationRequest.current) return;
      if ((page === "grades" || page === "timetable") && page !== next &&
          data?.security?.policy[page] && data.security.unlocked.includes(page)) {
        if (page === "grades") invalidateMenuReads("grades.read");
        await rpc("security.lock", { scope: page });
        await refresh();
      }
      setSelected(null);
      setAddDate(null);
      if (request === navigationRequest.current) {
        if (next === "checklist") setOpenedChecklist(true);
        if (next === "diary") setOpenedDiary(true);
        setPage(next);
      }
    } catch (e) {
      notify((e as Error).message, true);
    }
  };

  const lockScreen = async () => {
    if (lockRequest.current || !data?.security?.configured) return;
    lockRequest.current = true;
    setLocking(true);
    try {
      await finishEditing();
      ++navigationRequest.current;
      const security = await rpc<SecurityState>("security.lock", { scope: "main" });
      if (!security.locked) throw new Error("비밀번호를 먼저 설정하세요.");
      invalidateMenuReads();
      ++refreshRequest.current;
      privacyLocked.current = true;
      setData(previous => previous ? { ...previous, security } : previous);
      setQuery(""); setSelected(null); setAddDate(null);
      setExit(false); setExitError(""); setCredits(false); setStartupUpdate(false);
      setInstall(false); setRestart(false); setToast(null);
      if (toastTimer.current) clearTimeout(toastTimer.current);
      if (isTauri()) await invoke("privacy_lock");
      await refresh();
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      lockRequest.current = false;
      setLocking(false);
    }
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!data || data.security?.locked || event.repeat || event.isComposing || document.querySelector('dialog[open]')) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
      const key = event.key.toLowerCase();
      if (key === "?") { event.preventDefault(); setShortcuts(true); return; }
      if (!event.altKey || event.ctrlKey || event.metaKey) return;
      if (key === "n") { event.preventDefault(); setAddDate({ end: dateKey() }); }
      if (key === "r") { event.preventDefault(); document.querySelector<HTMLButtonElement>("[data-sync-action]")?.click(); }
      if (key === "l") { event.preventDefault(); void lockScreen(); }
      const pages: Page[] = ["home", "calendar", "assignments", "videos", "timetable", "grades"];
      if (/^[1-6]$/.test(key)) { event.preventDefault(); void navigate(pages[Number(key)-1]); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const sorted = useMemo(
    () =>
      data
        ? [...data.events].sort(
            (a, b) =>
              (a.due_at ? new Date(a.due_at).getTime() : Infinity) -
              (b.due_at ? new Date(b.due_at).getTime() : Infinity),
          )
        : [],
    [data],
  );
  const found = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    const matches: EventItem[] = [];
    if (!needle) return matches;
    for (const event of sorted) {
      if (`${event.title} ${event.course_name}`.toLocaleLowerCase().includes(needle)) matches.push(event);
      if (matches.length === 8) break;
    }
    return matches;
  }, [query, sorted]);
  const today = dateKey(),
    pending = remaining(sorted),
    todayEvents = pending.filter(
      (e) => e.due_at && dateKey(e.due_at) === today,
    );
  const openEvent = useCallback((key: string) => {
    setQuery("");
    setSelected(key);
  }, []);
  const context = useMemo(
    () =>
      data
        ? {
            data: { ...data, version: appVersion },
            mutate,
            notify,
            soundError,
            openEvent,
            leave,
            draft,
            requestRestart: () => {
              setRestart(true);
              setExit(true);
            },
            requestInstall: () => {
              setInstall(true);
              setExit(true);
            },
            openCredits: () => setCredits(true),
            resetView: () => {
              draft.current = null;
              leave.current = null;
              timetableView.current = null;
              setDiaryMigrationDismissed(false);
              setPage("home");
              setSelected(null);
              setAddDate(null);
              setLoggedIn(false);
              setStateGeneration((value) => value + 1);
            },
          }
        : null,
    [data, appVersion, mutate, notify, openEvent, soundError],
  );
  const locked = data?.security?.locked === true;
  const exitAction = !locked && restart ? "restart" : !locked && install ? "install" : "quit";
  const closeExit = () => {
    if (exitLock.current) return;
    setExit(false);
    setExitError("");
    setInstall(false);
    setRestart(false);
  };
  const confirmExit = async () => {
    if (exitLock.current) return;
    exitLock.current = true;
    setExiting(true);
    setExitError("");
    let closeDialog = false;
    try {
      if (!locked) await finishEditing();
      await stopEngine(exitAction === "install");
      if (isTauri()) await invoke(exitAction === "restart" ? "restart_app" : "quit_app");
      else closeDialog = true;
    } catch (error) {
      setExitError(error instanceof Error ? error.message : String(error));
      soundError();
    } finally {
      exitLock.current = false;
      setExiting(false);
      if (closeDialog) closeExit();
    }
  };
  const exitDialog = exit && (
    <Modal
      title={exitAction === "restart" ? t("재시작하시겠습니까?") : exitAction === "install" ? t("업데이트를 설치하시겠습니까?") : t("종료하시겠습니까?")}
      onClose={closeExit}
    >
      {exitError && <p role="alert" className="danger">{exitError}</p>}
      <div className="dialog-actions">
        <span />
        <button type="button" disabled={exiting} onClick={closeExit}>{t("취소")}</button>
        <button type="button" className="primary" disabled={exiting} onClick={() => void confirmExit()}>
          {exitAction === "restart" ? t("저장하고 재시작") : exitAction === "install" ? t("설치하고 종료") : locked ? t("종료") : t("저장하고 종료")}
        </button>
      </div>
    </Modal>
  );
  if (locked && context) {
    lockScreenShown.current = true;
    return <Context.Provider value={context}>
      <div className="security-app-lock">
        <header className="lock-window-drag" onMouseDown={dragWindow}>
          <WindowControls />
        </header>
        <UnlockView onExit={() => setExit(true)} />
        {exitDialog}
      </div>
    </Context.Provider>;
  }
  return (
    <div className={`app-shell${lockScreenShown.current ? " app-shell--unlocked" : ""}`}>
      <SecurityMonitor state={data?.security} beforeLock={finishEditing} refresh={refresh} />
      <DeveloperConsole
        allowed={Boolean(data?.preferences.developer_mode) && !data?.security?.locked}
        onError={soundError}
        onOpenError={consoleOpenError}
      />
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            void navigate("home");
          }}
        >
          <img src="/assets/icons/calix.svg" alt="" />
          <span className="brand-name">
            <span>Calix</span>
            {data?.preferences.developer_mode && <b className="dev-badge">Dev</b>}
          </span>
          <small
            className="brand-version"
            title={appVersion}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              const now = Date.now();
              const last = developerClicks.current;
              const count = now - last.time < 1500 ? last.count + 1 : 1;
              developerClicks.current = { count, time: now };
              if (count >= 5 && data?.preferences.developer_mode) {
                developerClicks.current.count = 0;
                window.dispatchEvent(new Event("calix:developer-console"));
              }
            }}
          >
            {appVersion}
          </small>
        </a>
        <div className="nav-label">{t("워크스페이스")}</div>
        <nav ref={sidebarNav}>
          <span className="nav-motion-marker" aria-hidden="true" />
          {navigation.filter(([id]) => id !== "attendance" || attendanceVisible).map(([id, title, Icon]) => (
            <button
              key={id}
              className={page === id ? "active" : ""}
              onClick={() => void navigate(id)}
              aria-current={page === id ? "page" : undefined}
              title={pageLabel(id, title)}
            >
              <Icon size={19} />
              <span>{pageLabel(id, title)}</span>
              {id === "assignments" && data && (
                <small>
                  {pending.filter((e) => e.kind === "assignment").length}
                </small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button
            className={page === "settings" ? "active" : ""}
            onClick={() => void navigate("settings")}
            title={t("설정")}
          >
            <Settings size={19} />
            <span>{t("설정")}</span>
          </button>
          <button
            className="creator user-profile"
            onClick={() => void navigate("settings")}
            title={t("내 프로필")}
            aria-label={t("내 프로필")}
          >
            {data?.preferences.avatar ? (
              <img src={data.preferences.avatar} alt="" />
            ) : (
              <span className="user-avatar">
                <UserRound size={20} />
              </span>
            )}
            <span>
              <strong>{data?.preferences.nickname || t("사용자")}</strong>
              <small>{t("내 프로필")}</small>
            </span>
            <Settings size={15} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar" onMouseDown={dragWindow}>
          <div className="breadcrumb">
            Calix <span>/</span>{" "}
            {pageLabel(page, navigation.find((n) => n[0] === page)?.[1] ?? "설정")}
          </div>
          <div className="top-actions">
            <div className="search-box" data-no-window-drag>
              <Search size={16} />
              <input
                ref={searchRef}
                placeholder={t("일정 검색")}
                aria-label={t("일정 검색")}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <kbd>Ctrl K</kbd>
              {query && (
                <div className="search-results glass">
                  {found.map((e) => (
                    <button key={e.key} onClick={() => openEvent(e.key)}>
                      <TypeBadge event={e} />
                      <span>
                        {e.title}
                        <small>{e.course_name}</small>
                      </span>
                    </button>
                  ))}
                  {!found.length && <p>{t("검색 결과 없음")}</p>}
                </div>
              )}
            </div>
            <button
              className="icon-button"
              data-sync-action
              title={busy ? t("동기화 중단") : t("동기화")}
              aria-label={busy ? t("동기화 중단") : t("동기화")}
              onClick={() => {
                if (!busy && !loggedIn) { notify("학교 로그인 후 동기화하세요.", true); return; }
                const cancelling = busy;
                if (!cancelling) setBusy(true);
                rpc(cancelling ? "sync.cancel" : "sync").catch((e) => {
                  if (!cancelling) setBusy(false);
                  notify(e.message, true);
                });
              }}
            >
              {busy ? <Square size={16} /> : <RefreshCw size={18} />}
            </button>
            <button
              className="quiet"
              disabled={busy}
              onClick={() =>
                void (async () => {
                  if (loggedIn) {
                    await rpc("session.logout");
                    invalidateMenuReads();
                    if (isTauri()) await invoke("auth_logout");
                  } else await openLogin();
                })().catch((error) => notify(String(error), true))
              }
            >
              {loggedIn ? <LogOut size={16} /> : <LogIn size={16} />}
              <span>{loggedIn ? t("로그아웃") : t("로그인")}</span>
            </button>
            <button
              className="primary"
              onClick={() => setAddDate({ end: today })}
              disabled={!data}
            >
              <Plus size={17} />{t("일정 추가")}{" "}</button>
            <button
              className="icon-button"
              title={data?.security?.configured ? t("잠금") : t("비밀번호 설정 후 잠금")}
              aria-label={t("잠금")}
              aria-busy={locking}
              disabled={!data?.security?.configured || locking}
              onClick={() => void lockScreen()}
            >
              <LockKeyhole size={16} />
            </button>
            <button
              className="icon-button"
              title={t("종료")}
              aria-label={t("종료")}
              onClick={() => setExit(true)}
            >
              <Power size={16} />
            </button>
            <WindowControls />
          </div>
        </header>
        <main ref={main}>
          {!data ? (
            <div className="loading-state">
              {error ? (
                <>
                  <h2>{t("연결 오류")}</h2>
                  <p>{error}</p>
                  <button
                    onClick={() =>
                      void refresh().catch((e) => setError(e.message))
                    }
                  >{t("다시 시도")}{" "}</button>
                </>
              ) : (
                <>
                  <div className="skeleton hero-skeleton" />
                  <div className="skeleton content-skeleton" />
                </>
              )}
            </div>
          ) : (
            <Context.Provider key={stateGeneration} value={context}>
              {(!data.preferences.onboarding_complete ||
                !data.preferences.nickname) && <Onboarding />}
              {data.privateDiaryMigration && data.preferences.onboarding_complete && !diaryMigrationDismissed &&
                <PrivateDiaryMigration onClose={() => setDiaryMigrationDismissed(true)} />}
              {page === "home" && (
                <>
                  <PageHeading title={(data.preferences.greeting === "{닉네임}님, 오셨군요!"
                    ? t(data.preferences.greeting) : data.preferences.greeting).replaceAll("{닉네임}", data.preferences.nickname || t("나"))}>
                    <time className="home-heading-date" dateTime={today}>{formatFullDate(today, data.preferences.date_era)}</time>
                    <MainSemesterControl />
                    <HomeProfilePhoto />
                  </PageHeading>
                  <section className="stats">
                    <button
                      className="stat glass"
                      onClick={() => void navigate("calendar")}
                    >
                      <span>{t("오늘까지 할 일")}{" "}<ArrowUpRight size={18} />
                      </span>
                      <strong>
                        <ChangedNumber value={todayEvents.length} />
                        <small>{t("건")}</small>
                      </strong>
                      <div className="stat-track">
                        <i
                          style={{ width: todayEvents.length ? "38%" : "0%" }}
                        />
                      </div>
                    </button>
                    <button
                      className="stat glass"
                      onClick={() => void navigate("assignments")}
                    >
                      <span>{t("남은 일정")}{" "}<ArrowUpRight size={18} />
                      </span>
                      <strong>
                        <ChangedNumber value={pending.length} />
                        <small>{t("개")}</small>
                      </strong>
                      <div className="mini-tags">
                        <span>{t("과제")}{" "}
                          {
                            pending.filter((e) => e.kind === "assignment")
                              .length
                          }
                        </span>
                        <span>{t("영상")}{" "}
                          {pending.filter((e) => e.kind === "movie").length}
                        </span>
                      </div>
                    </button>
                  </section>
                  <div className="home-content">
                    <section className="glass upcoming-panel">
                      <div className="section-heading">
                        <h2>{t("남은 일정")}</h2>
                        <button
                          className="text-button"
                          onClick={() => void navigate("calendar")}
                        >{t("전체 보기")}{" "}<ArrowUpRight size={15} />
                        </button>
                      </div>
                      <EventRows events={pending} limit={7} />
                    </section>
                    <section className="glass today-panel">
                      <div className="section-heading">
                        <h2>{t("오늘 할 일")}</h2>
                        <span className="count-pill">{todayEvents.length}</span>
                      </div>
                      {todayEvents.length ? (
                        todayEvents.slice(0, 5).map((e) => (
                          <button
                            key={e.key}
                            className="today-event"
                            onClick={() => openEvent(e.key)}
                          >
                            <span className={`event-symbol ${e.kind}`}>
                              {e.kind === "movie" ? (
                                <Video size={18} />
                              ) : (
                                <FileText size={18} />
                              )}
                            </span>
                            <span>
                              <strong>{e.title}</strong>
                              <small>{e.course_name}</small>
                              <em>{status(e)}</em>
                            </span>
                            <ArrowUpRight size={16} />
                          </button>
                        ))
                      ) : (
                        <div className="empty">
                          <Sun size={30} />
                          <p>{t("오늘 마감 없음")}</p>
                        </div>
                      )}
                      <div className="today-footer">
                        <CalendarDays size={17} />
                        {today.slice(5).replace("-", "월 ")}{t("일")}{" "}</div>
                    </section>
                  </div>
                </>
              )}
              {page === "calendar" && (
                <CalendarPage events={sorted} onAdd={(end, start) => setAddDate({ end, start })} />
              )}
              {(page === "assignments" || page === "videos") && (
                <EventListPage
                  key={page}
                  kind={page === "assignments" ? "assignment" : "movie"}
                  events={sorted}
                />
              )}
              {openedChecklist && <div hidden={page !== "checklist"}>
                <CachedChecklist />
              </div>}
              {page === "timetable" && <ProtectedSection scope="timetable">
                <TimetablePage key={data.mainTerm} viewState={timetableView} onOpenHome={() => void navigate("home")} />
              </ProtectedSection>}
              {page === "grades" && <ProtectedSection scope="grades"><GradesPage /></ProtectedSection>}
              {page === "attendance" && <AttendancePage />}
              {page === "study" && <StudyPage />}
              {page === "deadlines" && <DeadlinePage />}
              {page === "courses" && <CourseOverviewPage />}
              {openedDiary && <div hidden={page !== "diary"}>
                <Suspense fallback={<div className="loading-state" aria-busy="true" />}>
                  <CachedDiary active={page === "diary"} />
                </Suspense>
              </div>}
              {page === "settings" && <SettingsPage />}
              {selected && data.events.find((e) => e.key === selected) && (
                <EventDetails
                  key={selected}
                  event={data.events.find((e) => e.key === selected)!}
                  onClose={() => setSelected(null)}
                />
              )}
              {addDate && (
                <AddEvent
                  initialDate={addDate.end}
                  initialStart={addDate.start}
                  onClose={() => setAddDate(null)}
                />
              )}
              <FocusDock />
            </Context.Provider>
          )}
        </main>
        <footer className="statusbar">
          <span className={`connection-dot ${loggedIn ? "online" : ""}`} />
          <span>
            {busy
              ? t("동기화 중")
              : data?.lastSync
                ? t("최근 동기화 {0}", [String(dueText(data.lastSync))])
                : t("동기화 기록 없음")}
          </span>
          <button className="quiet" title={t("단축키 (?)")} onClick={() => setShortcuts(true)}>{t("단축키")}</button>
          <span className="status-version">{`v${appVersion}`}</span>
        </footer>
      </div>
      {shortcuts && <Modal title={t("단축키")} onClose={() => setShortcuts(false)}>
        <dl className="shortcut-list">{[["Alt + N", "일정 추가"], ["Alt + R", "동기화 / 중단"], ["Alt + L", "화면 잠금"], ["Alt + 1~6", "홈 / 달력 / 과제 / 영상 / 시간표 / 학점"], ["Ctrl + K", "일정 검색"], ["?", "단축키 안내"]].map(([key, label]) => <div key={key}><dt><kbd>{key}</kbd></dt><dd>{t(label)}</dd></div>)}</dl>
      </Modal>}
      <SyncNotice
        sound={Boolean(
          data?.preferences.reminders.enabled &&
          data?.preferences.reminders.sound,
        )}
        volume={data?.preferences.reminders.volume ?? 0.6}
        track={data?.preferences.reminders.sync_track ?? defaultSyncTrack}
      />
      {toast && (
        <div className={`toast${toast.error ? " toast-error" : ""}`} role={toast.error ? "alert" : "status"}>
          {toast.error ? <X size={17} /> : <Check size={17} />}
          {toast.message}
          <button aria-label={t("알림 닫기")} onClick={() => setToast(null)}>
            <X size={15} />
          </button>
        </div>
      )}
      {startupUpdate && context && (
        <Context.Provider value={context}>
          <UpdateDialog
            onClose={() => setStartupUpdate(false)}
            onInstall={() => {
              setStartupUpdate(false);
              setInstall(true);
              setExit(true);
            }}
          />
        </Context.Provider>
      )}
      {credits && (
        <Modal title="Calix" onClose={() => setCredits(false)}>
          <div className="credit-profile">
            <img
              className="studio-symbol"
              src="/assets/lutein-studio.png"
              alt=""
            />
            <h2>Lutein Studio</h2>
            <p>Calix {appVersion}</p>
          </div>
          <div className="credit-developer">
            <img src="/assets/profile-avatar.png" alt="" />
            <span>Lutté Laurent</span>
          </div>
          <section className="credit-thanks" aria-labelledby="credit-thanks-title">
            <h3 id="credit-thanks-title" lang="en">Special Thanks</h3>
            <dl>
              <div>
                <dt lang="en">Aurora QA</dt>
                <dd lang="en">YELIN CHAE</dd>
              </div>
              <div>
                <dt lang="ja">日本語監修</dt>
                <dd>Runo</dd>
              </div>
            </dl>
          </section>
          <div className="credit-links">
            <a
              href="https://github.com/luttechan/Calix"
              target="_blank"
              rel="noreferrer"
              onClick={(e) => {
                if (isTauri()) {
                  e.preventDefault();
                  void rpc("app.open", { page: "github" }).catch((error) =>
                    notify(error.message, true),
                  );
                }
              }}
            >
              GitHub <ArrowUpRight size={16} />
            </a>
            <a
              href="https://luttechan.github.io/lutte_family/"
              target="_blank"
              rel="noreferrer"
              onClick={(e) => {
                if (isTauri()) {
                  e.preventDefault();
                  void rpc("app.open", { page: "family" }).catch((error) =>
                    notify(error.message, true),
                  );
                }
              }}
            >
              Lutté Family <ArrowUpRight size={16} />
            </a>
          </div>
          <p className="license-note">
            Pretendard © 2021 Kil Hyung-jin. SIL OFL 1.1.
          </p>
        </Modal>
      )}
      {exitDialog}
    </div>
  );
}
function EventListPage({
  kind,
  events,
}: {
  kind: string;
  events: EventItem[];
}) {
  useLanguage();
  const [filter, setFilter] = useState<EventFilter>("all");
  const [view, setView] = useState<"all" | "course">("all");
  const [course, setCourse] = useState("all");
  const courses = useMemo(
    () => groupByCourse(events.filter((event) => event.kind === kind)),
    [events, kind],
  );
  const rows = events.filter(
    (event) =>
      event.kind === kind &&
      (course === "all" || String(event.course_id) === course),
  );
  const now = Date.now();
  const filtered = rows.filter((event) =>
    matchesEventFilter(event, filter, now),
  );
  const options: [EventFilter, string][] = [
    ["all", "전체"],
    ["pending", "미완료"],
    ["done", "완료"],
    ["overdue", "기한 경과"],
  ];
  return (
    <>
      <PageHeading title={kind === "assignment" ? t("과제") : t("영상")}>
        <span className="count-pill"><ChangedNumber value={filtered.length} />{t("개")}</span>
      </PageHeading>
      <div className="event-filter-bar">
        <div className="event-view-toolbar">
          <div className="segmented" aria-label={t("일정 보기")}>
            {(
              [
                ["all", "전체 보기"],
                ["course", "강의별 보기"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                aria-pressed={view === id}
                className={view === id ? "selected" : ""}
                onClick={() => setView(id)}
              >
                {t(label)}
              </button>
            ))}
          </div>
          <select
            aria-label={t("강의 선택")}
            value={course}
            onChange={(event) => setCourse(event.target.value)}
          >
            <option value="all">{t("전체 강의")}</option>
            {courses.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
        </div>
        <div className="event-status-filters" aria-label={t("일정 상태")}>
          {options.map(([value, label]) => (
            <button
              key={value}
              className={filter === value ? "selected" : ""}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {t(label)}
              <span>
                {
                  rows.filter((event) => matchesEventFilter(event, value, now))
                    .length
                }
              </span>
            </button>
          ))}
        </div>
      </div>
      {view === "all" ? (
        <section className="glass list-panel">
          <EventRows key={`${kind}:${course}:${filter}`} events={filtered} />
        </section>
      ) : (
        <div className="course-event-groups">
          {groupByCourse(filtered).map((group) => (
            <details className="glass course-event-group" key={group.id} open>
              <summary>
                <strong>{group.name}</strong>
                <span className="count-pill">{group.events.length}{t("개")}</span>
              </summary>
              <EventRows key={`${course}:${filter}`} events={group.events} />
            </details>
          ))}
          {!filtered.length && (
            <div className="glass empty">{t("일정 없음")}</div>
          )}
        </div>
      )}
    </>
  );
}
const firstCalendarYear = 1900;
const lastCalendarYear = 2200;
const calendarYears = Array.from({ length: lastCalendarYear - firstCalendarYear + 1 }, (_, index) => firstCalendarYear + index);
const calendarMonths = Array.from({ length: 12 }, (_, index) => String(index + 1).padStart(2, "0"));

type CalendarDrag = {
  pointer: number;
  origin: string;
  target?: string;
  x: number;
  y: number;
  grabbed?: CalendarRange & { event: EventItem; offset: number; action: "move" | "start" | "end" };
};
type CalendarPreview = {
  event?: EventItem;
  bars: { x: number; y: number; width: number; continuesBefore: boolean; continuesAfter: boolean }[];
};
type CalendarMenu = { event: EventItem; day: string; anchorDay: string; x: number; y: number; anchor: HTMLButtonElement };

function calendarCellAt(grid: HTMLDivElement, x: number, y: number) {
  return document.elementsFromPoint(x, y).find((element): element is HTMLElement =>
    element instanceof HTMLElement && Boolean(element.dataset.calendarDate) && grid.contains(element));
}

function calendarPreview(grid: HTMLDivElement, range: CalendarRange, grabbed: CalendarDrag["grabbed"]): CalendarPreview {
  const bounds = grid.getBoundingClientRect();
  const bars: CalendarPreview["bars"] = [];
  for (const week of grid.querySelectorAll(".calendar-week")) {
    const cells = Array.from(week.querySelectorAll<HTMLElement>("[data-calendar-date]"));
    const overlap = cells.filter(cell => cell.dataset.calendarDate! >= range.start && cell.dataset.calendarDate! <= range.end);
    if (!overlap.length) continue;
    const first = overlap[0].getBoundingClientRect();
    const last = overlap[overlap.length - 1].getBoundingClientRect();
    const occupied = Array.from(week.querySelectorAll<HTMLElement>(".calendar-event, .more-events"))
      .filter(item => !grabbed || item.dataset.calendarMove !== grabbed.event.key)
      .map(item => item.getBoundingClientRect())
      .filter(item => item.left < last.right - 7 && item.right > first.left + 7);
    const fits = (offset: number) => offset + 23 <= first.height - 3 &&
      occupied.every(item => first.top + offset + 23 <= item.top || first.top + offset >= item.bottom);
    const preferred = Math.min(grabbed?.offset ?? 45, first.height - 26);
    let y = preferred;
    if (!fits(y)) {
      y = 45;
      while (y + 23 <= first.height - 3 && !fits(y)) y += 27;
      if (y + 23 > first.height - 3) y = first.height - 26;
    }
    bars.push({
      x: first.left - bounds.left + 7,
      y: first.top - bounds.top + y,
      width: last.right - first.left - 14,
      continuesBefore: range.start < cells[0].dataset.calendarDate!,
      continuesAfter: range.end > cells[cells.length - 1].dataset.calendarDate!,
    });
  }
  return { event: grabbed?.event, bars };
}

function calendarDragRange(current: CalendarDrag, target: string): CalendarRange {
  const grabbed = current.grabbed;
  if (!grabbed) return orderedRange(current.origin, target);
  if (grabbed.action === "start") return { start: target < grabbed.end ? target : grabbed.end, end: grabbed.end };
  if (grabbed.action === "end") return { start: grabbed.start, end: target > grabbed.start ? target : grabbed.start };
  const days = dayDistance(current.origin, target);
  return { start: shiftCalendarDay(grabbed.start, days), end: shiftCalendarDay(grabbed.end, days) };
}

function CalendarEventMenu({ menu, onClose, onEdit, onDelete }: {
  menu: CalendarMenu;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const popup = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useLayoutEffect(() => {
    const element = popup.current!;
    const rect = element.getBoundingClientRect();
    element.style.left = `${Math.max(8, Math.min(menu.x, window.innerWidth - rect.width - 8))}px`;
    element.style.top = `${Math.max(8, Math.min(menu.y, window.innerHeight - rect.height - 8))}px`;
    element.querySelector("button")?.focus({ preventScroll: true });
  }, [menu]);
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (!(event.target instanceof Node) || !popup.current?.contains(event.target)) close.current();
    };
    const dismiss = () => close.current();
    document.addEventListener("pointerdown", outside, true);
    window.addEventListener("resize", dismiss);
    window.addEventListener("scroll", dismiss, true);
    window.addEventListener("blur", dismiss);
    return () => {
      document.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("scroll", dismiss, true);
      window.removeEventListener("blur", dismiss);
    };
  }, []);
  return createPortal(
    <div className="calendar-event-menu" ref={popup} role="menu" aria-label={menu.event.title}
      onContextMenu={event => event.preventDefault()}
      onKeyDown={event => {
        if (event.key === "Escape" || event.key === "Tab") {
          if (event.key === "Escape") event.preventDefault();
          event.stopPropagation();
          onClose();
          menu.anchor.focus({ preventScroll: true });
        } else if (["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) {
          event.preventDefault();
          const options = event.currentTarget.querySelectorAll("button");
          const toggle = document.activeElement === options[0] ? 1 : 0;
          options[event.key === "Home" ? 0 : event.key === "End" ? 1 : toggle]?.focus();
        }
      }}>
      <button type="button" role="menuitem" onClick={onEdit}><Pencil size={15} />{t("수정")}</button>
      <button type="button" role="menuitem" className="danger" onClick={onDelete}><Trash2 size={15} />{t("삭제")}</button>
    </div>,
    document.body,
  );
}

function CalendarPage({
  events,
  onAdd,
}: {
  events: EventItem[];
  onAdd: (end: string, start?: string) => void;
}) {
  useLanguage();
  const { data, openEvent, mutate, notify } = useCalix(),
    [month, setMonth] = useState(dateKey().slice(0, 7)),
    [day, setDay] = useState(dateKey()),
    [kind, setKind] = useState("all");
  const [year, monthNumber] = month.split("-");
  const calendarGrid = useRef<HTMLDivElement>(null);
  const drag = useRef<CalendarDrag | null>(null);
  const ignoreClick = useRef(false);
  const moving = useRef(false);
  const [preview, setPreview] = useState<CalendarPreview | null>(null);
  const [menu, setMenu] = useState<CalendarMenu | null>(null);
  const [remove, setRemove] = useState<CalendarMenu | null>(null);
  const finishDrag = useCallback(() => {
    const current = drag.current;
    drag.current = null;
    setPreview(null);
    const grid = calendarGrid.current;
    if (current && grid?.hasPointerCapture(current.pointer)) grid.releasePointerCapture(current.pointer);
  }, []);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && drag.current) {
        event.preventDefault();
        finishDrag();
      }
    };
    const abort = () => finishDrag();
    window.addEventListener("keydown", escape);
    window.addEventListener("blur", abort);
    window.addEventListener("resize", abort);
    return () => {
      window.removeEventListener("keydown", escape);
      window.removeEventListener("blur", abort);
      window.removeEventListener("resize", abort);
    };
  }, [finishDrag]);
  const previousMonth = useRef(month);
  useLayoutEffect(() => {
    const before = previousMonth.current;
    previousMonth.current = month;
    if (before === month || !calendarGrid.current) return;
    return animateCalendarMonth(calendarGrid.current, month > before ? 1 : -1);
  }, [month]);
  const moveMonth = (next: string) => {
    setMenu(null);
    finishDrag();
    const [nextYear, nextMonth] = next.split("-").map(Number);
    const lastDay = new Date(Date.UTC(nextYear, nextMonth, 0)).getUTCDate();
    const nextDay = Math.min(lastDay, Number(day.slice(8)));
    setMonth(next);
    setDay(`${next}-${String(nextDay).padStart(2, "0")}`);
  };
  const visibleYear = Number(year);
  const currentYear = Number(dateKey().slice(0, 4));
  const onSnapshot = visibleYear === currentYear || visibleYear === currentYear + 1;
  const bootDates = {
    holidays: data.holidays,
    specialDates: data.specialDates,
  };
  const [historical, setHistorical] = useState<{
    year: number; dates: typeof bootDates;
  }>();
  useEffect(() => {
    if (onSnapshot) return;
    let active = true;
    readMenu<typeof bootDates>("calendar.year", { year: visibleYear })
      .then((value) => {
        if (active) setHistorical({ year: visibleYear, dates: value });
      })
      .catch((e) => {
        if (active) notify(e.message, true);
      });
    return () => {
      active = false;
    };
  }, [visibleYear, onSnapshot, data.holidays, data.specialDates, notify]);
  const dates = onSnapshot ? bootDates :
    peekMenuRead<typeof bootDates>("calendar.year", { year: visibleYear }) ??
    (historical?.year === visibleYear ? historical.dates : bootDates);
  const { buckets, periods } = useMemo(() => {
    const buckets = new Map<string, EventItem[]>();
    const periods: CalendarPeriod[] = [];
    for (const e of events) {
      if (!e.due_at || (kind !== "all" && e.kind !== kind)) continue;
      const period = calendarPeriod(e);
      if (period) {
        periods.push(period);
        continue;
      }
      const key = dateKey(e.due_at);
      const group = buckets.get(key) || [];
      group.push(e);
      buckets.set(key, group);
    }
    periods.sort((a, b) => a.start.localeCompare(b.start) || b.end.localeCompare(a.end));
    return { buckets, periods };
  }, [events, kind]);
  const weeks = useMemo(() => {
    const days = monthGrid(month);
    return Array.from({ length: 6 }, (_, i) => {
      const week = days.slice(i * 7, i * 7 + 7);
      return { days: week, ...layoutCalendarWeek(week, periods) };
    });
  }, [month, periods]);
  const shownEvents = [...(buckets.get(day) ?? []), ...periods
    .filter(period => period.start <= day && day <= period.end).map(period => period.event)];
  const count = periods.filter(period => period.start.slice(0, 7) <= month && period.end.slice(0, 7) >= month).length +
    [...buckets.entries()].reduce((sum, [date, items]) => date.startsWith(month) ? sum + items.length : sum, 0);
  const open = (event: EventItem, day: string) => {
    setDay(day);
    openEvent(event.key);
  };
  const contextActions = (event: EventItem, day: string) => {
    if (!event.manual) return {};
    return {
      "aria-haspopup": "menu" as const,
      "aria-expanded": menu?.event.key === event.key && menu.anchorDay === day,
      onContextMenu: (click: React.MouseEvent<HTMLButtonElement>) => {
        click.preventDefault();
        finishDrag();
        const target = calendarGrid.current &&
          calendarCellAt(calendarGrid.current, click.clientX, click.clientY)?.dataset.calendarDate;
        setMenu({ event, day: target || day, anchorDay: day, x: click.clientX, y: click.clientY, anchor: click.currentTarget });
      },
      onKeyDown: (press: React.KeyboardEvent<HTMLButtonElement>) => {
        if (press.key !== "ContextMenu" && !(press.shiftKey && press.key === "F10")) return;
        press.preventDefault();
        const box = press.currentTarget.getBoundingClientRect();
        setMenu({ event, day, anchorDay: day, x: box.left, y: box.bottom, anchor: press.currentTarget });
      },
    };
  };
  const beginDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || event.pointerType !== "mouse" || !event.isPrimary) return;
    ignoreClick.current = false;
    if (moving.current || !(event.target instanceof Element)) return;
    const button = event.target.closest("button");
    if (button && !button.hasAttribute("data-calendar-add") && !button.hasAttribute("data-calendar-move")) return;
    const cell = calendarCellAt(event.currentTarget, event.clientX, event.clientY);
    const origin = cell?.dataset.calendarDate;
    if (!origin || origin < `${firstCalendarYear}-01-01` || origin > `${lastCalendarYear}-12-31`) return;
    const key = button?.getAttribute("data-calendar-move");
    const action = event.target.closest<HTMLElement>("[data-calendar-edge]")?.dataset.calendarEdge;
    const period = key ? periods.find(period => period.event.key === key) : undefined;
    const selected = period?.event ?? (key ? buckets.get(origin)?.find(item => item.key === key) : undefined);
    if (selected && button instanceof HTMLButtonElement && (action === "start" || action === "end")) {
      // Focusing the resize handle must not scroll the calendar into view.
      event.preventDefault();
      button.focus({ preventScroll: true });
    }
    drag.current = { pointer: event.pointerId, origin, x: event.clientX, y: event.clientY,
      grabbed: selected && cell && button ? { event: selected, start: period?.start ?? origin, end: period?.end ?? origin,
        action: action === "start" || action === "end" ? action : "move",
        offset: button.getBoundingClientRect().top - cell.getBoundingClientRect().top } : undefined };
  };
  const continueDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const current = drag.current;
    if (!current || current.pointer !== event.pointerId) return;
    const target = calendarCellAt(event.currentTarget, event.clientX, event.clientY)?.dataset.calendarDate;
    if (!target || target === current.target) return;
    if (!current.target && target === current.origin &&
        (!current.grabbed || Math.hypot(event.clientX - current.x, event.clientY - current.y) < 5)) return;
    if (!current.target) {
      ignoreClick.current = true;
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    current.target = target;
    setPreview(calendarPreview(event.currentTarget, calendarDragRange(current, target), current.grabbed));
  };
  const dropDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const current = drag.current;
    if (!current || current.pointer !== event.pointerId) return;
    const target = current.target
      ? calendarCellAt(event.currentTarget, event.clientX, event.clientY)?.dataset.calendarDate : undefined;
    finishDrag();
    if (!target || target === current.origin || target < `${firstCalendarYear}-01-01` || target > `${lastCalendarYear}-12-31`) return;
    if (current.grabbed) {
      const range = calendarDragRange(current, target);
      if (range.start === current.grabbed.start && range.end === current.grabbed.end) return;
      moving.current = true;
      const key = current.grabbed.event.key;
      const operation = current.grabbed.action === "move"
        ? mutate("event.move", { key, days: dayDistance(current.origin, target) })
        : mutate("event.resize", { key, ...range });
      void operation
        .then(() => setDay(target)).catch(() => {}).finally(() => { moving.current = false; });
      return;
    }
    const { start, end } = orderedRange(current.origin, target);
    setDay(start);
    onAdd(end, start);
  };
  return (
    <>
      <PageHeading title={t("달력")}>
        <div className="toolbar calendar-navigation">
          <button
            className="icon-button"
            aria-label={t("이전 달")}
            title={t("이전 달")}
            disabled={month === `${firstCalendarYear}-01`}
            onClick={() => moveMonth(shiftMonth(month, -1))}
          >
            <ChevronLeft size={19} />
          </button>
          <div className="calendar-jump">
            <select aria-label={t("달력 연도")} value={year} onChange={(event) => moveMonth(`${event.target.value}-${monthNumber}`)}>
              {calendarYears.map((option) => <option key={option} value={option}>{option}{t("년")}</option>)}
            </select>
            <select className="calendar-month" aria-label={t("달력 월")} value={monthNumber} onChange={(event) => moveMonth(`${year}-${event.target.value}`)}>
              {calendarMonths.map((option) => <option key={option} value={option}>{monthName(Number(option))}</option>)}
            </select>
          </div>
          <button
            className="icon-button"
            aria-label={t("다음 달")}
            title={t("다음 달")}
            disabled={month === `${lastCalendarYear}-12`}
            onClick={() => moveMonth(shiftMonth(month, 1))}
          >
            <ChevronRight size={19} />
          </button>
          <button
            onClick={() => {
              finishDrag();
              setMonth(dateKey().slice(0, 7));
              setDay(dateKey());
            }}
          >{t("오늘")}{" "}</button>
        </div>
      </PageHeading>
      <div className="calendar-toolbar">
        <div className="segmented">
          {[
            ["all", "전체"],
            ["assignment", "과제"],
            ["movie", "영상"],
          ].map(([value, label]) => (
            <button
              key={value}
              className={kind === value ? "selected" : ""}
              aria-pressed={kind === value}
              onClick={() => setKind(value)}
            >
              {t(label)}
            </button>
          ))}
        </div>
        <span className="muted">{count}{t("개 일정")}</span>
      </div>
      <section className="glass calendar-panel">
        <div className="weekday-row">
          {weekdays.map((name, i) => (
            <span key={name} className={i === 6 ? "sunday" : ""}>
              {t(name)}
            </span>
          ))}
        </div>
        <div className="month-grid" ref={calendarGrid} data-dragging={preview ? true : undefined}
          onPointerDown={beginDrag} onPointerMove={continueDrag} onPointerUp={dropDrag}
          onPointerLeave={() => { if (drag.current && !drag.current.target) finishDrag(); }}
          onPointerCancel={finishDrag} onLostPointerCapture={finishDrag}
          onClickCapture={event => {
            if (event.detail && ignoreClick.current) {
              event.stopPropagation();
              ignoreClick.current = false;
            }
          }}>
          {weeks.map(week => (
            <div className="calendar-week" key={week.days[0]} style={{ "--range-lanes": week.lanes } as CSSProperties}>
            {week.days.map((key, weekday) => (
            <div
              key={key}
              data-calendar-date={key}
              className={`day-cell ${key.startsWith(month) ? "" : "outside"} ${key === day ? "day-selected" : ""}`}
              onClick={() => setDay(key)}
              onDoubleClick={(e) => {
                if (!e.target || !(e.target instanceof Element) || e.target.closest("button")) return;
                onAdd(key);
              }}
            >
              <div className="day-heading">
                <button
                  data-calendar-add=""
                  aria-label={t("{0} 일정 추가", [String(key)])}
                  className={key === dateKey() ? "date-today" : ""}
                  onClick={(e) => {
                    e.stopPropagation();
                    setDay(key);
                    onAdd(key);
                  }}
                >
                  {Number(key.slice(8))}
                </button>
                <span className="holiday-name">
                  {dates.holidays[key] || dates.specialDates[key] || ""}
                </span>
              </div>
              <div className="day-events">
                {(buckets.get(key) || []).slice(0, 3).map((e) => (
                  <button
                    key={e.key}
                    {...contextActions(e, key)}
                    data-calendar-move={e.manual ? e.key : undefined}
                    data-drag-source={preview?.event?.key === e.key || undefined}
                    className={`calendar-event ${e.kind} ${isExcusedMovie(e) ? "excused" : e.completed ? "completed" : ""} ${!e.completed && e.kind === "assignment" && e.due_at && new Date(e.due_at).getTime() < Date.now() ? "late" : ""}`}
                    title={`${e.title} / ${status(e)}`}
                    onClick={(click) => {
                      click.stopPropagation();
                      open(e, key);
                    }}
                  >
                    <i />
                    <span className="calendar-event-title">{e.title}</span>
                    {isExcusedMovie(e) && <small className="calendar-attendance">{t("공결")}</small>}
                    {e.manual && <><span data-calendar-edge="start" aria-hidden="true" />
                      <span data-calendar-edge="end" aria-hidden="true" /></>}
                  </button>
                ))}
                {((buckets.get(key)?.length ?? 0) > 3 || week.hidden[weekday] > 0) && (
                  <button
                    className="more-events"
                    onClick={event => {
                      event.stopPropagation();
                      setDay(key);
                      requestAnimationFrame(() =>
                        document
                          .querySelector(".day-detail")
                          ?.scrollIntoView({ block: "nearest" }),
                      );
                    }}
                  >+{Math.max(0, (buckets.get(key)?.length ?? 0) - 3) + week.hidden[weekday]}{t("개")}</button>
                )}
              </div>
            </div>
            ))}
            {week.segments.length > 0 && <div className="calendar-week-ranges">
              {week.segments.map(segment => (
                <button type="button" key={segment.event.key} data-calendar-move={segment.event.key}
                  {...contextActions(segment.event, week.days[segment.from])}
                  data-drag-source={preview?.event?.key === segment.event.key || undefined}
                  className={`calendar-event calendar-span${segment.event.completed ? " completed" : ""}`}
                  data-continues-before={segment.start < week.days[0] || undefined}
                  data-continues-after={segment.end > week.days[6] || undefined}
                  style={{ gridColumn: `${segment.from + 1} / ${segment.to + 2}`, gridRow: segment.lane + 1,
                    "--event-color": segment.event.type_color || "var(--accent)" } as CSSProperties}
                  title={`${segment.event.title} (${segment.start} – ${segment.end})`}
                  onClick={event => open(segment.event,
                    (event.detail && calendarGrid.current &&
                      calendarCellAt(calendarGrid.current, event.clientX, event.clientY)?.dataset.calendarDate) || week.days[segment.from])}>
                  <i /><span className="calendar-event-title">{segment.event.title}</span>
                  {segment.start >= week.days[0] && <span data-calendar-edge="start" aria-hidden="true" />}
                  {segment.end <= week.days[6] && <span data-calendar-edge="end" aria-hidden="true" />}
                </button>
              ))}
            </div>}
            </div>
          ))}
          {preview && <div className="calendar-drag-layer" aria-hidden="true">
            {preview.bars.map((bar, index) => <div key={index} className="calendar-event calendar-span calendar-drag-bar"
              data-continues-before={bar.continuesBefore || undefined} data-continues-after={bar.continuesAfter || undefined}
              style={{ width: bar.width, transform: `translate3d(${bar.x}px, ${bar.y}px, 0)`,
                "--event-color": preview.event?.type_color || "var(--accent)" } as CSSProperties}>
              <i /><span className="calendar-event-title">{preview.event?.title ?? t("일정 추가")}</span>
            </div>)}
          </div>}
        </div>
      </section>
      <section className="glass day-detail">
        <div className="section-heading">
          <h2>
            {Number(day.slice(5, 7))}{t("월")}{" "}{Number(day.slice(8))}{t("일")}{" "}</h2>
          <button className="text-button" onClick={() => onAdd(day)}>
            <Plus size={16} />{t("일정 추가")}{" "}</button>
        </div>
        <EventRows events={shownEvents} />
      </section>
      {menu && <CalendarEventMenu menu={menu} onClose={() => setMenu(null)}
        onEdit={() => { setMenu(null); open(menu.event, menu.day); }}
        onDelete={() => { setRemove(menu); setMenu(null); }} />}
      {remove && <DeleteEventDialog event={remove.event} onDeleted={() => setRemove(null)}
        onClose={() => {
          setRemove(null);
          requestAnimationFrame(() => remove.anchor.focus({ preventScroll: true }));
        }} />}
    </>
  );
}

function DeleteEventDialog({ event, onClose, onDeleted }: {
  event: Pick<EventItem, "key" | "title">;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const { mutate } = useCalix();
  const [deleting, setDeleting] = useState(false);
  return <Modal title={t("정말 삭제하시겠습니까?")} onClose={() => { if (!deleting) onClose(); }}>
    <p>{event.title}</p>
    <div className="dialog-actions">
      <button autoFocus disabled={deleting} onClick={onClose}>{t("취소")}</button>
      <button className="danger" disabled={deleting} onClick={() => {
        setDeleting(true);
        void mutate("event.delete", { key: event.key }).then(onDeleted).catch(() => setDeleting(false));
      }}>{t("삭제")}</button>
    </div>
  </Modal>;
}

function ManualEventDates({ start, due, disabled, onChange }: {
  start: string;
  due: string;
  disabled: boolean;
  onChange: (start: string, due: string) => void;
}) {
  const dueLabel = t(start ? "종료일" : "기한");
  return <div className="form-grid">
    <label>{t("시작일")}
      <DateField label={t("시작일")} value={start} allowClear disabled={disabled}
        onChange={next => onChange(next, due || (next ? `${next}T23:59` : ""))} />
    </label>
    <label>{dueLabel}
      <DateField label={dueLabel} value={due} withTime allowClear disabled={disabled}
        onChange={next => onChange(next ? start : "", next)} />
    </label>
  </div>;
}

function EventDetails({
  event,
  onClose,
}: {
  event: EventItem;
  onClose: () => void;
}) {
  useLanguage();
  const { data, mutate, notify, draft } = useCalix();
  const [saving, setSaving] = useState(false),
    [dirty, setDirty] = useState(false),
    [title, setTitle] = useState(event.title),
    [note, setNote] = useState(event.note),
    [type, setType] = useState(event.type_id?.toString() || ""),
    [start, setStart] = useState(event.start_at ? dateKey(event.start_at) : ""),
    [due, setDue] = useState(localInput(event.due_at)),
    [remove, setRemove] = useState(false);
  const added = data.tasks.some((t) => t.source_key === event.key);
  const pending = useRef<Promise<boolean> | null>(null),
    saveRef = useRef<() => Promise<void>>(async () => {});
  const save = () => {
    if (pending.current) return pending.current;
    const task = (async () => {
      setSaving(true);
      try {
        await mutate("event.save", {
          key: event.key,
          title,
          note,
          type_id: type ? Number(type) : null,
          ...(event.manual ? { start_at: start ? `${start}T00:00:00+09:00` : null,
            due_at: due ? due + ":00+09:00" : null } : {}),
        });
        setDirty(false);
        notify("저장됨");
        return true;
      } catch {
        return false;
      } finally {
        setSaving(false);
      }
    })();
    pending.current = task;
    void task.finally(() => {
      pending.current = null;
    });
    return task;
  };
  saveRef.current = async () => {
    if ((dirty || pending.current) && !(await save()))
      throw new Error("일정을 저장하지 못했습니다.");
  };
  useEffect(() => {
    const guard = () => saveRef.current();
    draft.current = guard;
    return () => {
      if (draft.current === guard) draft.current = null;
    };
  }, [draft]);
  const close = () => {
    if (!dirty) onClose();
    else
      void save().then((ok) => {
        if (ok) onClose();
      });
  };
  return (
    <>
      <Modal title={t("상세 일정")} onClose={close}>
        <div className="detail-context">
          <TypeBadge event={event} />
          <span>{event.course_name || t("개인 일정")}</span>
          <span className={isExcusedMovie(event) ? "count-pill attendance-status excused" : "count-pill"}>{status(event)}</span>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <label>{t("일정 이름")}{" "}<input
              autoFocus
              maxLength={200}
              required
              disabled={saving}
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                setDirty(true);
              }}
            />
          </label>
          {event.manual ? (
              <ManualEventDates start={start} due={due} disabled={saving}
                onChange={(nextStart, nextDue) => {
                  setStart(nextStart);
                  setDue(nextDue);
                  setDirty(true);
                }} />
            ) : (
              <div className="detail-due"><CalendarDays size={17} />{dueText(event.due_at)}</div>
            )}
          {event.kind === "assignment" && event.completed && event.lms_data && (
            <section className="submission-feedback">
              <h3>{status(event)}</h3>
              {event.lms_data.grade && (
                <p>{t("평가")}{" "}<strong>{event.lms_data.grade}</strong>
                </p>
              )}
              {event.lms_data.feedback_available === false && (
                <p className="muted">{t("코멘트 확인 실패, 다시 동기화")}{" "}</p>
              )}
              {event.lms_data.rubric?.map((r, i) => (
                <blockquote key={`rubric-${i}`}>
                  <strong>{r.title}</strong>
                  <p>{r.text}</p>
                </blockquote>
              ))}
              {event.lms_data.comments?.map((c, i) => (
                <blockquote key={i}>
                  <p>{c.text}</p>
                  <footer>
                    {c.author || t("작성자 미표시")}
                    {c.created_at ? ` / ${dueText(c.created_at)}` : ""}
                  </footer>
                </blockquote>
              ))}
            </section>
          )}
          <label>{t("유형")}{" "}<select
              disabled={saving}
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setDirty(true);
              }}
            >
              {!event.manual && (
                <option value="">
                  {event.kind === "movie" ? t("영상") : t("과제")}{" "}{t("(기본)")}{" "}</option>
              )}
              {data.types.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>{t("메모")}{" "}<textarea
              aria-label={t("메모")}
              rows={5}
              disabled={saving}
              maxLength={20000}
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
                setDirty(true);
              }}
              placeholder={t("메모")}
            />
          </label>
          {!event.manual && (
            <button
              type="button"
              className="import-single"
              disabled={added || saving}
              onClick={() =>
                void (async () => {
                  if (dirty && !(await save())) return;
                  await mutate("checklist.import", { keys: [event.key] });
                  notify("체크리스트에 추가됨");
                })().catch(() => {})
              }
            >
              {added ? <Check size={17} /> : <Plus size={17} />}{" "}
              {added ? t("체크리스트에 추가됨") : t("체크리스트에 추가")}
            </button>
          )}
          <div className="dialog-actions">
            {event.url && (
              <button
                type="button"
                onClick={() =>
                  rpc("event.open", { key: event.key }).catch((e) =>
                    notify(e.message, true),
                  )
                }
              >{t("원본 열기")}{" "}<ArrowUpRight size={15} />
              </button>
            )}
            {event.manual && (
              <button
                type="button"
                className="danger"
                onClick={() => setRemove(true)}
              >{t("삭제")}{" "}</button>
            )}
            {event.manual && (
              <button
                type="button"
                onClick={() =>
                  void mutate("event.complete", {
                    key: event.key,
                    completed: !event.completed,
                  }).catch(() => {})
                }
              >
                {event.completed ? t("완료 취소") : t("완료")}
              </button>
            )}
            <span />
            {dirty && <small>{t("수정 중")}</small>}
            <button type="submit" className="primary" disabled={saving}>
              {saving ? t("저장 중") : t("저장")}
            </button>
          </div>
        </form>
      </Modal>
      {remove && (
        <DeleteEventDialog event={{ key: event.key, title }} onClose={() => setRemove(false)} onDeleted={onClose} />
      )}
    </>
  );
}
function AddEvent({
  initialDate,
  initialStart,
  onClose,
}: {
  initialDate: string;
  initialStart?: string;
  onClose: () => void;
}) {
  useLanguage();
  const { data, mutate, draft } = useCalix();
  const [saving, setSaving] = useState(false);
  const [start, setStart] = useState(initialStart ?? "");
  const [due, setDue] = useState(`${initialDate}T23:59`);
  const formRef = useRef<HTMLFormElement>(null),
    pending = useRef<Promise<unknown> | null>(null),
    saveRef = useRef<() => Promise<void>>(async () => {});
  const save = () => {
    if (pending.current) return pending.current;
    const element = formRef.current;
    if (!element || !element.reportValidity())
      return Promise.reject(new Error("일정 이름을 입력하세요."));
    const form = new FormData(element);
    setSaving(true);
    const task = mutate("event.add", {
      title: form.get("title"),
      type_id: Number(form.get("type")),
      course_id: Number(form.get("course")),
      start_at: start ? `${start}T00:00:00+09:00` : null,
      due_at: due ? `${due}:00+09:00` : null,
      note: form.get("note"),
    })
      .then(onClose)
      .finally(() => {
        pending.current = null;
        setSaving(false);
      });
    pending.current = task;
    return task;
  };
  saveRef.current = async () => {
    if (pending.current) {
      await pending.current;
      return;
    }
    const element = formRef.current;
    if (!element) return;
    const form = new FormData(element);
    if (
      String(form.get("title") || "").trim() ||
      String(form.get("note") || "").trim()
    )
      await save();
  };
  useEffect(() => {
    const guard = () => saveRef.current();
    draft.current = guard;
    return () => {
      if (draft.current === guard) draft.current = null;
    };
  }, [draft]);
  return (
    <Modal title={t("일정 추가")} onClose={onClose}>
      <form
        ref={formRef}
        onSubmit={(e) => {
          e.preventDefault();
          void save().catch(() => {});
        }}
      >
        <label>{t("일정 이름")}{" "}<input
            name="title"
            autoFocus
            required
            maxLength={200}
            placeholder={t("일정 이름")}
          />
        </label>
        <div className="form-grid">
          <label>{t("유형")}{" "}<select name="type">
              {data.types.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>{t("과목")}{" "}<select name="course">
              <option value="0">{t("개인 일정")}</option>
              {data.courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <ManualEventDates start={start} due={due} disabled={saving}
          onChange={(nextStart, nextDue) => { setStart(nextStart); setDue(nextDue); }} />
        <label>{t("메모")}{" "}<textarea name="note" rows={4} maxLength={20000} />
        </label>
        <div className="dialog-actions">
          <span />
          <button type="button" onClick={onClose}>{t("취소")}{" "}</button>
          <button className="primary" disabled={saving}>{t("추가")}{" "}</button>
        </div>
      </form>
    </Modal>
  );
}
