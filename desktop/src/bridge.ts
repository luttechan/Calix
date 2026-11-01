import { isTauri, invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { Command, type Child } from "@tauri-apps/plugin-shell";
let child: Child | null = null,
  starting: Promise<void> | null = null,
  sequence = 0,
  generation = 0,
  stopping = false;
const pending = new Map<
  number,
  {
    resolve: (value: unknown) => void;
    reject: (error: Error) => void;
    timer: ReturnType<typeof setTimeout>;
    method: string;
  }
>();
const listeners = new Set<(message: Record<string, unknown>) => void>();
const stopped = new Set<() => void>();
export function subscribe(
  listener: (message: Record<string, unknown>) => void,
) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
let browserEvents: Promise<unknown> | null = null;
let diagnosticEvents: Promise<unknown> | null = null;
let browserBarrier: Promise<unknown> = Promise.resolve();
function browserMessage(message: Record<string, unknown>) {
  if (message.event === "browser-collect") {
    const runId = String(message.runId);
    const peer = generation;
    void browserBarrier
      .then(() => {
        if (stopping || generation !== peer) return undefined;
        return invoke("campus_collect", { runId });
      })
      .then((payload) => {
        if (stopping || generation !== peer || payload === undefined) return;
        return rpc("browser.complete", { runId, payload });
      })
      .catch((error) => {
        if (stopping || generation !== peer) return;
        const text = String(error);
        return rpc("browser.failed", {
          runId,
          authentication: text.includes("AUTH_REQUIRED"),
          message: text.includes("AUTH_REQUIRED")
            ? "학교에 다시 로그인하세요."
            : `학교 일정 확인 실패: ${text.slice(0, 160)}`,
        }).catch(() => {});
      });
  }
  if (message.event === "browser-cancel")
    browserBarrier = browserBarrier
      .then(() => invoke("campus_cancel"))
      .catch(() => {});
}
function failAll(message: string) {
  for (const request of pending.values()) {
    clearTimeout(request.timer);
    request.reject(new Error(message));
  }
  pending.clear();
  child = null;
  starting = null;
  for (const resolve of stopped) resolve();
  stopped.clear();
}
async function start() {
  if (starting) return starting;
  const current = ++generation;
  starting = (async () => {
    await invoke("campus_debug", { enabled: false }).catch(() => {});
    if (!browserEvents)
      browserEvents = listen("campus:progress", (event) => {
        if (!stopping && child)
          void rpc(
            "browser.progress",
            event.payload as Record<string, unknown>,
          ).catch(() => {});
      }).catch(() => {
        browserEvents = null;
      });
    await browserEvents;
    if (!diagnosticEvents)
      diagnosticEvents = listen("campus:diagnostic", (event) => {
        if (!stopping && child)
          void rpc(
            "diagnostics.record",
            event.payload as Record<string, unknown>,
          ).catch(() => {});
      }).catch(() => {
        diagnosticEvents = null;
      });
    await diagnosticEvents;
    const command = Command.sidecar("binaries/calix-engine");
    command.stdout.on("data", (line: string) => {
      if (current !== generation) return;
      let message;
      try {
        message = JSON.parse(line);
      } catch {
        return;
      }
      if (!message || typeof message !== "object" || Array.isArray(message))
        return;
      if (message.event) {
        browserMessage(message);
        for (const listener of listeners) {
          try {
            listener(message);
          } catch {
            /* Other subscribers still receive the event. */
          }
        }
        return;
      }
      const request = pending.get(message.id);
      if (!request) return;
      pending.delete(message.id);
      clearTimeout(request.timer);
      if (message.error) request.reject(new Error(message.error));
      else {
        if (request.method === "diagnostics.enable")
          void invoke("campus_debug", {
            enabled: message.result === true,
          }).catch(() => {});
        request.resolve(message.result);
      }
    });
    const failed = (message: string) => {
      if (current !== generation) return;
      generation++;
      failAll(message);
    };
    command.on("error", () => failed("일정 서비스 연결이 끊겼습니다."));
    command.on("close", () => failed("일정 서비스가 종료되었습니다."));
    const spawned = await command.spawn();
    if (current !== generation) {
      await spawned.kill().catch(() => {});
      throw new Error("일정 서비스를 시작하지 못했습니다.");
    }
    child = spawned;
  })().catch((error) => {
    if (current === generation) starting = null;
    throw error;
  });
  return starting;
}
export async function rpc<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  if (stopping && method !== "quit") throw new Error("종료 중입니다.");
  const id = ++sequence;
  if (!isTauri()) {
    const response = await fetch("/api", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, method, params }),
    });
    if (!response.ok) throw new Error("일정 서비스에 연결하지 못했습니다.");
    const payload = await response.json();
    if (payload.error) throw new Error(payload.error);
    return payload.result;
  }
  await start();
  if (stopping && method !== "quit") throw new Error("종료 중입니다.");
  if (!child) throw new Error("일정 서비스를 시작하지 못했습니다.");
  if (pending.size >= 128)
    throw new Error("처리 중인 작업이 많습니다. 잠시 후 다시 시도하세요.");
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error("처리 시간이 초과되었습니다."));
    }, 120000);
    pending.set(id, {
      resolve: (value) => resolve(value as T),
      reject,
      timer,
      method,
    });
    child!
      .write(JSON.stringify({ id, method, params }) + "\n")
      .catch((error) => {
        pending.delete(id);
        clearTimeout(timer);
        reject(error);
      });
  });
}
export async function stopEngine(install = false) {
  stopping = true;
  if (isTauri()) await invoke("campus_cancel").catch(() => {});
  if (starting) {
    try {
      await starting;
    } catch (error) {
      stopping = false;
      throw error;
    }
  }
  if (!isTauri()) {
    try {
      await rpc("quit", { install });
    } catch (error) {
      stopping = false;
      throw error;
    }
    return;
  }
  if (!child) return;
  let timer: ReturnType<typeof setTimeout> | undefined,
    done: () => void = () => {};
  const closed = new Promise<void>((resolve, reject) => {
    done = () => {
      clearTimeout(timer);
      resolve();
    };
    timer = setTimeout(() => {
      stopped.delete(done);
      reject(new Error("동기화 종료를 기다리는 중입니다."));
    }, 20000);
    stopped.add(done);
  });
  // Observe both promises immediately, including a quit response racing process exit.
  try {
    await Promise.all([
      rpc("quit", { install }).catch((error) => {
        if (child) throw error;
      }),
      closed,
    ]);
  } catch (error) {
    stopping = false;
    throw error;
  } finally {
    clearTimeout(timer);
    stopped.delete(done);
  }
}
