import { useMemo, useState } from "react";
import {
  Plus,
  Trash2,
  Download,
  Check,
  Palette,
  CalendarDays,
  CalendarRange,
  SlidersHorizontal,
  ArrowUpRight,
  Bell,
  ShieldCheck,
  Terminal,
  UserRound,
} from "lucide-react";
import { Modal, TypeBadge, useCalix } from "./App";
import { rpc } from "./bridge";
import { InlineCell } from "./InlineCell";
import { ChecklistDeadline, DateField } from "./ChecklistDeadline";
import { useChecklistWidths } from "./checklistWidths";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { UpdateDialog } from "./UpdateDialog";
import { ProfileSettings, ResetSettings } from "./Profile";
import { ReminderSettingsPanel } from "./Reminders";
import { DevPanel } from "./DevPanel";
import { SecuritySettings } from "./Security";
import { SemesterSettings } from "./SemesterSettings";
import { dateKey, dueText, status, weekdays } from "./dates";
import type { Task, Preferences } from "./types";
const taskCollator = new Intl.Collator("ko", { numeric: true });
export function ChecklistPage() {
  const { data, mutate, notify } = useCalix();
  const columns = useChecklistWidths();
  const [listPage, setListPage] = useState(0),
    [section, setSection] = useState(1),
    [search, setSearch] = useState(""),
    [pending, setPending] = useState(false),
    [batch, setBatch] = useState(false),
    [remove, setRemove] = useState<Task | null>(null),
    [sectionEdit, setSectionEdit] = useState(false),
    [statusEdit, setStatusEdit] = useState(false),
    [sort, setSort] = useState<{ key: keyof Task; descending: boolean }>({
      key: "due_at",
      descending: false,
    });
  const rows = useMemo(
    () =>
      data.tasks
        .filter(
          (t) =>
            t.section_id === section &&
            (!pending || t.status_kind === "open") &&
            [t.title, t.category, t.role, t.professor, t.note]
              .join(" ")
              .toLocaleLowerCase()
              .includes(search.toLocaleLowerCase()),
        )
        .sort((a, b) => {
          const x = a[sort.key] ?? "",
            y = b[sort.key] ?? "";
          return (
            taskCollator.compare(String(x), String(y)) *
            (sort.descending ? -1 : 1)
          );
        }),
    [data.tasks, section, search, pending, sort],
  );
  const pageCount = Math.max(1, Math.ceil(rows.length / 25)),
    currentPage = Math.min(listPage, pageCount - 1),
    visibleRows = rows.slice(currentPage * 25, currentPage * 25 + 25);
  const suggestions = useMemo(() => {
    const unique = (values: string[]) => [...new Set(values.filter(Boolean))];
    return {
      category: unique([...data.tasks.map((task) => task.category), ...data.courses.map((course) => course.name)]),
      role: unique([...data.tasks.map((task) => task.role), "작성", "자료 조사", "발표", "검토"]),
      professor: unique([...data.tasks.map((task) => task.professor), ...data.sessions.map((session) => session.professor)]),
    };
  }, [data.tasks, data.courses, data.sessions]);
  const save = (task: Task, field: string, value: unknown) => {
    if (task[field as keyof Task] !== value)
      void mutate("checklist.save", { id: task.id, field, value }).catch(
        () => {},
      );
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>체크리스트</h1>
        </div>
        <button
          className="primary"
          onClick={() =>
            void mutate("checklist.add", { section_id: section }).catch(
              () => {},
            )
          }
        >
          <Plus size={17} />할 일 추가
        </button>
      </div>
      <div className="checklist-top">
        <div className="section-tabs">
          {data.sections.map((s) => (
            <button
              className={s.id === section ? "selected" : ""}
              key={s.id}
              onClick={() => setSection(s.id)}
            >
              {s.name}
              <small>
                {data.tasks.filter((t) => t.section_id === s.id).length}
              </small>
            </button>
          ))}
          {data.sections.length < 5 && (
            <button
              className="icon-button"
              aria-label="섹션 추가"
              title="섹션 추가"
              onClick={() => setSectionEdit(true)}
            >
              <Plus size={17} />
            </button>
          )}
        </div>
        <div className="toolbar">
          <button onClick={() => setStatusEdit(true)}>
            <SlidersHorizontal size={15} />
            상태 편집
          </button>
          {section === 1 && (
            <button onClick={() => setBatch(true)}>
              <Download size={15} />
              일괄 가져오기
            </button>
          )}
        </div>
      </div>
      <section className="glass checklist-panel">
        <div className="checklist-tools">
          <input
            aria-label="할 일 검색"
            placeholder="할 일 검색"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={pending}
              onChange={(e) => setPending(e.target.checked)}
            />
            미완료만
          </label>
          <span className="muted">{rows.length}개</span>
        </div>
        <div className="table-scroll">
          <table className="checklist-table" data-resized={Boolean(columns.widths)} style={columns.tableWidth ? {width: columns.tableWidth, minWidth: columns.tableWidth} : undefined}>
            {columns.widths && <colgroup>{columns.widths.map((width, index) => <col key={index} style={{width}} />)}<col style={{width:columns.actionWidth}} /></colgroup>}
            <thead>
              <tr>
                {[
                  ["title", "할 일"],
                  ["due_at", "기한"],
                  ["category", "분류"],
                  ["role", "내 역할"],
                  ["professor", "담당 교수"],
                  ["status_name", "상태"],
                  ["note", "비고"],
                ].map(([key, title], index) => (
                  <th key={key} aria-sort={sort.key === key ? (sort.descending ? "descending" : "ascending") : "none"}>
                    <button
                      onClick={() =>
                        setSort({
                          key: key as keyof Task,
                          descending:
                            sort.key === key ? !sort.descending : false,
                        })
                      }
                    >
                      {title}
                      {sort.key === key ? (
                        <span>{sort.descending ? "↓" : "↑"}</span>
                      ) : null}
                    </button>
                    <span className="checklist-resize" {...columns.handle(index, title)} />
                  </th>
                ))}
                <th className="delete-cell" aria-label="삭제" />
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((task) => (
                <tr key={task.id}>
                  <td>
                    <div className="task-title">
                      <input
                        aria-label={`${task.title} 완료`}
                        type="checkbox"
                        checked={task.status_kind === "done"}
                        onChange={(e) =>
                          void mutate("checklist.toggle", {
                            id: task.id,
                            checked: e.target.checked,
                          }).catch(() => {})
                        }
                      />
                      <InlineCell
                        label="할 일"
                        value={task.title}
                        onCommit={(value) =>
                          save(task, "title", value || "새 할 일")
                        }
                      />
                    </div>
                  </td>
                  <td>
                    <ChecklistDeadline value={task.due_at} onCommit={(value) => save(task, "due_at", value)} />
                  </td>
                  {(["category", "role", "professor"] as const).map((field) => (
                    <td key={field}>
                      <InlineCell
                        label={
                          field === "category"
                            ? "분류"
                            : field === "role"
                              ? "내 역할"
                              : "담당 교수"
                        }
                        value={task[field]}
                        suggestions={suggestions[field]}
                        maxLength={field === "professor" ? 120 : 100}
                        onCommit={(value) => save(task, field, value || "")}
                      />
                    </td>
                  ))}
                  <td>
                    <InlineCell
                      label="상태"
                      value={task.status_id}
                      display={task.status_name}
                      color={task.status_color}
                      options={data.statuses.map((s) => ({
                        value: s.id,
                        label: s.name,
                      }))}
                      onCommit={(value) => save(task, "status_id", value)}
                    />
                  </td>
                  <td>
                    <InlineCell
                      label="비고"
                      value={task.note}
                      maxLength={20000}
                      onCommit={(value) => save(task, "note", value || "")}
                    />
                  </td>
                  <td className="delete-cell">
                    <button
                      className="icon-button row-delete"
                      title="삭제"
                      aria-label={`${task.title} 삭제`}
                      onClick={() => setRemove(task)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <div className="empty">할 일 없음</div>}
        </div>
        {pageCount > 1 && (
          <div className="pagination">
            <span>
              {currentPage + 1} / {pageCount}
            </span>
            <button
              disabled={!currentPage}
              onClick={() => setListPage(currentPage - 1)}
            >
              이전
            </button>
            <button
              disabled={currentPage >= pageCount - 1}
              onClick={() => setListPage(currentPage + 1)}
            >
              다음
            </button>
          </div>
        )}
      </section>
      {batch && <BatchImport onClose={() => setBatch(false)} />}
      {remove && (
        <Modal title="정말 삭제하시겠습니까?" onClose={() => setRemove(null)}>
          <p className="muted">{remove.title}</p>
          <div className="dialog-actions">
            <span />
            <button onClick={() => setRemove(null)}>취소</button>
            <button
              className="primary"
              onClick={() =>
                void mutate("checklist.delete", { id: remove.id })
                  .then(() => {
                    setRemove(null);
                    notify("삭제됨");
                  })
                  .catch(() => {})
              }
            >
              삭제
            </button>
          </div>
        </Modal>
      )}
      {sectionEdit && (
        <Modal title="섹션 추가" onClose={() => setSectionEdit(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const name = new FormData(e.currentTarget).get("name");
              void mutate("section.save", { name })
                .then((id) => {
                  setSection(Number(id));
                  setSectionEdit(false);
                })
                .catch(() => {});
            }}
          >
            <label>
              이름
              <input name="name" autoFocus required maxLength={32} />
            </label>
            <div className="dialog-actions">
              <span />
              <button className="primary">추가</button>
            </div>
          </form>
        </Modal>
      )}
      {statusEdit && (
        <Modal title="상태 편집" onClose={() => setStatusEdit(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void mutate("status.save", {
                id: f.get("id") ? Number(f.get("id")) : null,
                name: f.get("name"),
                color: f.get("color"),
                kind: f.get("kind"),
              })
                .then(() => setStatusEdit(false))
                .catch(() => {});
            }}
          >
            <label>
              상태
              <select
                name="id"
                onChange={(e) => {
                  const s = data.statuses.find(
                    (s) => s.id === Number(e.target.value),
                  );
                  const form = e.currentTarget.form!;
                  for (const [key, value] of Object.entries({
                    name: s?.name || "",
                    color: s?.color || "#af527f",
                    kind: s?.kind || "open",
                  })) {
                    (form.elements.namedItem(key) as HTMLInputElement).value =
                      value;
                  }
                }}
              >
                <option value="">새 상태</option>
                {data.statuses.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              이름
              <input name="name" maxLength={24} required />
            </label>
            <div className="form-grid">
              <label>
                색상
                <input name="color" type="color" defaultValue="#af527f" />
              </label>
              <label>
                처리
                <select name="kind">
                  <option value="open">진행할 일</option>
                  <option value="done">완료</option>
                  <option value="cancel">취소</option>
                </select>
              </label>
            </div>
            <div className="dialog-actions">
              <span />
              <button className="primary">저장</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
function BatchImport({ onClose }: { onClose: () => void }) {
  const { data, mutate, notify } = useCalix(),
    [page, setPage] = useState(0),
    [query, setQuery] = useState(""),
    [kind, setKind] = useState("all"),
    [keys, setKeys] = useState(new Set<string>()),
    [saving, setSaving] = useState(false);
  const imported = new Set(data.tasks.map((t) => t.source_key));
  const rows = data.events.filter(
    (e) =>
      !e.manual &&
      !imported.has(e.key) &&
      (kind === "all" || e.kind === kind) &&
      (e.title + " " + e.course_name).includes(query),
  );
  const pageCount = Math.max(1, Math.ceil(rows.length / 50)),
    currentPage = Math.min(page, pageCount - 1);
  const toggle = (key: string) =>
    setKeys((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  return (
    <Modal title="일괄 가져오기" onClose={onClose} wide>
      <div className="import-toolbar">
        <input
          aria-label="가져올 일정 검색"
          placeholder="일정 또는 과목 검색"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          aria-label="가져올 유형"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="all">모든 유형</option>
          <option value="assignment">과제</option>
          <option value="movie">영상</option>
        </select>
      </div>
      <div className="import-list">
        {rows.slice(currentPage * 50, currentPage * 50 + 50).map((e) => (
          <label key={e.key} className="import-row">
            <input
              type="checkbox"
              checked={keys.has(e.key)}
              onChange={() => toggle(e.key)}
            />
            <TypeBadge event={e} />
            <span>
              <strong>{e.title}</strong>
              <small>{e.course_name}</small>
            </span>
            <small>{dueText(e.due_at)}</small>
          </label>
        ))}
        {!rows.length && <div className="empty">가져올 일정 없음</div>}
      </div>
      {pageCount > 1 && (
        <div className="pagination">
          <span>
            {currentPage + 1} / {pageCount}
          </span>
          <button
            disabled={!currentPage}
            onClick={() => setPage(currentPage - 1)}
          >
            이전
          </button>
          <button
            disabled={currentPage >= pageCount - 1}
            onClick={() => setPage(currentPage + 1)}
          >
            다음
          </button>
        </div>
      )}
      <div className="dialog-actions">
        <button
          onClick={() => setKeys(new Set([...keys, ...rows.map((e) => e.key)]))}
        >
          전체 선택
        </button>
        <button
          onClick={() =>
            setKeys(
              (previous) =>
                new Set(
                  [...previous].filter(
                    (key) => !rows.some((e) => e.key === key),
                  ),
                ),
            )
          }
        >
          선택 해제
        </button>
        <span />
        <small>{keys.size}개 선택</small>
        <button
          className="primary"
          disabled={!keys.size || saving}
          onClick={() => {
            setSaving(true);
            void mutate("checklist.import", { keys: [...keys] })
              .then((count) => {
                notify(`${count}개 추가됨`);
                onClose();
              })
              .catch(() => {})
              .finally(() => setSaving(false));
          }}
        >
          가져오기
        </button>
      </div>
    </Modal>
  );
}
export { TimetablePage } from "./Timetable";
export function SettingsPage() {
  const { data, mutate, notify, requestInstall, requestRestart, openCredits } =
      useCalix(),
    [type, setType] = useState(false),
    [holiday, setHoliday] = useState(false),
    [special, setSpecial] = useState(false),
    [updates, setUpdates] = useState(false),
    [restore, setRestore] = useState<string | null>(null),
    [backupPassword, setBackupPassword] = useState(""),
    [fileBusy, setFileBusy] = useState(false),
    [ankiSelection, setAnkiSelection] = useState<boolean | null>(null);
  const categories = [
    ["profile", "내 프로필", UserRound],
    ["appearance", "화면", Palette],
    ["alarms", "알림과 소리", Bell],
    ["calendar", "일정", CalendarDays],
    ["semester", "학기", CalendarRange],
    ["menus", "메뉴 활성화", SlidersHorizontal],
    ["security", "비밀번호와 잠금", ShieldCheck],
    ["app", "앱 관리", Download],
    ["dev", "Dev", Terminal],
  ] as const;
  const [category, setCategory] = useState<string>("profile");
  const selectCategory = (id: string) => {
    setCategory(id);
    document.querySelector(".workspace main")?.scrollTo({ top: 0 });
  };
  const requestFile = async (mode: string) => {
    if (!isTauri()) {
      notify("파일 선택은 Windows 앱에서 진행합니다.");
      return;
    }
    setFileBusy(true);
    try {
      const path = await invoke<string | null>("backup_file", { mode });
      if (!path) return;
      if (mode === "restore") setRestore(path);
      else {
        await mutate("backup.export", { path });
        notify("백업됨");
      }
    } catch (error) {
      notify(String(error), true);
    } finally {
      setFileBusy(false);
    }
  };
  const themes: [Preferences["theme"], string, string][] = [
    ["pink", "핑크", "#d09bb7"],
    ["sky", "스카이블루", "#9bb8db"],
    ["mint", "민트", "#9bcdb9"],
    ["purple", "퍼플", "#b7a0d4"],
    ["dark", "다크", "#333242"],
    ["peach", "피치", "#deaa92"],
    ["amber", "앰버", "#d7b16a"],
    ["olive", "올리브", "#a7b580"],
    ["lavender", "라벤더", "#aaa7dc"],
  ];
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>설정</h1>
        </div>
      </div>
      <div
        className="settings-categories"
        role="tablist"
        aria-label="설정 카테고리"
      >
        {categories.map(([id, label, Icon], index) => (
          <button
            key={id}
            id={`settings-tab-${id}`}
            role="tab"
            aria-selected={category === id}
            aria-controls={`settings-pane-${id}`}
            tabIndex={category === id ? 0 : -1}
            onClick={() => selectCategory(id)}
            onKeyDown={(event) => {
              const step =
                event.key === "ArrowRight"
                  ? 1
                  : event.key === "ArrowLeft"
                    ? -1
                    : 0;
              if (step || event.key === "Home" || event.key === "End") {
                event.preventDefault();
                const next =
                  event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? categories.length - 1
                      : (index + step + categories.length) % categories.length;
                selectCategory(categories[next][0]);
                document
                  .getElementById(`settings-tab-${categories[next][0]}`)
                  ?.focus();
              }
            }}
          >
            <Icon aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
      </div>
      {category === "semester" && (
        <div role="tabpanel" id="settings-pane-semester" aria-labelledby="settings-tab-semester">
          <SemesterSettings />
        </div>
      )}
      {category === "security" && (
        <div role="tabpanel" id="settings-pane-security" aria-labelledby="settings-tab-security">
          <SecuritySettings />
        </div>
      )}
      {category === "menus" && (
        <div
          role="tabpanel"
          id="settings-pane-menus"
          aria-labelledby="settings-tab-menus"
        >
          <section className="glass settings-panel menu-settings">
            <div className="settings-heading"><SlidersHorizontal aria-hidden="true" /><h2>출결</h2></div>
            {([
              ["attendance_visible", "메뉴 표시", "사이드바에 출결 메뉴를 표시합니다."],
              ["attendance_sync", "출결 동기화", "다음 동기화부터 출결 기록을 가져옵니다."],
            ] as const).map(([key, label, description]) => (
              <label className="menu-option" key={key}>
                <span>
                  <strong>{label}</strong>
                  <small>{description}</small>
                </span>
                <input
                  type="checkbox"
                  role="switch"
                  aria-label={label}
                  checked={data.preferences[key] === true}
                  onChange={(event) => {
                    void mutate("preferences.save", {
                      [key]: event.target.checked,
                    }).catch(() => {});
                  }}
                />
              </label>
            ))}
          </section>
        </div>
      )}
      <div
        role="tabpanel"
        id="settings-pane-dev"
        aria-labelledby="settings-tab-dev"
        hidden={category !== "dev"}
      >
        <DevPanel active={category === "dev"} />
      </div>
      <div
        role="tabpanel"
        id="settings-pane-profile"
        aria-labelledby="settings-tab-profile"
        hidden={category !== "profile"}
      >
        <ProfileSettings />
      </div>
      <div
        role="tabpanel"
        id="settings-pane-alarms"
        aria-labelledby="settings-tab-alarms"
        hidden={category !== "alarms"}
      >
        <ReminderSettingsPanel active={category === "alarms"} />
      </div>
      <div
        role="tabpanel"
        id="settings-pane-appearance"
        aria-labelledby="settings-tab-appearance"
        hidden={category !== "appearance"}
      >
        <section className="glass settings-panel">
          <div className="settings-heading">
            <Palette aria-hidden="true" />
            <h2>화면</h2>
          </div>
          <div className="theme-picker">
            {themes.map(([id, name, color]) => (
              <button
                key={id}
                aria-pressed={data.preferences.theme === id}
                className={data.preferences.theme === id ? "selected" : ""}
                onClick={() =>
                  void mutate("preferences.save", { theme: id }).catch(() => {})
                }
              >
                <span style={{ background: color }}>
                  {data.preferences.theme === id && <Check size={20} />}
                </span>
                {name}
              </button>
            ))}
          </div>
          <div className="setting-row">
            <div>
              <strong>글래스</strong>
              <small>배경 블러와 반투명 패널</small>
            </div>
            <button
              className={`switch ${data.preferences.glass ? "on" : ""}`}
              role="switch"
              aria-checked={data.preferences.glass}
              aria-label="글래스"
              onClick={() =>
                void mutate("preferences.save", {
                  glass: !data.preferences.glass,
                }).catch(() => {})
              }
            >
              <i />
            </button>
          </div>
          <div className="setting-row">
            <strong>글꼴</strong>
            <select
              aria-label="글꼴"
              value={data.preferences.font_mode}
              onChange={(e) =>
                void mutate("preferences.save", {
                  font_mode: e.target.value,
                }).catch(() => {})
              }
            >
              <option value="pretendard">Pretendard</option>
              <option value="windows">Windows 기본</option>
            </select>
          </div>
        </section>
      </div>
      <div
        role="tabpanel"
        id="settings-pane-calendar"
        aria-labelledby="settings-tab-calendar"
        hidden={category !== "calendar"}
      >
        <section className="glass settings-panel">
          <div className="settings-heading">
            <CalendarDays aria-hidden="true" />
            <h2>일정</h2>
          </div>
          <button className="settings-link" onClick={() => setType(true)}>
            내 일정 카테고리
            <ArrowUpRight size={17} />
          </button>
          <button className="settings-link" onClick={() => setHoliday(true)}>
            공휴일 등록
            <ArrowUpRight size={17} />
          </button>
          <button className="settings-link" onClick={() => setSpecial(true)}>
            특수 일정 등록
            <ArrowUpRight size={17} />
          </button>
        </section>
      </div>
      <div
        role="tabpanel"
        id="settings-pane-app"
        aria-labelledby="settings-tab-app"
        hidden={category !== "app"}
      >
        <section className="glass settings-panel">
          <div className="settings-heading">
            <Download aria-hidden="true" />
            <h2>앱 관리</h2>
          </div>
          {[
            ["updates", "업데이트 확인"],
            ["backup", "개인 자료 백업"],
            ["restore", "백업 복원"],
            ["credits", "앱 정보"],
          ].map(([mode, label]) => (
            <button
              key={mode}
              className="settings-link"
              disabled={fileBusy}
              onClick={() => {
                if (mode === "credits") openCredits();
                else if (mode === "updates") setUpdates(true);
                else void requestFile(mode);
              }}
            >
              {label}
              <ArrowUpRight size={17} />
            </button>
          ))}
          <button
            className="settings-link"
            onClick={() =>
              void rpc("app.open", { page: "guide" }).catch((e) =>
                notify(e.message, true),
              )
            }
          >
            사용 설명서
            <ArrowUpRight size={17} />
          </button>

          <button
            className="settings-link"
            onClick={() => {
              if (isTauri()) requestRestart();
              else notify("재시작은 Windows 앱에서 진행합니다.");
            }}
          >
            재시작
            <ArrowUpRight size={17} />
          </button>
        </section>
        <section className="glass settings-panel">
          <div className="settings-heading"><h2>외부 연동</h2></div>
          <label className="menu-option">
            <span>
              <strong>Anki 동기화</strong>
              <small>같은 PC의 Anki에서 덱별 카드 수를 가져옵니다.</small>
            </span>
            <input
              type="checkbox"
              role="switch"
              aria-label="Anki 동기화"
              checked={ankiSelection ?? data.preferences.anki_sync === true}
              disabled={ankiSelection !== null}
              onChange={(event) => {
                const enabled = event.target.checked;
                setAnkiSelection(enabled);
                void mutate("preferences.save", { anki_sync: enabled })
                  .catch(() => {})
                  .finally(() => setAnkiSelection(null));
              }}
            />
          </label>
        </section>
        <ResetSettings />
      </div>
      {type && (
        <Modal title="내 일정 카테고리" onClose={() => setType(false)}>
          <div className="type-list">
            {data.types.map((t) => (
              <div key={t.id}>
                <span style={{ background: t.color }} />
                {t.name}
              </div>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void mutate("type.save", {
                name: f.get("name"),
                color: f.get("color"),
              })
                .then(() => setType(false))
                .catch(() => {});
            }}
          >
            <div className="form-grid">
              <label>
                이름
                <input name="name" required maxLength={40} />
              </label>
              <label>
                색상
                <input type="color" name="color" defaultValue="#af527f" />
              </label>
            </div>
            <div className="dialog-actions">
              <span />
              <button className="primary">추가</button>
            </div>
          </form>
        </Modal>
      )}
      {holiday && (
        <Modal title="공휴일 등록" onClose={() => setHoliday(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void mutate("holiday.save", {
                date: f.get("date"),
                name: f.get("name"),
                enabled: true,
              })
                .then(() => setHoliday(false))
                .catch(() => {});
            }}
          >
            <label>
              날짜
              <DateField label="공휴일 날짜" name="date" defaultValue={dateKey()} />
            </label>
            <label>
              이름
              <input name="name" maxLength={80} required />
            </label>
            <div className="dialog-actions">
              <span />
              <button className="primary">등록</button>
            </div>
          </form>
        </Modal>
      )}
      {updates && (
        <UpdateDialog
          onClose={() => setUpdates(false)}
          onInstall={() => {
            setUpdates(false);
            requestInstall();
          }}
        />
      )}
      {restore && (
        <Modal
          title="백업을 복원하시겠습니까?"
          onClose={() => setRestore(null)}
        >
          <p className="muted">현재 자료를 백업 파일로 바꿉니다.</p>
          <label>백업 비밀번호<input type="password" autoComplete="current-password" placeholder="암호화된 백업만 입력" value={backupPassword} onChange={event => setBackupPassword(event.target.value)} /></label>
          <div className="dialog-actions">
            <span />
            <button onClick={() => setRestore(null)}>취소</button>
            <button
              className="primary"
              disabled={fileBusy}
              onClick={() => {
                setFileBusy(true);
                void mutate("backup.restore", { path: restore, password: backupPassword })
                  .then(() => {
                    setRestore(null);
                    setBackupPassword("");
                    notify("복원됨");
                  })
                  .catch(() => {})
                  .finally(() => setFileBusy(false));
              }}
            >
              복원
            </button>
          </div>
        </Modal>
      )}
      {special && (
        <Modal title="특수 일정 등록" className="settings-choice-dialog" onClose={() => setSpecial(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void mutate("special.save", {
                catholic: f.has("catholic"),
                birthday: f.has("birthday"),
              })
                .then(() => setSpecial(false))
                .catch(() => {});
            }}
          >
            <div className="settings-choice-list">
              <label className="menu-option">
                <strong>가톨릭 일정</strong>
                <input name="catholic" type="checkbox" role="switch" defaultChecked={data.preferences.catholic} />
              </label>
              <label className="menu-option">
                <strong>???</strong>
                <input name="birthday" type="checkbox" role="switch" defaultChecked={data.preferences.birthday} />
              </label>
            </div>
            <div className="dialog-actions">
              <span />
              <button type="button" onClick={() => setSpecial(false)}>취소</button>
              <button className="primary">저장</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
