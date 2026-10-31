import { beforeEach, expect, test, vi } from "vitest";

const mock = vi.hoisted(() => ({
  commands: [] as any[],
  spawn: null as null | ((child: any) => Promise<any>),
}));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: () => true }));
vi.mock("@tauri-apps/plugin-shell", () => ({
  Command: {
    sidecar: () => {
      const handlers: Record<string, Function> = {};
      const writes: string[] = [];
      const child = {
        write: vi.fn(async (value: string) => {
          writes.push(value);
        }),
        kill: vi.fn(async () => {}),
      };
      const command = {
        handlers,
        writes,
        child,
        stdout: {
          on: (_event: string, callback: Function) => {
            handlers.stdout = callback;
          },
        },
        on: (event: string, callback: Function) => {
          handlers[event] = callback;
        },
        spawn: vi.fn(() =>
          mock.spawn ? mock.spawn(child) : Promise.resolve(child),
        ),
      };
      mock.commands.push(command);
      return command;
    },
  },
}));

beforeEach(() => {
  vi.resetModules();
  mock.commands.length = 0;
  mock.spawn = null;
});
async function boot() {
  const bridge = await import("./bridge");
  const request = bridge.rpc("bootstrap");
  await vi.waitFor(() => expect(mock.commands[0]?.writes.length).toBe(1));
  const command = mock.commands[0];
  const id = JSON.parse(command.writes[0]).id;
  command.handlers.stdout(JSON.stringify({ id, result: true }));
  await request;
  return { bridge, command };
}

test("shutdown does not let console polling respawn the engine", async () => {
  const { bridge, command } = await boot();
  const closing = bridge.stopEngine();
  await vi.waitFor(() => expect(command.writes.length).toBe(2));
  await expect(bridge.rpc("diagnostics.read")).rejects.toThrow("종료 중");
  const id = JSON.parse(command.writes[1]).id;
  command.handlers.stdout(JSON.stringify({ id, result: true }));
  command.handlers.close();
  await closing;
  await expect(bridge.rpc("bootstrap")).rejects.toThrow("종료 중");
  expect(mock.commands.length).toBe(1);
});

test("a delayed close from the old process cannot kill a new connection", async () => {
  const { bridge, command: old } = await boot();
  old.handlers.error();
  const request = bridge.rpc("bootstrap");
  await vi.waitFor(() => expect(mock.commands[1]?.writes.length).toBe(1));
  const current = mock.commands[1];
  old.handlers.close();
  const id = JSON.parse(current.writes[0]).id;
  current.handlers.stdout(JSON.stringify({ id, result: "new process" }));
  await expect(request).resolves.toBe("new process");
  current.handlers.close();
});

test("malformed messages and one failing subscriber do not block other responses", async () => {
  const { bridge, command } = await boot();
  const cleanup = bridge.subscribe(() => {
    throw Error("broken subscriber");
  });
  const healthy = vi.fn();
  const cleanupHealthy = bridge.subscribe(healthy);
  expect(() => command.handlers.stdout("null")).not.toThrow();
  expect(() => command.handlers.stdout("[]")).not.toThrow();
  command.handlers.stdout(JSON.stringify({ event: "sync-state", busy: false }));
  expect(healthy).toHaveBeenCalledOnce();
  cleanup();
  cleanupHealthy();
  command.handlers.close();
});

test("shutdown while startup is pending cannot dispatch an ordinary request", async () => {
  let finish: () => void = () => {};
  mock.spawn = (child) =>
    new Promise((resolve) => {
      finish = () => resolve(child);
    });
  const bridge = await import("./bridge");
  const request = bridge.rpc("bootstrap").catch((error) => error);
  await vi.waitFor(() => expect(mock.commands.length).toBe(1));
  const closing = bridge.stopEngine();
  finish();
  expect(((await request) as Error).message).toContain("종료 중");
  const command = mock.commands[0];
  await vi.waitFor(() => expect(command.writes.length).toBe(1));
  const row = JSON.parse(command.writes[0]);
  expect(row.method).toBe("quit");
  command.handlers.stdout(JSON.stringify({ id: row.id, result: true }));
  command.handlers.close();
  await closing;
});

test("a child arriving after startup failure is stopped without affecting its replacement", async () => {
  let finish: () => void = () => {};
  mock.spawn = (child) =>
    new Promise((resolve) => {
      finish = () => resolve(child);
    });
  const bridge = await import("./bridge");
  const oldRequest = bridge.rpc("bootstrap").catch((error) => error);
  await vi.waitFor(() => expect(mock.commands.length).toBe(1));
  const old = mock.commands[0];
  old.handlers.error();
  mock.spawn = null;
  const currentRequest = bridge.rpc("bootstrap");
  await vi.waitFor(() => expect(mock.commands[1]?.writes.length).toBe(1));
  finish();
  expect(await oldRequest).toBeInstanceOf(Error);
  expect(old.child.kill).toHaveBeenCalledOnce();
  const current = mock.commands[1];
  current.handlers.stdout(
    JSON.stringify({ id: JSON.parse(current.writes[0]).id, result: true }),
  );
  await expect(currentRequest).resolves.toBe(true);
  current.handlers.close();
});
