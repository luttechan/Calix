import { t, useLanguage } from "./i18n";
import { PageHeading } from "./PageHeading";
import { ColorField } from "./ColorField";
import { CredentialPrompt, PrivateDiaryMigration, SecuritySettings } from "./Security";
import { pinLength } from "./PinKeypad";
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
    [migration, setMigration] = useState(false),
    [entries, setEntries] = useState<Summary[]>(data.journals),
    [id, setId] = useState<string | null>(null),
    [title, setTitle] = useState(""),
    [date, setDate] = useState(dateKey()),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [remove, setRemove] = useState(false);
  const loading = useRef(false),
    accessRevision = useRef(0),
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
      if (secretRef.current) {
        accessRevision.current++;
        await rpc("vault.lock");
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
        accessRevision.current++;
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
    if (next === secret || busy) return;
    try {
      await save();
      accessRevision.current++;
      await rpc("vault.lock");
      clear();
      setSecret(next);
      secretRef.current = next;
      setUnlocked(false);
      setError("");
      if (next) setEntries([]);
      else await reload(false);
    } catch (e) {
      notify((e as Error).message, true);
    }
  };
  const unlockDiary = async (password: string) => {
    const request = ++accessRevision.current;
    setBusy(true);
    setError("");
    try {
      await rpc("vault.unlock", { password });
      if (request !== accessRevision.current) return;
      const summaries = await rpc<Summary[]>("diary.list", { secret: true });
      if (request === accessRevision.current) {
        setEntries(summaries);
        setUnlocked(true);
      }
    } catch (error) {
      if (request === accessRevision.current) {
        setError((error as Error).message);
        soundError();
      }
    } finally {
      setBusy(false);
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
      <PageHeading title={t("일기장")}>
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
      </PageHeading>
      {secret && !unlocked ? (
        <section className="glass vault-panel">
          <div className="vault-symbol">
            <Lock size={31} />
          </div>
          <h2>{t("비밀 일기")}</h2>
          {data.privateDiaryMigration ? <>
            <button type="button" className="primary" onClick={() => setMigration(true)}>{t("비밀 일기 암호 변경")}</button>
            {migration && <PrivateDiaryMigration onClose={() => setMigration(false)} />}
          </> : !data.security?.configured ? <SecuritySettings setupOnly />
            : <CredentialPrompt label={pinLength(data.security.credential_mode) ? "PIN" : "비밀번호"}
              mode={data.security.credential_mode} pending={busy} error={error} nextLabel="잠금 해제"
              onSubmit={password => void unlockDiary(password)} />}
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
              <ColorField label={t("글자 색")} onChange={value => editor?.chain().setColor(value).run()} />
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
