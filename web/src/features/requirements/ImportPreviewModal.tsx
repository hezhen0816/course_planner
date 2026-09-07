import { type ApiImportPreview, formatCredits } from '../../shared/domain/planner';

export function ImportPreviewModal({
  preview,
  onConfirm,
  onClose,
}: {
  preview: ApiImportPreview;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const name = String(preview.requirement_set.name || 'PDF 匯入需求');
  const totalCredits = preview.requirement_set.total_credits as number | undefined;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
      <div className="max-h-[86vh] w-full max-w-2xl overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="border-b border-slate-200 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">匯入預覽</h2>
              <p className="mt-1 text-sm text-slate-500">{name}{totalCredits ? `・${formatCredits(totalCredits)} 學分` : ''}</p>
            </div>
            <button onClick={onClose} className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100">✕</button>
          </div>
        </div>
        <div className="max-h-[62vh] overflow-y-auto p-4">
          {preview.warnings.length > 0 && (
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {preview.warnings.join('；')}
            </div>
          )}
          <div className="space-y-2">
            {preview.pending_requirements.map((requirement) => (
              <div key={String(requirement.id)} className="rounded-md border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium text-slate-900">{String(requirement.title)}</p>
                  <span className="text-sm text-slate-500">
                    {formatCredits(requirement.required_credits as number | null | undefined)} 學分
                  </span>
                </div>
                {requirement.note ? <p className="mt-1 text-sm text-slate-500">{String(requirement.note)}</p> : null}
              </div>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-200 p-4">
          <button onClick={onClose} className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            取消
          </button>
          <button onClick={onConfirm} className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
            加入待修池
          </button>
        </div>
      </div>
    </div>
  );
}
