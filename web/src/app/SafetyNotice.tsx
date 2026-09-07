import { AlertTriangle } from 'lucide-react';

export function SafetyNotice() {
  return (
    <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
      <span>選課輔助工具，不自動搶課、不輪詢名額；送出官方系統前仍需使用者確認。</span>
    </div>
  );
}
