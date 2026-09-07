import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import type { AppData, CourseSearchResult, PendingRequirement } from '../../shared/types';
import {
  type PlanningMode,
  displayClassroom,
  displaySlots,
  findConflicts,
  findScheduledCourseByOffering,
  formatCredits,
  parseNodeSlots,
  requirementCourseCode,
} from '../../shared/domain/planner';

export function OfferingModal({
  requirement,
  semesterName,
  status,
  error,
  offerings,
  data,
  activeSemesterId,
  planningMode,
  onClose,
  onSchedule,
}: {
  requirement: PendingRequirement;
  semesterName: string;
  status: 'idle' | 'loading' | 'error';
  error: string;
  offerings: CourseSearchResult[];
  data: AppData;
  activeSemesterId: string;
  planningMode: PlanningMode;
  onClose: () => void;
  onSchedule: (offering: CourseSearchResult, force: boolean) => boolean;
}) {
  const code = requirementCourseCode(requirement);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
      <div className="max-h-[86vh] w-full max-w-3xl overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="border-b border-slate-200 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">{requirement.title}</h2>
              <p className="mt-1 text-sm text-slate-500">
                {code ? `依課碼 ${code} 選擇要排入 ${semesterName} 的班別。` : `選擇要排入 ${semesterName} 的實際開課班別。`}
              </p>
            </div>
            <button onClick={onClose} className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100">✕</button>
          </div>
        </div>
        <div className="max-h-[68vh] overflow-y-auto p-4">
          {status === 'loading' && <p className="text-sm text-slate-500">查詢開課資料中...</p>}
          {status === 'error' && <p className="text-sm text-red-600">{error}</p>}
          {status === 'idle' && offerings.length === 0 && <p className="text-sm text-slate-500">查無符合的開課班別。</p>}
          <div className="space-y-3">
            {offerings.map((offering) => {
              const conflicts = findConflicts(offering, data, activeSemesterId);
              const alreadyAdded = Boolean(findScheduledCourseByOffering(offering, data, activeSemesterId));
              const conflictBlocksSchedule = conflicts.length > 0 && planningMode !== 'lottery';
              const hasSlots = parseNodeSlots(offering.node).length > 0;
              return (
                <div key={`${offering.course_no}-${offering.node}-${offering.teacher}`} className="rounded-md border border-slate-200 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-950">{offering.course_name}</p>
                      <p className="mt-1 text-sm text-slate-500">
                        {offering.course_no}・{offering.teacher || '未列教師'}・{formatCredits(offering.credits)} 學分
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        {displaySlots(parseNodeSlots(offering.node))}・{displayClassroom(offering.classroom)}
                      </p>
                      {offering.contents && <p className="mt-1 text-xs text-slate-400">{offering.contents}</p>}
                      {!hasSlots && (
                        <p className="mt-2 text-sm text-amber-600">此課程沒有節次資料，無法檢查衝堂。</p>
                      )}
                      {alreadyAdded && (
                        <p className="mt-2 flex items-center gap-1 text-sm text-emerald-600">
                          <CheckCircle2 className="h-4 w-4" />
                          已排入目前學期
                        </p>
                      )}
                      {!alreadyAdded && conflicts.length > 0 && (
                        <p className={`mt-2 flex items-center gap-1 text-sm ${planningMode === 'lottery' ? 'text-amber-600' : 'text-red-600'}`}>
                          <AlertTriangle className="h-4 w-4" />
                          {planningMode === 'lottery' ? '同時段競爭：' : '與 '}
                          {conflicts.map((course) => course.name).join('、')}
                          {planningMode === 'lottery' ? '，可作為同時段志願' : ' 衝堂'}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <button
                        onClick={() => {
                          if (onSchedule(offering, false)) onClose();
                        }}
                        disabled={alreadyAdded || conflictBlocksSchedule}
                        className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                      >
                        {alreadyAdded ? '已加入' : '排入課表'}
                      </button>
                      {!alreadyAdded && conflictBlocksSchedule && (
                        <button
                          onClick={() => {
                            if (onSchedule(offering, true)) onClose();
                          }}
                          className="rounded-md border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
                        >
                          仍要加入
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
