import { rpc } from "./bridge";

type MenuRead = "attendance.read" | "grades.read" | "calendar.year" | "focus.totals" |
  "semester.roster" | "anki.read" | "anv.status";

type Entry = { value?: unknown; request?: Promise<unknown>; updatedAt?: number };
const entries = new Map<MenuRead, Map<string, Entry>>();
const lifetime: Partial<Record<MenuRead, number>> = {
  "focus.totals": 30_000,
  "anki.read": 60_000,
  "anv.status": 60_000,
};

function keyFor(params: Record<string, unknown>) {
  return JSON.stringify(params, Object.keys(params).sort());
}

export function peekMenuRead<T>(method: MenuRead, params: Record<string, unknown> = {}): T | undefined {
  return entries.get(method)?.get(keyFor(params))?.value as T | undefined;
}

export function readMenu<T>(method: MenuRead, params: Record<string, unknown> = {}): Promise<T> {
  const key = keyFor(params);
  let group = entries.get(method);
  if (!group) entries.set(method, group = new Map());
  let entry = group.get(key);
  if (!entry) {
    if (group.size >= 24) group.delete(group.keys().next().value!);
    group.set(key, entry = {});
  }
  if (entry.request) return entry.request as Promise<T>;
  if (entry.updatedAt !== undefined && Date.now() - entry.updatedAt < (lifetime[method] ?? Infinity)) {
    return Promise.resolve(entry.value as T);
  }
  const result = entry;
  result.request = rpc<T>(method, params).then(value => {
    result.value = value;
    result.updatedAt = Date.now();
    return value;
  }).finally(() => { result.request = undefined; });
  return result.request as Promise<T>;
}

export function rememberMenuRead(method: MenuRead, params: Record<string, unknown>, value: unknown) {
  let group = entries.get(method);
  if (!group) entries.set(method, group = new Map());
  if (!group.has(keyFor(params)) && group.size >= 24) group.delete(group.keys().next().value!);
  group.set(keyFor(params), { value, updatedAt: Date.now() });
}

export function invalidateMenuReads(...methods: MenuRead[]) {
  if (methods.length === 0) entries.clear();
  else for (const method of methods) entries.delete(method);
}
