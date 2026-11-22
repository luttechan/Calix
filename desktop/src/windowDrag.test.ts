import { afterEach, describe, expect, it, vi } from "vitest";
import type { MouseEvent } from "react";
import { dragWindow } from "./windowDrag";

const commands = vi.hoisted(() => ({
  drag: vi.fn(async () => {}),
  maximize: vi.fn(async () => {}),
  isTauri: vi.fn(() => true),
}));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: commands.isTauri }));
vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => ({ startDragging: commands.drag, toggleMaximize: commands.maximize }),
}));

class Target {
  constructor(private control = false) {}
  closest() { return this.control ? this : null; }
}

function press(target: Target, button = 0, detail = 1) {
  vi.stubGlobal("Element", Target);
  const preventDefault = vi.fn();
  dragWindow({ target, button, detail, preventDefault } as unknown as MouseEvent<HTMLElement>);
  return preventDefault;
}

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("window title bar", () => {
  it("starts native dragging from a non-interactive descendant", () => {
    expect(press(new Target())).toHaveBeenCalledOnce();
    expect(commands.drag).toHaveBeenCalledOnce();
  });

  it("leaves mouse controls and non-primary clicks alone", () => {
    expect(press(new Target(true))).not.toHaveBeenCalled();
    expect(press(new Target(), 2)).not.toHaveBeenCalled();
    expect(commands.drag).not.toHaveBeenCalled();
  });

  it("toggles maximization on double-click", () => {
    press(new Target(), 0, 2);
    expect(commands.maximize).toHaveBeenCalledOnce();
    expect(commands.drag).not.toHaveBeenCalled();
  });
});
