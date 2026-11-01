import { invoke } from "@tauri-apps/api/core";
const result = window as unknown as { __reminderProbe: unknown };
const payload = {
  title: "알림 실행 검사",
  message: "7일 이내 과제와 영상",
  urgent: false,
  theme: "pink",
  glass: true,
  sound: "",
  volume: 0,
  total: 1,
  events: [
    {
      key: "probe-seven-days",
      title: "7일 후 과제",
      course_name: "검사",
      kind: "assignment",
      due_at: new Date(Date.now() + 7 * 86400000).toISOString(),
    },
  ],
};
const timed = async <T>(job: Promise<T>): Promise<T> => {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      job,
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(Error("IPC_TIMEOUT")), 10000);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
};
void (async () => {
  try {
    const started = performance.now();
    const first = invoke<number>("reminder_show", { payload });
    const ready = invoke("app_ready");
    const backup = invoke("backup_file", { mode: "probe" }).then(
      () => {
        throw Error("UNEXPECTED_BACKUP_SUCCESS");
      },
      (error) => {
        if (!String(error).includes("작업을 확인하세요.")) throw error;
        return true;
      },
    );
    let revision = await timed(first);
    await timed(Promise.all([ready, backup]));
    const createMs = performance.now() - started;
    for (let i = 0; i < 5; i++) {
      const old = revision;
      revision = await timed(
        invoke<number>("reminder_show", {
          payload: { ...payload, title: "갱신 " + i },
        }),
      );
      await timed(invoke("reminder_close", { revision: old }));
      const refreshed = await timed(
        invoke<number>("reminder_show", { payload }),
      );
      if (refreshed !== revision + 1)
        throw Error("STALE_CLOSE_REMOVED_NEW_REMINDER");
      revision = refreshed;
      await timed(invoke("app_ready"));
      await timed(invoke("reminder_close", { revision }));
      const reopened = await timed(
        invoke<number>("reminder_show", { payload }),
      );
      if (reopened !== revision + 2) throw Error("CLOSE_REOPEN_ORDER");
      revision = reopened;
    }
    result.__reminderProbe = {
      passed: true,
      cycles: 5,
      backupResponsive: true,
      mainResponsive: true,
      createMs,
      revision,
    };
  } catch (error) {
    result.__reminderProbe = { passed: false, error: String(error) };
  }
})();
