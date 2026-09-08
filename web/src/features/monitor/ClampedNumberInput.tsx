import React, { useEffect, useState } from 'react';

interface ClampedNumberInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange' | 'min' | 'max' | 'step' | 'type'> {
  value: number;
  min: number;
  max: number;
  step?: number;
  /** 使用者離開欄位（或按 Enter）時才回呼，值已夾在 [min, max] 內 */
  onCommit: (value: number) => void;
}

/**
 * 可清空重打的數字輸入框：編輯期間保留原始字串，失焦時才解析並夾到範圍內。
 * 直接在 onChange 夾值會讓使用者無法先清空再輸入新數字。
 */
const ClampedNumberInput: React.FC<ClampedNumberInputProps> = ({ value, min, max, step, onCommit, onBlur, onKeyDown, ...rest }) => {
  const [text, setText] = useState(String(value));

  useEffect(() => {
    setText(String(value));
  }, [value]);

  const commit = () => {
    const parsed = parseInt(text, 10);
    const next = Number.isNaN(parsed) ? value : Math.min(max, Math.max(min, parsed));
    setText(String(next));
    if (next !== value) onCommit(next);
  };

  return (
    <input
      {...rest}
      type="number"
      inputMode="numeric"
      min={min}
      max={max}
      step={step}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={(e) => { commit(); onBlur?.(e); }}
      onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); onKeyDown?.(e); }}
    />
  );
};

export default ClampedNumberInput;
