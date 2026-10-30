import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
  memo,
  type ReactNode,
  type RefObject,
} from "react";
import {
  Home,
  CalendarDays,
  CheckSquare,
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
} from "lucide-react";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { WindowControls } from "./WindowControls";
import { rpc, subscribe, stopEngine } from "./bridge";
import {
  dateKey,
  dueText,
  localInput,
  monthGrid,
  remaining,
  shiftMonth,
  status,
  weekdays,
} from "./dates";
import type { Snapshot, EventItem, Page } from "./types";
import { ChecklistPage, TimetablePage, SettingsPage } from "./Workspaces";
import { DiaryPage } from "./Diary";
const CachedDiary = memo(DiaryPage),
  CachedChecklist = memo(ChecklistPage);
import { finishStartup } from "./startup";
type ContextValue = {
  data: Snapshot;
  mutate: (
    method: string,
    params?: Record<string, unknown>,
  ) => Promise<unknown>;
  notify: (message: string) => void;
  openEvent: (key: string) => void;
  leave: RefObject<(() => Promise<void>) | null>;
  draft: RefObject<(() => Promise<void>) | null>;
  requestInstall: () => void;
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
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "wide" : ""}`}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button
          className="icon-button"
          title="닫기"
          aria-label="닫기"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
export function TypeBadge({ event }: { event: EventItem }) {
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
          ? "영상"
          : event.kind === "assignment"
            ? "과제"
            : "일정")}
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
  const { openEvent } = useCalix(),
    [index, setIndex] = useState(0);
  const count = Math.ceil(events.length / limit),
    page = Math.min(index, Math.max(0, count - 1)),
    start = limit < 50 ? 0 : page * limit;
  return (
    <div className="event-table">
      <div className="event-table-head">
        <span>유형</span>
        <span>과목</span>
        <span>일정</span>
        <span>기한</span>
        <span>남은 시간</span>
      </div>
      {events.slice(start, start + limit).map((e) => (
        <button
          key={e.key}
          className={`event-row ${e.completed ? "completed" : ""}`}
          onClick={() => openEvent(e.key)}
        >
          <TypeBadge event={e} />
          <span className="muted ellipsis">{e.course_name || "개인 일정"}</span>
          <span className="event-name ellipsis">{e.title}</span>
          <span className="muted nowrap">{dueText(e.due_at)}</span>
          <span
            className={
              !e.completed &&
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
      {!events.length && <div className="empty">일정이 없습니다.</div>}
      {limit >= 50 && count > 1 && (
        <div className="pagination">
          <span>
            {start + 1}–{Math.min(start + limit, events.length)} /{" "}
            {events.length}
          </span>
          <button
            className="icon-button"
            aria-label="이전 목록"
            disabled={!page}
            onClick={() => setIndex(page - 1)}
          >
            <ChevronLeft size={17} />
          </button>
          <button
            className="icon-button"
            aria-label="다음 목록"
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
  ["checklist", "체크리스트", CheckSquare],
  ["diary", "일기장", BookOpen],
];
export function App() {
  const [data, setData] = useState<Snapshot | null>(null),
    [error, setError] = useState(""),
    [page, setPage] = useState<Page>("home"),
    [selected, setSelected] = useState<string | null>(null),
    [addDate, setAddDate] = useState<string | null>(null),
    [toast, setToast] = useState(""),
    [query, setQuery] = useState(""),
    [busy, setBusy] = useState(false),
    [loggedIn, setLoggedIn] = useState(false),
    [credits, setCredits] = useState(false),
    [exit, setExit] = useState(false),
    [install, setInstall] = useState(false);
  const draft = useRef<(() => Promise<void>) | null>(null),
    leave = useRef<(() => Promise<void>) | null>(null),
    searchRef = useRef<HTMLInputElement>(null),
    toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (data || error) finishStartup();
  }, [data, error]);
  const notify = useCallback((message: string) => {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 4500);
  }, []);
  const finishEditing = async () => {
    if (draft.current) await draft.current();
    if (leave.current) await leave.current();
  };
  const openLogin = async () => {
    if (!isTauri()) {
      notify("로그인은 Windows 앱에서 진행합니다.");
      return;
    }
    await Promise.all([rpc("session.prepare"), invoke("auth_open", {
      theme: document.documentElement.dataset.theme || "pink",
      font: document.documentElement.dataset.font || "pretendard",
    })]);
  };
  const refresh = useCallback(async () => {
    const snapshot = await rpc<Snapshot>("bootstrap");
    setData(snapshot);
    setError("");
  }, []);
  const mutate = useCallback(
    async (method: string, params: Record<string, unknown> = {}) => {
      let result;
      try {
        result = await rpc(method, params);
      } catch (e) {
        notify((e as Error).message);
        throw e;
      }
      try {
        await refresh();
      } catch {
        notify("저장됨 / 목록을 다시 불러오지 못했습니다.");
      }
      return result;
    },
    [refresh, notify],
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
    void rpc("session.restore").catch(() => {});
    rpc<{ loggedIn: boolean }>("engine.state")
      .then((value) => {
        if (alive) setLoggedIn(value.loggedIn);
      })
      .catch(() => {});
    const unsubscribe = subscribe((message) => {
      if (message.event === "data-changed") {
        setBusy(false);
        void refresh().catch((e) => notify(e.message));
      }
      if (message.event === "auth-required")
        void openLogin().catch((error) => notify(String(error)));
      if (message.event === "auth-cancelled") setBusy(false);
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
      if (message.event === "notice") notify(String(message.message));
      if (message.event === "update-ready") {
        setInstall(true);
        setExit(true);
      }
      if (message.event === "authentication")
        setLoggedIn(Boolean(message.loggedIn));
      if (message.event === "sync-progress") {
        notify(String(message.message));
        if (String(message.message).includes("완료")) setBusy(false);
      }
      if (message.event === "sync-error") {
        setBusy(false);
        notify(String(message.message));
      }
    });
    return () => {
      alive = false;
      unsubscribe();
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, []);
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
      [
        "app:hidden",
        () => {
          void finishEditing().catch((e) => notify(e.message));
        },
      ],
      [
        "auth:cookies",
        (message: { payload: unknown }) => {
          void rpc(
            "session.import",
            message.payload as Record<string, unknown>,
          ).catch((error) =>
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
  }, [
    data?.preferences.theme,
    data?.preferences.glass,
    data?.preferences.font_mode,
  ]);
  const navigate = async (next: Page) => {
    try {
      await finishEditing();
      setSelected(null);
      setAddDate(null);
      setPage(next);
    } catch (e) {
      notify((e as Error).message);
    }
  };

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
  const found = useMemo(
    () =>
      query.trim()
        ? sorted
            .filter((e) =>
              (e.title + " " + e.course_name)
                .toLocaleLowerCase()
                .includes(query.trim().toLocaleLowerCase()),
            )
            .slice(0, 8)
        : [],
    [query, sorted],
  );
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
            data,
            mutate,
            notify,
            openEvent,
            leave,
            draft,
            requestInstall: () => {
              setInstall(true);
              setExit(true);
            },
          }
        : null,
    [data, mutate, notify, openEvent],
  );
  return (
    <div className="app-shell">
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
          <span>Calix</span>
          <small>1.4</small>
        </a>
        <div className="nav-label">워크스페이스</div>
        <nav>
          {navigation.map(([id, title, Icon]) => (
            <button
              key={id}
              className={page === id ? "active" : ""}
              onClick={() => void navigate(id)}
              title={title}
            >
              <Icon size={19} />
              <span>{title}</span>
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
            title="설정"
          >
            <Settings size={19} />
            <span>설정</span>
          </button>
          <button
            className="creator"
            onClick={() => setCredits(true)}
            title="크레딧"
          >
            <img src="/assets/profile-avatar.png" alt="" />
            <span>
              <strong>Lutté Laurent</strong>
              <small>Calix</small>
            </span>
            <ArrowUpRight size={15} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar" data-tauri-drag-region>
          <div className="breadcrumb" data-tauri-drag-region>
            Calix <span>/</span>{" "}
            {navigation.find((n) => n[0] === page)?.[1] || "설정"}
          </div>
          <div className="top-actions">
            <div className="search-box">
              <Search size={16} />
              <input
                ref={searchRef}
                placeholder="일정 검색"
                aria-label="일정 검색"
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
                  {!found.length && <p>검색 결과가 없습니다.</p>}
                </div>
              )}
            </div>
            <button
              className="icon-button"
              title={busy ? "동기화 중" : "동기화"}
              aria-label="동기화"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                rpc("sync").catch((e) => {
                  setBusy(false);
                  notify(e.message);
                });
              }}
            >
              <RefreshCw size={18} className={busy ? "spin" : ""} />
            </button>
            <button
              className="quiet"
              onClick={() =>
                void (async () => {
                  if (loggedIn) {
                    if (isTauri()) await invoke("auth_logout");
                    await rpc("session.logout");
                  } else await openLogin();
                })().catch((error) => notify(String(error)))
              }
            >
              {loggedIn ? <LogOut size={16} /> : <LogIn size={16} />}
              <span>{loggedIn ? "로그아웃" : "로그인"}</span>
            </button>
            <button
              className="primary"
              onClick={() => setAddDate(today)}
              disabled={!data}
            >
              <Plus size={17} />
              일정 추가
            </button>
            <button
              className="icon-button"
              title="종료"
              aria-label="종료"
              onClick={() => setExit(true)}
            >
              <Power size={16} />
            </button>
            <WindowControls />
          </div>
        </header>
        <main>
          {!data ? (
            <div className="loading-state">
              {error ? (
                <>
                  <h2>연결을 확인하세요.</h2>
                  <p>{error}</p>
                  <button
                    onClick={() =>
                      void refresh().catch((e) => setError(e.message))
                    }
                  >
                    다시 시도
                  </button>
                </>
              ) : (
                <>
                  <div className="skeleton hero-skeleton" />
                  <div className="skeleton content-skeleton" />
                </>
              )}
            </div>
          ) : (
            <Context.Provider value={context}>
              {page === "home" && (
                <>
                  <section className="welcome">
                    <div>
                      <p className="eyebrow">
                        {new Intl.DateTimeFormat("ko-KR", {
                          timeZone: "Asia/Seoul",
                          month: "long",
                          day: "numeric",
                          weekday: "long",
                        }).format(new Date())}
                      </p>
                      <h1>오셨군요!</h1>
                      <p className="welcome-note">
                        {todayEvents.length
                          ? `오늘 마감 일정 ${todayEvents.length}개`
                          : "오늘 마감 일정 없음"}
                      </p>
                    </div>
                    <div className="welcome-mark" aria-hidden="true">
                      <img src="/assets/icons/calix.svg" alt="" />
                    </div>
                  </section>
                  <section className="stats">
                    <button
                      className="stat glass"
                      onClick={() => void navigate("calendar")}
                    >
                      <span>
                        오늘까지 할 일 <ArrowUpRight size={18} />
                      </span>
                      <strong>
                        {todayEvents.length}
                        <small>건</small>
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
                      <span>
                        남은 일정 <ArrowUpRight size={18} />
                      </span>
                      <strong>
                        {pending.length}
                        <small>개</small>
                      </strong>
                      <div className="mini-tags">
                        <span>
                          과제{" "}
                          {
                            pending.filter((e) => e.kind === "assignment")
                              .length
                          }
                        </span>
                        <span>
                          영상{" "}
                          {pending.filter((e) => e.kind === "movie").length}
                        </span>
                      </div>
                    </button>
                  </section>
                  <div className="home-content">
                    <section className="glass upcoming-panel">
                      <div className="section-heading">
                        <h2>남은 일정</h2>
                        <button
                          className="text-button"
                          onClick={() => void navigate("calendar")}
                        >
                          전체 보기 <ArrowUpRight size={15} />
                        </button>
                      </div>
                      <EventRows events={pending} limit={7} />
                    </section>
                    <section className="glass today-panel">
                      <div className="section-heading">
                        <h2>오늘 할 일</h2>
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
                          <p>오늘 마감 일정이 없습니다.</p>
                        </div>
                      )}
                      <div className="today-footer">
                        <CalendarDays size={17} />
                        {today.slice(5).replace("-", "월 ")}일
                      </div>
                    </section>
                  </div>
                </>
              )}
              {page === "calendar" && (
                <CalendarPage events={sorted} onAdd={setAddDate} />
              )}
              {(page === "assignments" || page === "videos") && (
                <>
                  <div className="page-heading">
                    <div>
                      <p className="eyebrow">수업 일정</p>
                      <h1>{page === "assignments" ? "과제" : "영상"}</h1>
                    </div>
                    <span className="count-pill">
                      {
                        sorted.filter(
                          (e) =>
                            e.kind ===
                            (page === "assignments" ? "assignment" : "movie"),
                        ).length
                      }
                      개
                    </span>
                  </div>
                  <section className="glass list-panel">
                    <EventRows
                      events={sorted.filter(
                        (e) =>
                          e.kind ===
                          (page === "assignments" ? "assignment" : "movie"),
                      )}
                    />
                  </section>
                </>
              )}
              <div hidden={page !== "checklist"}>
                <CachedChecklist />
              </div>
              {page === "timetable" && <TimetablePage />}
              <div hidden={page !== "diary"}>
                <CachedDiary active={page === "diary"} />
              </div>
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
                  initialDate={addDate}
                  onClose={() => setAddDate(null)}
                />
              )}
            </Context.Provider>
          )}
        </main>
        <footer className="statusbar">
          <span className={`connection-dot ${loggedIn ? "online" : ""}`} />
          <span>
            {busy
              ? "동기화 중"
              : data?.lastSync
                ? `최근 동기화 ${dueText(data.lastSync)}`
                : "동기화 기록 없음"}
          </span>
          <span className="status-version">v1.4.1</span>
        </footer>
      </div>
      {toast && (
        <div className="toast" role="status">
          <Check size={17} />
          {toast}
          <button aria-label="알림 닫기" onClick={() => setToast("")}>
            <X size={15} />
          </button>
        </div>
      )}
      {credits && (
        <Modal title="Calix" onClose={() => setCredits(false)}>
          <div className="credit-profile">
            <img src="/assets/profile-avatar.png" alt="Lutté Laurent" />
            <h2>Lutté Laurent</h2>
            <p>Calix 1.4.1</p>
          </div>
          <div className="credit-links">
            <a
              href="https://github.com/luttechan/Calix"
              target="_blank"
              rel="noreferrer"
              onClick={(e) => {
                if (isTauri()) {
                  e.preventDefault();
                  void rpc("app.open", { page: "github" }).catch((error) =>
                    notify(error.message),
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
                    notify(error.message),
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
      {exit && (
        <Modal
          title={install ? "업데이트를 설치하시겠습니까?" : "종료하시겠습니까?"}
          onClose={() => {
            setExit(false);
            setInstall(false);
          }}
        >
          <div className="dialog-actions">
            <span />
            <button
              onClick={() => {
                setExit(false);
                setInstall(false);
              }}
            >
              취소
            </button>
            <button
              className="primary"
              onClick={() =>
                void (async () => {
                  await finishEditing();
                  await stopEngine(install);
                  if (isTauri()) await invoke("quit_app");
                  else setExit(false);
                })().catch((e) => notify(e.message))
              }
            >
              {install ? "설치하고 종료" : "저장하고 종료"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
function CalendarPage({
  events,
  onAdd,
}: {
  events: EventItem[];
  onAdd: (date: string) => void;
}) {
  const { data, openEvent, notify } = useCalix(),
    [month, setMonth] = useState(dateKey().slice(0, 7)),
    [day, setDay] = useState(dateKey()),
    [kind, setKind] = useState("all");
  const [dates, setDates] = useState({
    holidays: data.holidays,
    specialDates: data.specialDates,
  });
  useEffect(() => {
    let active = true;
    rpc<{
      holidays: Record<string, string>;
      specialDates: Record<string, string>;
    }>("calendar.year", { year: Number(month.slice(0, 4)) })
      .then((value) => {
        if (active) setDates(value);
      })
      .catch((e) => {
        if (active) notify(e.message);
      });
    return () => {
      active = false;
    };
  }, [month.slice(0, 4), data.holidays, data.specialDates]);
  const buckets = useMemo(() => {
    const result = new Map<string, EventItem[]>();
    for (const e of events) {
      if (!e.due_at || (kind !== "all" && e.kind !== kind)) continue;
      const key = dateKey(e.due_at);
      const group = result.get(key) || [];
      group.push(e);
      result.set(key, group);
    }
    return result;
  }, [events, kind]);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">나의 일정</p>
          <h1>
            {Number(month.slice(0, 4))}년 {Number(month.slice(5))}월
          </h1>
        </div>
        <div className="toolbar">
          <button
            className="icon-button"
            title="이전 달"
            onClick={() => setMonth(shiftMonth(month, -1))}
          >
            <ChevronLeft size={19} />
          </button>
          <button
            onClick={() => {
              setMonth(dateKey().slice(0, 7));
              setDay(dateKey());
            }}
          >
            오늘
          </button>
          <button
            className="icon-button"
            title="다음 달"
            onClick={() => setMonth(shiftMonth(month, 1))}
          >
            <ChevronRight size={19} />
          </button>
        </div>
      </div>
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
              onClick={() => setKind(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="muted">
          {
            events.filter(
              (e) => e.due_at && dateKey(e.due_at).startsWith(month),
            ).length
          }
          개 일정
        </span>
      </div>
      <section className="glass calendar-panel">
        <div className="weekday-row">
          {weekdays.map((name, i) => (
            <span key={name} className={i === 6 ? "sunday" : ""}>
              {name}
            </span>
          ))}
        </div>
        <div className="month-grid">
          {monthGrid(month).map((key) => (
            <div
              key={key}
              className={`day-cell ${key.startsWith(month) ? "" : "outside"} ${key === day ? "day-selected" : ""}`}
              onClick={() => setDay(key)}
              onDoubleClick={(e) => {
                if (e.target === e.currentTarget) onAdd(key);
              }}
            >
              <div className="day-heading">
                <button
                  aria-label={`${key} 일정 추가`}
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
                    className={`calendar-event ${e.kind} ${e.completed ? "completed" : ""} ${!e.completed && e.kind === "assignment" && e.due_at && new Date(e.due_at).getTime() < Date.now() ? "late" : ""}`}
                    title={`${e.title} / ${status(e)}`}
                    onClick={(click) => {
                      click.stopPropagation();
                      setDay(key);
                      openEvent(e.key);
                    }}
                  >
                    <i />
                    {e.title}
                  </button>
                ))}
                {(buckets.get(key)?.length || 0) > 3 && (
                  <button
                    className="more-events"
                    onClick={() => {
                      setDay(key);
                      requestAnimationFrame(() =>
                        document
                          .querySelector(".day-detail")
                          ?.scrollIntoView({ block: "nearest" }),
                      );
                    }}
                  >
                    +{buckets.get(key)!.length - 3}개
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="glass day-detail">
        <div className="section-heading">
          <h2>
            {Number(day.slice(5, 7))}월 {Number(day.slice(8))}일
          </h2>
          <button className="text-button" onClick={() => onAdd(day)}>
            <Plus size={16} />
            일정 추가
          </button>
        </div>
        <EventRows events={buckets.get(day) || []} />
      </section>
    </>
  );
}
function EventDetails({
  event,
  onClose,
}: {
  event: EventItem;
  onClose: () => void;
}) {
  const { data, mutate, notify, draft } = useCalix();
  const [saving, setSaving] = useState(false),
    [dirty, setDirty] = useState(false),
    [title, setTitle] = useState(event.title),
    [note, setNote] = useState(event.note),
    [type, setType] = useState(event.type_id?.toString() || ""),
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
          ...(event.manual ? { due_at: due ? due + ":00+09:00" : null } : {}),
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
      <Modal title="상세 일정" onClose={close}>
        <div className="detail-context">
          <TypeBadge event={event} />
          <span>{event.course_name || "개인 일정"}</span>
          <span className="count-pill">{status(event)}</span>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <label>
            일정 이름
            <input
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
          <div className="detail-due">
            <CalendarDays size={17} />
            {event.manual ? (
              <input
                type="datetime-local"
                aria-label="기한"
                value={due}
                disabled={saving}
                onChange={(e) => {
                  setDue(e.target.value);
                  setDirty(true);
                }}
              />
            ) : (
              dueText(event.due_at)
            )}
          </div>
          <label>
            유형
            <select
              disabled={saving}
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setDirty(true);
              }}
            >
              {!event.manual && (
                <option value="">
                  {event.kind === "movie" ? "영상" : "과제"} (기본)
                </option>
              )}
              {data.types.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            메모
            <textarea
              aria-label="메모"
              rows={5}
              disabled={saving}
              maxLength={20000}
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
                setDirty(true);
              }}
              placeholder="메모"
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
              {added ? "체크리스트에 추가됨" : "체크리스트에 추가"}
            </button>
          )}
          <div className="dialog-actions">
            {event.url && (
              <button
                type="button"
                onClick={() =>
                  rpc("event.open", { key: event.key }).catch((e) =>
                    notify(e.message),
                  )
                }
              >
                원본 열기 <ArrowUpRight size={15} />
              </button>
            )}
            {event.manual && (
              <button
                type="button"
                className="danger"
                onClick={() => setRemove(true)}
              >
                삭제
              </button>
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
                {event.completed ? "완료 취소" : "완료"}
              </button>
            )}
            <span />
            {dirty && <small>수정 중</small>}
            <button type="submit" className="primary" disabled={saving}>
              {saving ? "저장 중" : "저장"}
            </button>
          </div>
        </form>
      </Modal>
      {remove && (
        <Modal title="정말 삭제하시겠습니까?" onClose={() => setRemove(false)}>
          <p>{title}</p>
          <div className="dialog-actions">
            <span />
            <button onClick={() => setRemove(false)}>취소</button>
            <button
              className="primary"
              onClick={() =>
                void mutate("event.delete", { key: event.key })
                  .then(onClose)
                  .catch(() => {})
              }
            >
              삭제
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
function AddEvent({
  initialDate,
  onClose,
}: {
  initialDate: string;
  onClose: () => void;
}) {
  const { data, mutate, draft } = useCalix();
  const [saving, setSaving] = useState(false);
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
      due_at: form.get("due") ? String(form.get("due")) + ":00+09:00" : null,
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
    <Modal title="일정 추가" onClose={onClose}>
      <form
        ref={formRef}
        onSubmit={(e) => {
          e.preventDefault();
          void save().catch(() => {});
        }}
      >
        <label>
          일정 이름
          <input
            name="title"
            autoFocus
            required
            maxLength={200}
            placeholder="일정 이름"
          />
        </label>
        <div className="form-grid">
          <label>
            유형
            <select name="type">
              {data.types.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            과목
            <select name="course">
              <option value="0">개인 일정</option>
              {data.courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          기한
          <input
            type="datetime-local"
            name="due"
            defaultValue={`${initialDate}T23:59`}
          />
        </label>
        <label>
          메모
          <textarea name="note" rows={4} maxLength={20000} />
        </label>
        <div className="dialog-actions">
          <span />
          <button type="button" onClick={onClose}>
            취소
          </button>
          <button className="primary" disabled={saving}>
            추가
          </button>
        </div>
      </form>
    </Modal>
  );
}
