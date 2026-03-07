import React from 'react';

interface ProgressBarProps {
  current: number;
  target: number;
  label: string;
  subLabel?: string;
  colorClass: string;
  isCount?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ current, target, label, subLabel, colorClass, isCount = false }) => {
  const percentage = target > 0 ? Math.min(100, (current / target) * 100) : 0;
  const unit = isCount ? '學期' : '學分';
  
  return (
    <div className="mb-3">
      <div className="flex justify-between items-end mb-1">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className="text-xs text-gray-500">
          {target > 0 ? `${current} / ${target} ${unit}` : `${current} ${unit} / 未設定`}
          {subLabel && <span className="ml-1">({subLabel})</span>}
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div 
          className={`h-2.5 rounded-full transition-all duration-500 ${colorClass}`} 
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
};
