import { t, useLanguage } from "./i18n";
import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { TextStyle } from "@tiptap/extension-text-style";
import { Color } from "@tiptap/extension-color";
import DOMPurify from "dompurify";
import {
  Bold,
  Italic,
  Underline,
  Plus,
  Lock,
  Unlock,
  Trash2,
  Check,
  BookOpen,
} from "lucide-react";
import { Modal, useCalix } from "./App";
import { rpc } from "./bridge";
import { dateKey } from "./dates";
import { DateField } from "./ChecklistDeadline";
import type { Summary, Journal } from "./types";
export function DiaryPage({ active = true }: { active?: boolean }) {
  useLanguage();
  const { data, notify, leave, mutate, soundError } = useCalix();
  const [secret, setSecret] = useState(false),
    [unlocked, setUnlocked] = useState(false),
    [initialized, setInitialized] = useState(false),
    [entries, setEntries] = useState<Summary[]>(data.journals),
    [id, setId] = useState<string | null>(null),
    [title, setTitle] = useState(""),
    [date, setDate] = useState(dateKey()),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [remove, setRemove] = useState(false);
  const loading = useRef(false),
    saveRef = useRef<() => Promise<void>>(async () => {}),
    dirtyRef = useRef(false),
    secretRef = useRef(false),
    saving = useRef<Promise<void> | null>(null);
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ link: { openOnClick: false } }),
      TextStyle,
      Color,
    ],
    content: "",
    editorProps: {
      attributes: { class: "journal-editor", "aria-label": "일기 본문" },
    },
    onUpdate: () => {
      if (!loading.current) {
        setDirty(true);
        dirtyRef.current = true;
      }
    },
  });
  const reload = async (currentSecret = secret) =>
    setEntries(await rpc<Summary[]>("diary.list", { secret: currentSecret }));
  const clear = () => {
    setId(null);
    setTitle("");
    setDate(dateKey());
    loading.current = true;
    editor?.commands.clearContent(false);
    loading.current = false;
    setDirty(false);
    dirtyRef.current = false;
  };
  const saveEntry = async () => {
    if (!editor || !dirtyRef.current) return;
    const value = {
      date,
      title: title.trim() || "제목 없음",
      body: editor.getText(),
      html: DOMPurify.sanitize(editor.getHTML(), {
        FORBID_TAGS: ["img", "iframe", "video", "audio", "style"],
        FORBID_ATTR: ["src", "srcset"],
      }),
    };
    setBusy(true);
    try {
      const key = (await mutate("diary.save", { secret, value, id })) as string;
      setId(key);
      setDirty(false);
      dirtyRef.current = false;
      await reload();
    } finally {
      setBusy(false);
    }
  };
  const save = () => {
    if (saving.current) return saving.current;
    const task = saveEntry();
    saving.current = task;
    void task
      .finally(() => {
        saving.current = null;
      })
      .catch(() => {});
    return task;
  };
  useEffect(() => {
    editor?.setEditable(!busy, false);
  }, [editor, busy]);
  saveRef.current = save;
  secretRef.current = secret;
  useEffect(() => {
    if (!active) return;
    const guard = async () => {
      await saveRef.current();
      if (secretRef.current) await rpc("vault.lock");
      if (secretRef.current) {
        clear();
        setEntries([]);
        setUnlocked(false);
      }
    };
    leave.current = guard;
    return () => {
      if (leave.current === guard) leave.current = null;
    };
  }, [leave, editor, active]);
  useEffect(() => {
    if (active && !secret) setEntries(data.journals);
  }, [active, data.journals, secret]);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const lock = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (!secretRef.current) return;
        void saveRef
          .current()
          .then(() => rpc("vault.lock"))
          .then(() => {
            clear();
            setEntries([]);
            setUnlocked(false);
          })
          .catch((e) => notify(e.message, true));
      }, 500);
    };
    const visibility = () => {
      if (document.hidden) lock();
    };
    window.addEventListener("blur", lock);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      if (timer) clearTimeout(timer);
      window.removeEventListener("blur", lock);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [editor]);
  const switchMode = async (next: boolean) => {
    try {
      await save();
      await rpc("vault.lock");
      clear();
      setSecret(next);
      secretRef.current = next;
      setUnlocked(false);
      setPassword("");
      setError("");
      if (next) {
        const state = await rpc<{ initialized: boolean }>("vault.state");
        setInitialized(state.initialized);
        setEntries([]);
      } else await reload(false);
    } catch (e) {
      notify((e as Error).message, true);
    }
  };
  const open = async (key: string) => {
    if (busy) return;
    try {
      await save();
      setBusy(true);
      const value = await rpc<Journal>("diary.read", { secret, id: key });
      loading.current = true;
      setId(key);
      setDate(value.date);
      setTitle(value.title);
      editor?.commands.setContent(
        DOMPurify.sanitize(
          value.html ||
            `<p>${value.body.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll("\n", "</p><p>")}</p>`,
          {
            FORBID_TAGS: ["img", "iframe", "video", "audio", "style"],
            FORBID_ATTR: ["src", "srcset"],
          },
        ),
        { emitUpdate: false },
      );
      loading.current = false;
      setDirty(false);
      dirtyRef.current = false;
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{t("일기장")}</h1>
        </div>
        <div className="toolbar">
          <div className="segmented">
            <button
              className={!secret ? "selected" : ""}
              onClick={() => void switchMode(false)}
            >{t("일반 일기")}{" "}</button>
            <button
              className={secret ? "selected" : ""}
              onClick={() => void switchMode(true)}
            >
              <Lock size={13} />{t("비밀 일기")}{" "}</button>
          </div>
          {(!secret || unlocked) && (
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                void save()
                  .then(() => {
                    clear();
                    setTitle("");
                    setDirty(true);
                    dirtyRef.current = true;
                  })
                  .catch((e) => notify(e.message, true))
              }
            >
              <Plus size={17} />{t("새 일기")}{" "}</button>
          )}
        </div>
      </div>
      {secret && !unlocked ? (
        <section className="glass vault-panel">
          <div className="vault-symbol">
            <Lock size={31} />
          </div>
          <h2>{initialized ? t("비밀 일기") : t("비밀 일기 만들기")}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              const value = password;
              setPassword("");
              void rpc("vault.unlock", { password: value })
                .then(() => {
                  setUnlocked(true);
                  return reload(true);
                })
                .catch((e) => { setError(e.message); soundError(); })
                .finally(() => setBusy(false));
            }}
          >
            <label>
              <span>{initialized ? t("암호") : t("암호 (12자 이상)")}</span>
              <input
                type="password"
                autoComplete="off"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={initialized ? 1 : 12}
                maxLength={4096}
                required
                aria-label={t("비밀 일기 암호")}
              />
            </label>
            {error && <p className="danger">{error}</p>}
            <button className="primary" disabled={busy}>
              {busy ? t("확인 중") : initialized ? t("잠금 해제") : t("만들기")}
            </button>
          </form>
        </section>
      ) : (
        <section className="glass diary-workspace">
          <aside className="journal-list">
            <div className="journal-list-title">
              <BookOpen size={17} />
              <span>{entries.length}{t("개 기록")}</span>
              {secret && (
                <button
                  className="icon-button"
                  title={t("잠금")}
                  onClick={() =>
                    void save()
                      .then(() => rpc("vault.lock"))
                      .then(() => {
                        clear();
                        setUnlocked(false);
                        setEntries([]);
                      })
                      .catch((e) => notify(e.message, true))
                  }
                >
                  <Lock size={15} />
                </button>
              )}
            </div>
            {entries.map((entry) => (
              <button
                disabled={busy}
                key={entry.id}
                className={id === entry.id ? "selected" : ""}
                onClick={() => void open(entry.id)}
              >
                <small>{entry.date.replaceAll("-", ". ")}</small>
                <strong>{entry.title}</strong>
              </button>
            ))}
            {!entries.length && <p className="empty">{t("아직 기록이 없습니다.")}</p>}
          </aside>
          <div className="journal-paper">
            <div className="journal-meta">
              <DateField
                disabled={busy}
                label={t("일기 날짜")}
                value={date}
                onChange={(value) => {
                  setDate(value);
                  setDirty(true);
                  dirtyRef.current = true;
                }}
              />
              <span>{busy ? t("저장 중") : dirty ? t("수정 중") : t("저장됨")}</span>
              <button
                className="icon-button"
                disabled={!id}
                title={t("일기 삭제")}
                onClick={() => setRemove(true)}
              >
                <Trash2 size={16} />
              </button>
            </div>
            <input
              disabled={busy}
              className="journal-title"
              aria-label={t("일기 제목")}
              placeholder={t("오늘의 제목")}
              maxLength={200}
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                setDirty(true);
                dirtyRef.current = true;
              }}
            />
            <div className="format-bar">
              <button
                title={t("굵게 (Ctrl+B)")}
                aria-pressed={editor?.isActive("bold")}
                onClick={() => editor?.chain().focus().toggleBold().run()}
              >
                <Bold size={16} />
              </button>
              <button
                title={t("기울임 (Ctrl+I)")}
                aria-pressed={editor?.isActive("italic")}
                onClick={() => editor?.chain().focus().toggleItalic().run()}
              >
                <Italic size={16} />
              </button>
              <button
                title={t("밑줄 (Ctrl+U)")}
                aria-pressed={editor?.isActive("underline")}
                onClick={() => editor?.chain().focus().toggleUnderline().run()}
              >
                <Underline size={16} />
              </button>
              <input
                type="color"
                aria-label={t("글자 색")}
                defaultValue="#af527f"
                onChange={(e) =>
                  editor?.chain().focus().setColor(e.target.value).run()
                }
              />
              <span />
              <button
                className="save-entry"
                disabled={busy || !dirty}
                onClick={() =>
                  void save()
                    .then(() => notify("일기 저장됨"))
                    .catch((e) => notify(e.message, true))
                }
              >
                <Check size={15} />{t("저장")}{" "}</button>
            </div>
            <EditorContent editor={editor} />
          </div>
        </section>
      )}
      {remove && (
        <Modal title={t("정말 삭제하시겠습니까?")} onClose={() => setRemove(false)}>
          <p className="muted">{title}</p>
          <div className="dialog-actions">
            <span />
            <button onClick={() => setRemove(false)}>{t("취소")}</button>
            <button
              className="primary"
              onClick={() =>
                void mutate("diary.delete", { secret, id })
                  .then(() => {
                    clear();
                    setRemove(false);
                    return reload();
                  })
                  .catch((e) => notify(e.message, true))
              }
            >{t("삭제")}{" "}</button>
          </div>
        </Modal>
      )}
    </>
  );
}
