import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Calculator,
  Link2,
  Plus,
  Save,
  Search,
  Trash2,
  Undo2,
} from "lucide-react";
import { Modal, useCalix } from "./App";
import { rpc } from "./bridge";
import {
  changeCount,
  changedItems,
  createSheet,
  creditValue,
  gradeOptions,
  previewGrades,
  validateSheet,
  type GradeData,
  type GradeDraft,
  type GradeErrors,
  type GradeField,
  type GradeSheet,
} from "./gradeState";
import "./security-grades.css";

const EMPTY_ERRORS: GradeErrors[string] = {};
const collator = new Intl.Collator("ko", {
  numeric: true,
  sensitivity: "base",
});
const GradeRow = memo(function GradeRow({
  item,
  options,
  errors,
  changed,
  focus,
  onField,
  onDelete,
}: {
  item: GradeDraft;
  options: string[];
  errors: GradeErrors[string];
  changed: boolean;
  focus: boolean;
  onField: (id: string, key: GradeField, value: string | number) => void;
  onDelete: (id: string) => void;
}) {
  const field = (key: GradeField, value: string | number) =>
    onField(item.id, key, value);
  const error = (key: GradeField) =>
    errors[key] && (
      <span className="grade-field-error" id={`${item.id}-${key}-error`}>
        {errors[key]}
      </span>
    );
  const attrs = (key: GradeField) => ({
    "data-field": key,
    "aria-invalid": !!errors[key],
    "aria-describedby": errors[key] ? `${item.id}-${key}-error` : undefined,
  });
  return (
    <div
      className={`grade-row ${item.excluded ? "excluded" : ""} ${changed ? "modified" : ""}`}
      data-grade-id={item.id}
    >
      <label className="grade-course grade-field">
        <span className="grade-field-label">과목</span>
        <span className="grade-course-input">
          {item.linked && <Link2 size={14} aria-label="시간표 연결" />}
          <input
            {...attrs("title")}
            aria-label={`${item.title || "새 과목"} 과목명`}
            title={item.title}
            value={item.title}
            readOnly={item.linked}
            maxLength={200}
            autoFocus={focus}
            onChange={(event) => field("title", event.target.value)}
          />
        </span>
        {error("title")}
      </label>
      <label className="grade-field">
        <span className="grade-field-label">학점</span>
        <input
          {...attrs("credits")}
          type="text"
          inputMode="decimal"
          maxLength={8}
          aria-label={`${item.title || "새 과목"} 학점`}
          value={item.credits}
          onFocus={(event) => {
            if (creditValue(item.credits) === 0) event.currentTarget.select();
          }}
          onChange={(event) =>
            field(
              "credits",
              event.target.value.replace(",", ".").replace(/^0+(?=\d)/, ""),
            )
          }
        />
        {error("credits")}
      </label>
      <label className="grade-field">
        <span className="grade-field-label">성적</span>
        <select
          {...attrs("grade")}
          aria-label={`${item.title || "새 과목"} 성적`}
          value={item.grade}
          onChange={(event) => field("grade", event.target.value)}
        >
          <option value="">미입력</option>
          {item.grade && !options.includes(item.grade) && (
            <option value={item.grade}>{item.grade} (미지원)</option>
          )}
          {options.map((grade) => (
            <option key={grade}>{grade}</option>
          ))}
        </select>
        {error("grade")}
      </label>
      <label className="grade-field">
        <span className="grade-field-label">분류</span>
        <select
          {...attrs("category")}
          aria-label={`${item.title || "새 과목"} 분류`}
          value={item.category}
          onChange={(event) => field("category", event.target.value)}
        >
          {["전공", "교양", "일반"].map((category) => (
            <option key={category}>{category}</option>
          ))}
        </select>
        {error("category")}
      </label>
      <div className="grade-actions">
        <label className="grade-exclude">
          <input
            type="checkbox"
            checked={!!item.excluded}
            onChange={(event) =>
              field("excluded", Number(event.target.checked))
            }
          />
          제외
        </label>
        {!item.linked && (
          <button
            type="button"
            className="icon-button"
            title="과목 삭제"
            aria-label={`${item.title || "새 과목"} 삭제`}
            onClick={() => onDelete(item.id)}
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>
    </div>
  );
});

export function GradesPage() {
  const { data, notify, leave } = useCalix();
  const [semester, setSemester] = useState(data.mainTerm),
    [sheet, setSheet] = useState<GradeSheet | null>(null),
    [loading, setLoading] = useState(true),
    [pending, setPending] = useState(false);
  const [error, setError] = useState(""),
    [errors, setErrors] = useState<GradeErrors>({}),
    [query, setQuery] = useState(""),
    [focus, setFocus] = useState("");
  const [remove, setRemove] = useState<string | null>(null),
    [discard, setDiscard] = useState(false),
    [order, setOrder] = useState<string[]>([]),
    [sort, setSort] = useState<{
      field: "title" | "credits" | "grade" | "category";
      desc: boolean;
    } | null>(null);
  const latest = useRef<GradeSheet | null>(null),
    job = useRef<Promise<void> | null>(null),
    request = useRef(0),
    mounted = useRef(true),
    form = useRef<HTMLFormElement>(null),
    saveRef = useRef<(silent?: boolean) => Promise<void>>(async () => {});
  const update = useCallback((next: GradeSheet | null) => {
    latest.current = next;
    setSheet(next);
  }, []);
  const count = sheet ? changeCount(sheet) : 0;
  const stamp = JSON.stringify(
    data.sessions.map((item) => [
      item.id,
      item.semester,
      item.course_id,
      item.title,
    ]),
  );
  const load = useCallback(
    async (term: string) => {
      const id = ++request.current;
      setLoading(true);
      setError("");
      try {
        const result = await rpc<GradeData>("grades.read", { semester: term });
        if (
          mounted.current &&
          id === request.current &&
          !(
            latest.current?.base.semester === term &&
            changeCount(latest.current)
          )
        ) {
          update(createSheet(result));
          setErrors({});
          setOrder([]);
          setSort(null);
        }
      } catch (reason) {
        if (mounted.current && id === request.current)
          setError((reason as Error).message);
      } finally {
        if (mounted.current && id === request.current) setLoading(false);
      }
    },
    [update],
  );
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      ++request.current;
    };
  }, []);
  useEffect(() => {
    if (
      latest.current?.base.semester === semester &&
      changeCount(latest.current)
    )
      return;
    void load(semester);
    return () => {
      ++request.current;
    };
  }, [semester, stamp, load]);
  const focusField = (id: string, key: GradeField) => {
    setQuery("");
    requestAnimationFrame(() => {
      const rows =
        form.current?.querySelectorAll<HTMLElement>(".grade-row") ?? [];
      const row = [...rows].find((el) => el.dataset.gradeId === id);
      const input = row?.querySelector<HTMLElement>(`[data-field="${key}"]`);
      input?.focus();
      input?.scrollIntoView({ block: "nearest" });
    });
  };
  const save = async (silent = false) => {
    if (job.current) return job.current;
    const current = latest.current;
    if (!current || !changeCount(current)) return;
    const invalid = validateSheet(current);
    setErrors(invalid);
    setError("");
    const first = Object.entries(invalid)[0];
    if (first) {
      focusField(first[0], Object.keys(first[1])[0] as GradeField);
      throw new Error("입력을 확인하세요.");
    }
    setPending(true);
    const task = (async () => {
      try {
        const result = await rpc<GradeData>("grades.save_all", {
          semester: current.base.semester,
          revision: current.base.revision,
          scale: current.scale,
          items: changedItems(current).map((item) => ({
            ...item,
            credits: creditValue(item.credits),
            excluded: !!item.excluded,
          })),
          deleted: current.deleted
            .filter((item) =>
              current.base.items.some((base) => base.id === item.id),
            )
            .map((item) => item.id),
        });
        if (mounted.current) {
          update(createSheet(result));
          setErrors({});
          setFocus("");
          if (!silent) notify("전체 저장됨");
        }
      } catch (reason) {
        if (mounted.current) setError((reason as Error).message);
        throw reason;
      } finally {
        job.current = null;
        if (mounted.current) setPending(false);
      }
    })();
    job.current = task;
    return task;
  };
  saveRef.current = save;
  useEffect(() => {
    const guard = () => saveRef.current(true);
    leave.current = guard;
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (!document.querySelector("dialog[open]"))
          void saveRef.current().catch(() => {});
      }
    };
    const unload = (event: BeforeUnloadEvent) => {
      if (latest.current && changeCount(latest.current)) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("keydown", key);
    window.addEventListener("beforeunload", unload);
    return () => {
      if (leave.current === guard) leave.current = null;
      window.removeEventListener("keydown", key);
      window.removeEventListener("beforeunload", unload);
    };
  }, [leave, remove, discard]);
  const onField = useCallback(
    (id: string, key: GradeField, value: string | number) => {
      const current = latest.current;
      if (!current || job.current) return;
      update({
        ...current,
        items: current.items.map((item) =>
          item.id === id ? { ...item, [key]: value } : item,
        ),
      });
      setErrors((previous) => {
        if (!previous[id]?.[key]) return previous;
        const next = { ...previous, [id]: { ...previous[id] } };
        delete next[id][key];
        if (!Object.keys(next[id]).length) delete next[id];
        return next;
      });
    },
    [update],
  );
  const options = useMemo(
    () => (sheet ? gradeOptions(sheet.scale) : []),
    [sheet?.scale],
  );
  const changed = useMemo(
    () => new Set(sheet ? changedItems(sheet).map((item) => item.id) : []),
    [sheet],
  );
  const summary = useMemo(() => (sheet ? previewGrades(sheet) : null), [sheet]);
  const visible = useMemo(() => {
    if (!sheet) return [];
    const index = new Map(order.map((id, i) => [id, i]));
    return sheet.items
      .filter((item) =>
        item.title
          .toLocaleLowerCase()
          .includes(query.trim().toLocaleLowerCase()),
      )
      .sort(
        (a, b) =>
          (index.get(a.id) ?? Number.MAX_SAFE_INTEGER) -
          (index.get(b.id) ?? Number.MAX_SAFE_INTEGER),
      );
  }, [sheet, order, query]);
  const sortBy = (field: NonNullable<typeof sort>["field"]) => {
    if (!sheet) return;
    const desc = sort?.field === field ? !sort.desc : false;
    setSort({ field, desc });
    setOrder(
      [...sheet.items]
        .sort((a, b) => {
          const result =
            field === "credits"
              ? (creditValue(a.credits) ?? -1) - (creditValue(b.credits) ?? -1)
              : collator.compare(String(a[field]), String(b[field]));
          return desc ? -result : result;
        })
        .map((item) => item.id),
    );
  };
  return (
    <section className="grades-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">GRADEBOOK</p>
          <h1>학점 계산기</h1>
        </div>
        <Calculator size={26} aria-hidden="true" />
      </header>
      <div className="grades-toolbar">
        <label>
          학기
          <select
            aria-label="학기"
            value={semester}
            disabled={pending}
            onChange={(event) => {
              const next = event.target.value;
              void save(true)
                .then(() => {
                  update(null);
                  setSemester(next);
                  setQuery("");
                  setErrors({});
                })
                .catch((reason) => notify(reason.message));
            }}
          >
            {data.timetableTerms.map((term) => (
              <option key={term.name}>{term.name}</option>
            ))}
          </select>
        </label>
        {sheet && (
          <label>
            평점 기준
            <select
              aria-label="평점 기준"
              value={sheet.scale}
              disabled={pending}
              onChange={(event) => {
                const next = { ...sheet, scale: event.target.value };
                update(next);
                setErrors((previous) =>
                  Object.keys(previous).length ? validateSheet(next) : previous,
                );
              }}
            >
              {["4.5", "4.3", "4.0"].map((scale) => (
                <option key={scale}>{scale}</option>
              ))}
            </select>
          </label>
        )}
        <button
          className="button primary"
          type="button"
          disabled={!sheet || pending}
          onClick={() => {
            if (!sheet) return;
            const id = "manual:" + crypto.randomUUID().replaceAll("-", "");
            setQuery("");
            setOrder([]);
            setSort(null);
            setFocus(id);
            update({
              ...sheet,
              items: [
                ...sheet.items,
                {
                  id,
                  title: "",
                  credits: "3",
                  grade: "",
                  category: "일반",
                  excluded: 0,
                  linked: false,
                },
              ],
            });
          }}
        >
          <Plus size={16} />
          과목 추가
        </button>
      </div>
      {!data.timetableConfigured && (
        <p className="muted">시간표에서 학기를 설정하면 자동으로 연결됩니다.</p>
      )}
      {error && (
        <div className="grade-error-banner" role="alert">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => (count ? setDiscard(true) : void load(semester))}
          >
            다시 불러오기
          </button>
        </div>
      )}
      {Object.keys(errors).length > 0 && (
        <div className="grade-error-banner" role="alert">
          <strong>입력을 확인하세요.</strong>
          <ul>
            {Object.entries(errors).flatMap(([id, fields]) =>
              Object.entries(fields).map(([field, message]) => (
                <li key={id + field}>
                  <button
                    type="button"
                    onClick={() => focusField(id, field as GradeField)}
                  >
                    {sheet?.items.find((item) => item.id === id)?.title ||
                      "새 과목"}
                    : {message}
                  </button>
                </li>
              )),
            )}
          </ul>
        </div>
      )}
      {loading && !sheet && (
        <div className="empty" role="status">
          불러오는 중
        </div>
      )}
      {sheet && summary && (
        <>
          <div className="grade-summary" aria-label="학점 계산 결과">
            <article>
              <span>평점평균</span>
              <strong>
                {summary.gpa ?? "—"}
                <small> / {sheet.scale}</small>
              </strong>
            </article>
            <article>
              <span>취득 학점</span>
              <strong>
                {summary.earned_credits}
                <small> 학점</small>
              </strong>
            </article>
            <article>
              <span>평점 산입</span>
              <strong>
                {summary.graded_credits}
                <small> 학점</small>
              </strong>
            </article>
            <article>
              <span>성적 미입력</span>
              <strong>
                {summary.pending}
                <small> 과목</small>
              </strong>
            </article>
          </div>
          <p className="grade-policy">
            P는 취득 학점에 포함됩니다. P와 NP는 평점평균에서 제외됩니다.
          </p>
          <form
            id="grade-form"
            ref={form}
            className="grades-form"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void save().catch(() => {});
            }}
          >
            <div className="grade-search">
              <Search size={16} />
              <input
                type="search"
                aria-label="과목 검색"
                placeholder="과목 검색"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") event.preventDefault();
                }}
              />
              <span>{visible.length}과목</span>
            </div>
            <fieldset disabled={pending} className="grade-edit-fields">
              <div className="grade-table">
                <div className="grade-table-head">
                  {(
                    [
                      ["title", "과목"],
                      ["credits", "학점"],
                      ["grade", "성적"],
                      ["category", "분류"],
                    ] as const
                  ).map(([field, label]) => (
                    <button
                      type="button"
                      key={field}
                      title={`${label} 정렬`}
                      onClick={() => sortBy(field)}
                      aria-label={`${label} ${sort?.field === field && !sort.desc ? "내림차순" : "오름차순"} 정렬`}
                    >
                      {label}
                      {sort?.field === field &&
                        (sort.desc ? (
                          <ArrowDown size={12} />
                        ) : (
                          <ArrowUp size={12} />
                        ))}
                    </button>
                  ))}
                  <span>관리</span>
                </div>
                {visible.map((item) => (
                  <GradeRow
                    key={item.id}
                    item={item}
                    options={options}
                    errors={errors[item.id] ?? EMPTY_ERRORS}
                    changed={changed.has(item.id)}
                    focus={focus === item.id}
                    onField={onField}
                    onDelete={setRemove}
                  />
                ))}
                {!visible.length && (
                  <div className="empty">
                    {sheet.items.length
                      ? "검색 결과가 없습니다."
                      : "시간표에 수업을 추가하거나 과목을 직접 입력하세요."}
                  </div>
                )}
              </div>
            </fieldset>
          </form>
          <div className="grade-savebar">
            <span role="status">
              {pending ? "저장 중" : count ? `변경 ${count}건` : "저장됨"}
            </span>
            {sheet.deleted.length > 0 && (
              <button
                type="button"
                disabled={pending}
                onClick={() => {
                  const item = sheet.deleted[sheet.deleted.length - 1];
                  update({
                    ...sheet,
                    items: [...sheet.items, item],
                    deleted: sheet.deleted.slice(0, -1),
                  });
                }}
              >
                <Undo2 size={16} />
                삭제 취소
              </button>
            )}
            {count > 0 && (
              <button
                type="button"
                disabled={pending}
                onClick={() => setDiscard(true)}
              >
                변경 취소
              </button>
            )}
            <button
              className="primary"
              type="submit"
              form="grade-form"
              disabled={pending || !count}
              title="전체 저장 (Ctrl+S)"
            >
              <Save size={16} />
              {pending ? "저장 중" : "전체 저장"}
            </button>
          </div>
          <details className="grade-sources">
            <summary>계산 기준</summary>
            <p>
              과목별 학점과 평점의 곱을 합산한 뒤 평점 산입 학점으로 나눕니다.
            </p>
            {(
              [
                ["grade45", "4.5 기준 / 부산외대"],
                ["grade43", "4.3 기준 / 연세대"],
                ["grade40", "4.0 기준 / UC Berkeley"],
              ] as const
            ).map(([page, label]) => (
              <button
                type="button"
                key={page}
                className="grade-source-link"
                onClick={() =>
                  void rpc("app.open", { page }).catch((reason) =>
                    notify(reason.message),
                  )
                }
              >
                {label}
              </button>
            ))}
          </details>
        </>
      )}
      {remove && (
        <Modal title="정말 삭제하시겠습니까?" onClose={() => setRemove(null)}>
          <div className="dialog-actions">
            <button type="button" onClick={() => setRemove(null)}>
              취소
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => {
                const current = latest.current,
                  item = current?.items.find((item) => item.id === remove);
                if (current && item && !item.linked) {
                  update({
                    ...current,
                    items: current.items.filter((row) => row.id !== remove),
                    deleted: [...current.deleted, item],
                  });
                  setErrors((previous) => {
                    const next = { ...previous };
                    delete next[remove];
                    return next;
                  });
                }
                setRemove(null);
              }}
            >
              삭제
            </button>
          </div>
        </Modal>
      )}
      {discard && (
        <Modal
          title="변경 내용을 취소하시겠습니까?"
          onClose={() => setDiscard(false)}
        >
          <div className="dialog-actions">
            <button type="button" onClick={() => setDiscard(false)}>
              계속 입력
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => {
                setDiscard(false);
                update(null);
                setQuery("");
                const term = data.timetableTerms.some(
                  (term) => term.name === semester,
                )
                  ? semester
                  : data.mainTerm;
                if (term !== semester) setSemester(term);
                else void load(term);
              }}
            >
              변경 취소
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
