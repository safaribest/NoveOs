import { useEffect, useRef, useState } from "react";

interface TypewriterTextProps {
  text: string;
  speed?: number;
  className?: string;
  cursorClassName?: string;
  onComplete?: () => void;
}

/**
 * 增量打字机组件。
 *
 * 当 `text` 追加新内容时，仅对新增部分执行逐字动画；
 * 当 `text` 发生非追加变化（回退/替换）时，直接整体更新，避免闪烁。
 */
export function TypewriterText({
  text,
  speed = 10,
  className,
  cursorClassName = "animate-pulse",
  onComplete,
}: TypewriterTextProps) {
  const [state, setState] = useState({ displayed: text, pending: "" });
  const lastTextRef = useRef(text);

  // text 变化时更新待输出队列
  useEffect(() => {
    if (text === lastTextRef.current) return;
    lastTextRef.current = text;

    setState((prev) => {
      if (text.startsWith(prev.displayed)) {
        return { ...prev, pending: text.slice(prev.displayed.length) };
      }
      return { displayed: "", pending: text };
    });
  }, [text]);

  // 逐字输出 pending 中的内容
  useEffect(() => {
    if (state.pending.length === 0) {
      if (state.displayed === text) onComplete?.();
      return;
    }

    const chunk = Math.max(1, Math.floor(state.pending.length / 16));
    const timer = setTimeout(() => {
      const added = state.pending.slice(0, chunk);
      setState((prev) => ({
        displayed: prev.displayed + added,
        pending: prev.pending.slice(chunk),
      }));
    }, speed);

    return () => clearTimeout(timer);
  }, [state.pending, state.displayed, text, speed, onComplete]);

  return (
    <span className={className}>
      {state.displayed}
      {state.pending.length > 0 && (
        <span className={`ml-0.5 align-middle ${cursorClassName}`}>|</span>
      )}
    </span>
  );
}
