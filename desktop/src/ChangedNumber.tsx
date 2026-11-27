import { useLayoutEffect, useRef } from "react";
import { motionReduced } from "./motion";

export function ChangedNumber({ value }: { value: string | number | null | undefined }) {
  const element = useRef<HTMLSpanElement>(null);
  const previous = useRef(value);
  useLayoutEffect(() => {
    const before = previous.current;
    previous.current = value;
    if (before === value || before == null || value == null || !element.current || motionReduced()) return;
    const animation = element.current.animate(
      [{ opacity: .3, transform: "translateY(6px) scale(.9)" }, { opacity: 1, transform: "none" }],
      { duration: 240, easing: "cubic-bezier(.18,1,.28,1)" },
    );
    return () => animation.cancel();
  }, [value]);
  return <span ref={element} className="changed-number">{value ?? "—"}</span>;
}
