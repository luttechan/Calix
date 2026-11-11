import { useEffect, useRef, useState, type InputHTMLAttributes } from "react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & {
  value: number;
  onValueChange: (value: number) => void;
};

export function NumberField({ value, onValueChange, onFocus, onBlur, ...props }: Props) {
  const [draft, setDraft] = useState(String(value));
  const focused = useRef(false);
  useEffect(() => { if (!focused.current) setDraft(String(value)); }, [value]);
  return (
    <input {...props} type="number" value={draft}
      onFocus={event => {
        focused.current = true;
        if (Number(event.currentTarget.value) === 0) event.currentTarget.select();
        onFocus?.(event);
      }}
      onBlur={event => {
        focused.current = false;
        if (draft === "" || !Number.isFinite(Number(draft))) setDraft(String(value));
        onBlur?.(event);
      }}
      onChange={event => {
        const next = event.target.value.replace(/^(-?)0+(?=\d)/, "$1");
        setDraft(next);
        if (next !== "" && Number.isFinite(Number(next))) onValueChange(Number(next));
      }}
    />
  );
}
