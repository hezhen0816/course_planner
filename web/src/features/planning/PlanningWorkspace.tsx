import { currentEnrollmentPhase, formatPhaseRange, nextEnrollmentPhase, type EnrollmentPhase } from '../../shared/domain/enrollmentCalendar';
import { useState, type CSSProperties } from 'react';
import { ArrowDown, ArrowUp, CheckCircle2, Clock, Loader2, Trash2 } from 'lucide-react';
import type { AppData, Course, GpaStatus, OfficialSelectionRegisteredCourse, OfficialSelectionRequiredPresetCourse, OfficialSelectionSyncResponse, PendingRequirement, PlannerStats } from '../../shared/types';
import { parseCourseDepartment } from '../../shared/domain/courseDepartments';
import {
  PERIODS,
  type PlanningMode,
  type RequirementStatus,
  displayClassroom,
  displaySlots,
  formatCredits,
  isHistoryImportedCourse,
  parseNodeSlots,
  requirementCourseCode,
} from '../../shared/domain/planner';

const PERIOD_TIME_LABELS: Record<string, { start: string; end: string }> = {
  '1': { start: '08:10', end: '09:00' },
  '2': { start: '09:10', end: '10:00' },
  '3': { start: '10:20', end: '11:10' },
  '4': { start: '11:20', end: '12:10' },
  '5': { start: '12:20', end: '13:10' },
  '6': { start: '13:20', end: '14:10' },
  '7': { start: '14:20', end: '15:10' },
  '8': { start: '15:30', end: '16:20' },
  '9': { start: '16:30', end: '17:20' },
  '10': { start: '17:30', end: '18:20' },
  A: { start: '18:25', end: '19:15' },
  B: { start: '19:20', end: '20:10' },
  C: { start: '20:15', end: '21:05' },
  D: { start: '21:10', end: '22:00' },
};
function ScheduleLegend() {
  const items = [
    { label: '本系必修', className: 'border-rose-200 bg-rose-50' },
    { label: '本系選修', className: 'border-blue-200 bg-blue-50' },
    { label: '通識', className: 'border-violet-200 bg-violet-50' },
    { label: '體育', className: 'border-lime-200 bg-lime-50' },
    { label: '雙主修', className: 'border-teal-200 bg-teal-50' },
    { label: '輔系', className: 'border-fuchsia-200 bg-fuchsia-50' },
    { label: '待加簽', className: 'border-amber-300 bg-amber-50' },
  ];

  return (
    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1">
          <span className={`h-2.5 w-2.5 rounded border ${item.className}`} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

type CourseTone = 'required' | 'elective' | 'general' | 'pe' | 'doubleMajor' | 'minor' | 'virtual' | 'group' | 'conflict' | 'other';

type CourseClassification = {
  label: string;
  tone: CourseTone;
};

const GENERAL_COURSE_DEPARTMENT_CODES = new Set(['GE', 'TC', 'SA']);

function classifyCourseByCode(
  courseNo: string,
  requireOption: string | undefined,
  data: AppData,
  fallbackTone: CourseTone = 'other',
): CourseClassification {
  const departmentCode = parseCourseDepartment(courseNo)?.code;
  const programDepartments = data.settings?.programDepartments;
  const normalizedRequireOption = (requireOption || '').trim().toUpperCase();
  if (departmentCode && departmentCode === programDepartments?.doubleMajorDepartmentCode) {
    return { label: '雙主修', tone: 'doubleMajor' };
  }
  if (departmentCode && departmentCode === programDepartments?.minorDepartmentCode) {
    return { label: '輔系', tone: 'minor' };
  }
  if (departmentCode && departmentCode === programDepartments?.homeDepartmentCode) {
    if (normalizedRequireOption === 'R' || normalizedRequireOption.includes('必')) {
      return { label: '本系必修', tone: 'required' };
    }
    if (normalizedRequireOption === 'E' || normalizedRequireOption.includes('選')) {
      return { label: '本系選修', tone: 'elective' };
    }
    return { label: '本系', tone: fallbackTone };
  }
  if (departmentCode && GENERAL_COURSE_DEPARTMENT_CODES.has(departmentCode)) {
    return { label: '通識', tone: 'general' };
  }
  if (departmentCode === 'PE') {
    return { label: '體育', tone: 'pe' };
  }

  if (normalizedRequireOption === 'R' || normalizedRequireOption.includes('必')) {
    return { label: '必修', tone: 'required' };
  }
  if (normalizedRequireOption === 'E' || normalizedRequireOption.includes('選')) {
    return { label: '選修', tone: 'elective' };
  }
  return { label: '未分類', tone: fallbackTone };
}

function scheduleToneClass(tone: CourseTone, conflicting = false): string {
  if (conflicting) return 'border-red-300 bg-red-50 text-red-950';
  const toneClasses: Record<CourseTone, string> = {
    required: 'border-rose-200 bg-rose-50 text-rose-950',
    elective: 'border-blue-200 bg-blue-50 text-blue-950',
    general: 'border-violet-200 bg-violet-50 text-violet-950',
    pe: 'border-lime-200 bg-lime-50 text-lime-950',
    doubleMajor: 'border-teal-200 bg-teal-50 text-teal-950',
    minor: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-950',
    virtual: 'border-amber-300 bg-amber-50 text-amber-950',
    group: 'border-amber-300 bg-amber-50 text-amber-950',
    conflict: 'border-red-300 bg-red-50 text-red-950',
    other: 'border-blue-100 bg-white text-slate-900',
  };
  return toneClasses[tone];
}

function scheduleAccentClass(tone: CourseTone, conflicting = false): string {
  if (conflicting) return 'bg-red-400';
  const toneClasses: Record<CourseTone, string> = {
    required: 'bg-rose-400',
    elective: 'bg-blue-400',
    general: 'bg-violet-400',
    pe: 'bg-lime-400',
    doubleMajor: 'bg-teal-400',
    minor: 'bg-fuchsia-400',
    virtual: 'bg-amber-400',
    group: 'bg-amber-400',
    conflict: 'bg-red-400',
    other: 'bg-blue-500',
  };
  return toneClasses[tone];
}

function badgeToneClass(tone: CourseTone, conflicting = false): string {
  if (conflicting) return 'bg-red-500 text-white';
  const toneClasses: Record<CourseTone, string> = {
    required: 'bg-rose-100 text-rose-700',
    elective: 'bg-blue-100 text-blue-700',
    general: 'bg-violet-100 text-violet-700',
    pe: 'bg-lime-100 text-lime-700',
    doubleMajor: 'bg-teal-100 text-teal-700',
    minor: 'bg-fuchsia-100 text-fuchsia-700',
    virtual: 'bg-amber-100 text-amber-700',
    group: 'bg-amber-100 text-amber-700',
    conflict: 'bg-red-500 text-white',
    other: 'bg-blue-100 text-blue-700',
  };
  return toneClasses[tone];
}

function groupedItemToneClass(tone: CourseTone): string {
  const toneClasses: Record<CourseTone, string> = {
    required: 'border-rose-100 bg-rose-50',
    elective: 'border-blue-100 bg-blue-50',
    general: 'border-violet-100 bg-violet-50',
    pe: 'border-lime-100 bg-lime-50',
    doubleMajor: 'border-teal-100 bg-teal-50',
    minor: 'border-fuchsia-100 bg-fuchsia-50',
    virtual: 'border-amber-100 bg-amber-50',
    group: 'border-amber-100 bg-amber-50',
    conflict: 'border-red-100 bg-red-50',
    other: 'border-slate-100 bg-white',
  };
  return toneClasses[tone];
}

function gpaBadgeLabel(gpa?: number | null, status?: GpaStatus): string {
  if (typeof gpa === 'number' && Number.isFinite(gpa)) return `GPA ${gpa.toFixed(2)}`;
  if (status === 'no_data') return '查無 GPA';
  if (status === 'error') return 'GPA 錯誤';
  return 'GPA 未啟用';
}

function gpaBadgeClass(gpa?: number | null, status?: GpaStatus): string {
  if (typeof gpa === 'number' && Number.isFinite(gpa)) return 'bg-indigo-50 text-indigo-700 ring-indigo-100';
  if (status === 'no_data') return 'bg-amber-50 text-amber-700 ring-amber-100';
  if (status === 'error') return 'bg-red-50 text-red-700 ring-red-100';
  return 'bg-slate-100 text-slate-500 ring-slate-200';
}

function GpaBadge({ gpa, status }: { gpa?: number | null; status?: GpaStatus }) {
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-1.5 py-0 text-[10px] font-medium ring-1 ${gpaBadgeClass(gpa, status)}`}>
      {gpaBadgeLabel(gpa, status)}
    </span>
  );
}

type SelectionChanceEstimate = {
  selectedCount: number;
  capacity: number;
  pressureRatio: number;
  probabilityPercent: number;
};

function estimateSelectionChance(
  selectedCount?: number | null,
  capacity?: number | null,
): SelectionChanceEstimate | null {
  if (
    selectedCount === null
    || selectedCount === undefined
    || capacity === null
    || capacity === undefined
    || !Number.isFinite(selectedCount)
    || !Number.isFinite(capacity)
    || capacity <= 0
  ) {
    return null;
  }
  const pressureRatio = selectedCount / capacity;
  const probabilityPercent = pressureRatio > 0 ? Math.min(100, 100 / pressureRatio) : 100;
  return {
    selectedCount,
    capacity,
    pressureRatio,
    probabilityPercent,
  };
}

function formatProbabilityPercent(value: number): string {
  if (value >= 99.95) return '100%';
  return `${value.toFixed(1)}%`;
}

function SelectionChanceBadge({
  selectedCount,
  capacity,
}: {
  selectedCount?: number | null;
  capacity?: number | null;
}) {
  const estimate = estimateSelectionChance(selectedCount, capacity);
  if (!estimate) {
    return (
      <span className="inline-flex shrink-0 items-center rounded-full bg-slate-100 px-1.5 py-0 text-[10px] font-medium text-slate-500 ring-1 ring-slate-200">
        機率未公告
      </span>
    );
  }

  const isOverCapacity = estimate.selectedCount > estimate.capacity;
  const toneClass = isOverCapacity
    ? 'bg-red-50 text-red-700 ring-red-100'
    : 'bg-emerald-50 text-emerald-700 ring-emerald-100';
  return (
    <>
      <span
        className={`inline-flex shrink-0 items-center rounded-full px-1.5 py-0 text-[10px] font-medium ring-1 ${toneClass}`}
        title={`估算方式：人數 ${estimate.selectedCount} / 名額 ${estimate.capacity} = ${estimate.pressureRatio.toFixed(2)} 倍，選上估 ${formatProbabilityPercent(estimate.probabilityPercent)}`}
      >
        選上估 {formatProbabilityPercent(estimate.probabilityPercent)}
      </span>
      {isOverCapacity && (
        <span className="inline-flex shrink-0 items-center rounded-full bg-amber-50 px-1.5 py-0 text-[10px] font-medium text-amber-700 ring-1 ring-amber-100">
          建議前排
        </span>
      )}
    </>
  );
}

function EnrollmentCountBadge({
  selectedCount,
  capacity,
}: {
  selectedCount?: number | null;
  capacity?: number | null;
}) {
  if (selectedCount == null || capacity == null) return null;
  return (
    <span className="inline-flex shrink-0 items-center rounded-full bg-white/65 px-1.5 py-0 text-[10px] font-medium text-slate-600 ring-1 ring-slate-200">
      {selectedCount}/{capacity} 人
    </span>
  );
}

function planningModeLabel(mode: PlanningMode): string {
  return mode === 'lottery' ? '初選志願' : '加退選';
}

function planningModeDescription(mode: PlanningMode): string {
  return mode === 'lottery'
    ? '同時段多門課會視為競爭志願，抽中一門後其他同時段或同課名志願會失效。'
    : '加退選接近先搶先贏，同時段課程應視為真衝堂並在送出前處理。';
}

function scheduledCredits(courses: Course[]): number {
  return courses.reduce((sum, course) => sum + (course.category === 'pe' ? 0 : course.credits), 0);
}

export function PlanningWorkspace({
  data,
  stats,
  activeSemester,
  enrolledCourses,
  querySemester,
  planningMode,
  plannerMessage,
  officialSelection,
  officialActionCourseNo,
  officialOrderStatus,
  onModeChange,
  onJoinOfficialCourse,
  onRemoveOfficialCourse,
  onSaveOfficialOrder,
  onDeleteCourse,
}: {
  data: AppData;
  stats: PlannerStats;
  activeSemester?: AppData['semesters'][number];
  /** 學校那邊實際選上的課（校務同步取自選課清單 ChooseList/D01/D01） */
  enrolledCourses: Course[];
  querySemester: string;
  planningMode: PlanningMode;
  plannerMessage: string;
  officialSelection: OfficialSelectionSyncResponse | null;
  officialActionCourseNo: string | null;
  officialOrderStatus: 'idle' | 'loading';
  onModeChange: (mode: PlanningMode) => void;
  onJoinOfficialCourse: (courseNo: string, courseName: string) => void;
  onRemoveOfficialCourse: (courseNo: string, courseName: string) => void;
  onSaveOfficialOrder: (orderedCourseNos: string[]) => void;
  onDeleteCourse: (courseId: string) => void;
}) {
  const virtualCourses = activeSemester?.courses.filter((course) => !isHistoryImportedCourse(course)) || [];
  const virtualCredits = scheduledCredits(virtualCourses);
  const officialRegisteredCount = officialSelection?.registered_count || 0;
  const officialAvailableCount = officialSelection?.available_count || 0;
  const officialRegisteredCredits = (officialSelection?.registered_courses || []).reduce(
    (sum, course) => sum + (course.credits || 0),
    0,
  );
  const currentPlanningCredits = officialRegisteredCredits + virtualCredits;
  const enrolledCredits = scheduledCredits(enrolledCourses);
  const addDropCredits = enrolledCredits + virtualCredits;
  const officialRequiredPresetCourses = officialSelection ? requiredPresetCoursesForDisplay(officialSelection) : [];
  const officialRequiredPresetCount = officialRequiredPresetCourses.length;
  const officialSelectionListCount = officialSelection?.selection_list_rows.length || 0;
  const officialScheduleHasData = officialSelection ? hasOfficialScheduleWeekdayData(officialSelection.schedule_rows) : false;
  const showSelectionListWithoutSchedule = Boolean(officialSelection && officialSelectionListCount > 0 && !officialScheduleHasData);
  const totalPlanningItems = officialRegisteredCount + officialAvailableCount + virtualCourses.length;
  const syncedAtLabel = data.schoolSync?.scheduleSyncedAt
    ? `課表 ${new Date(data.schoolSync.scheduleSyncedAt).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })}`
    : officialSelection ? formatSyncTime(officialSelection.synced_at) : '尚未同步';
  const enrollmentPhase: EnrollmentPhase = currentEnrollmentPhase(querySemester);
  const upcomingPhase = nextEnrollmentPhase(querySemester);
  const isPreregistrationPhase = enrollmentPhase.kind === 'preregistration';
  const [showWeekend, setShowWeekend] = useState(false);
  const modeOptions: Array<{ value: PlanningMode; label: string }> = [
    { value: 'lottery', label: '初選志願' },
    { value: 'addDrop', label: '加退選' },
  ];

  return (
    <section id="schedule-preview" className="mt-6 rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">選課工作台</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">官方選課狀態</h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-500">
              {planningModeDescription(planningMode)}
            </p>
          </div>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
              {modeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => onModeChange(option.value)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                    planningMode === option.value
                      ? 'bg-white text-blue-700 shadow-sm'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
              <span className="text-slate-500">官方同步：</span>
              <span className="font-medium text-slate-900">{syncedAtLabel}</span>
            </div>
          </div>
        </div>
        <ScheduleLegend />
        {plannerMessage && (
          <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
            {plannerMessage}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-0 xl:grid-cols-[300px_minmax(0,1fr)_280px]">
        <aside className="border-b border-slate-200 p-4 xl:border-b-0 xl:border-r">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-900">
                {planningMode === 'addDrop' ? '選課清單與待加簽' : '官方狀態與待加簽'}
              </h3>
              <p className="mt-1 text-xs text-slate-500">{planningModeLabel(planningMode)}模式 · 官方資料優先</p>
            </div>
            <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
              {planningMode === 'addDrop' ? enrolledCourses.length + virtualCourses.length : totalPlanningItems} 項
            </span>
          </div>

          {/* 目前階段由教務處時程表推導（shared/domain/enrollmentCalendar），不讓使用者手動宣告 */}
          <div className={`mt-3 rounded-md border px-3 py-2 text-xs ${
            enrollmentPhase.kind === 'closed'
              ? 'border-slate-200 bg-slate-50 text-slate-600'
              : 'border-blue-200 bg-blue-50 text-blue-800'
          }`}>
            {/* 側欄只有 300px：標題與日期分兩行，日期本身不斷行（原本會拆成「9/7 09:00 –」＋「9/21 17:00」） */}
            {enrollmentPhase.kind === 'closed' ? (
              <>
                <div>目前不在選課階段</div>
                {upcomingPhase && (
                  <div className="mt-0.5">
                    下一階段：<span className="font-semibold">{upcomingPhase.label}</span>
                    <span className="ml-1 whitespace-nowrap">{formatPhaseRange(upcomingPhase)}</span>
                  </div>
                )}
              </>
            ) : (
              <>
                <div>目前階段：<span className="font-semibold">{enrollmentPhase.label}</span></div>
                <div className="mt-0.5 whitespace-nowrap">{formatPhaseRange(enrollmentPhase)}</div>
              </>
            )}
          </div>

          <div className="mt-4 space-y-4">
            {planningMode === 'addDrop' ? (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-slate-700">目前選課清單</h4>
                  <span className="text-xs text-slate-500">{enrolledCourses.length} 門・{formatCredits(enrolledCredits)} 學分</span>
                </div>
                {enrolledCourses.length === 0 ? (
                  <div className="rounded-md border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
                    先用「資料同步」取得校務系統的選課清單，這裡就會列出已選上的課。
                  </div>
                ) : (
                  <div className="space-y-2">
                    {enrolledCourses.map((course) => (
                      <PlanningListCourse key={course.id} course={course} data={data} />
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <>
                {!isPreregistrationPhase && (
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    目前不是初選階段，官方初選清單本來就會是空的；要看實際選上的課請切到「加退選」。
                  </div>
                )}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-slate-700">
                      已登記志願
                    </h4>
                    <span className="text-xs text-slate-500">
                      {officialRegisteredCount} 門
                    </span>
                  </div>
                  {officialSelection ? (
                    <OfficialRegisteredList
                      data={data}
                      selection={officialSelection}
                      actionCourseNo={officialActionCourseNo}
                      orderStatus={officialOrderStatus}
                      onRemoveOfficialCourse={onRemoveOfficialCourse}
                      onSaveOfficialOrder={onSaveOfficialOrder}
                    />
                  ) : (
                    <div className="rounded-md border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
                      先同步官方選課狀態，才能顯示已登記志願。
                    </div>
                  )}
                </div>

                <div className="border-t border-slate-100 pt-4">
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-slate-700">待加入清單</h4>
                    <span className="text-xs text-slate-500">
                      {officialAvailableCount} 門
                    </span>
                  </div>
                  {officialSelection ? (
                    <OfficialAvailableList
                      selection={officialSelection}
                      actionCourseNo={officialActionCourseNo}
                      onJoinOfficialCourse={onJoinOfficialCourse}
                    />
                  ) : (
                    <div className="rounded-md border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
                      先同步官方選課狀態，才能顯示待加入清單。
                    </div>
                  )}
                </div>
              </>
            )}

            <div className="border-t border-slate-100 pt-4">
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-sm font-semibold text-slate-700">待加簽課程</h4>
                <span className="text-xs text-slate-500">{virtualCourses.length} 門・{formatCredits(virtualCredits)} 學分</span>
              </div>
              {virtualCourses.length === 0 ? (
                <div className="rounded-md border border-dashed border-amber-200 bg-amber-50 px-3 py-4 text-center text-sm text-amber-700">
                  官方拒絕或需要加簽追蹤的課程會在這裡保留，並標在功課表上。
                </div>
              ) : (
                <div className="space-y-2">
                  {virtualCourses.map((course) => (
                    <PlanningListCourse
                      key={course.id}
                      course={course}
                      data={data}
                      onDelete={() => onDeleteCourse(course.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </aside>

        <div className="min-w-0 border-b border-slate-200 xl:border-b-0 xl:border-r">
          <div className="border-b border-slate-100 p-4">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="text-base font-semibold text-slate-900">官方功課表</h3>
                <p className="mt-1 text-sm text-slate-500">
                  {planningMode === 'addDrop'
                    ? `已選上 ${enrolledCourses.length} 門 · 待加簽 ${virtualCourses.length} 門`
                    : `已登記 ${officialRegisteredCount} 門 · 學校預排 ${officialRequiredPresetCount} 門 · 待加簽 ${virtualCourses.length} 門`}
                </p>
                {showSelectionListWithoutSchedule ? (
                  <p className="mt-2 text-xs text-amber-600">
                    已取得選課清單 {officialSelectionListCount} 門，但官方功課表資料仍為空；目前課表會以課碼補查節次顯示，查不到節次的課不會硬塞進課表。
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <WeekendToggleButton
                  showWeekend={showWeekend}
                  onToggle={() => setShowWeekend((current) => !current)}
                />
                <p className="text-xs text-slate-400 sm:hidden">課表可左右滑動查看更多星期欄位。</p>
              </div>
            </div>
          </div>
          <PlanningScheduleGrid
            officialScheduleRows={officialSelection?.schedule_rows || []}
            officialRegisteredCourses={officialSelection?.registered_courses || []}
            officialRequiredPresetCourses={officialRequiredPresetCourses}
            enrolledCourses={planningMode === 'addDrop' ? enrolledCourses : []}
            virtualCourses={virtualCourses}
            showWeekend={showWeekend}
            mode={planningMode}
            data={data}
            onDeleteCourse={onDeleteCourse}
          />
        </div>

        <aside className="p-4">
          <h3 className="text-base font-semibold text-slate-900">規劃檢查</h3>
          <p className="mt-1 text-xs text-slate-500">依目前選課階段解讀衝堂、互斥與學分限制。</p>

          <div className="mt-4 grid grid-cols-2 gap-3">
            {planningMode === 'addDrop' ? (
              <>
                <MetricBox label="已選上" value={`${enrolledCourses.length} 門`} tone="emerald" />
                <MetricBox label="待加入清單" value={String(officialAvailableCount)} tone="blue" />
                <MetricBox label="目前學分" value={`${formatCredits(addDropCredits)} 學分`} tone="amber" />
                <MetricBox label="待加簽" value={`${virtualCourses.length} 門`} tone="slate" />
              </>
            ) : (
              <>
                <MetricBox label="已登記志願" value={String(officialRegisteredCount)} tone="emerald" />
                <MetricBox label="待加入清單" value={String(officialAvailableCount)} tone="blue" />
                <MetricBox label="目前學分" value={`${formatCredits(currentPlanningCredits)} 學分`} tone="amber" />
                <MetricBox label="待加簽" value={`${virtualCourses.length} 門`} tone="slate" />
              </>
            )}
          </div>

          <div className="mt-4 rounded-lg border border-slate-200 p-3">
            <h4 className="text-sm font-semibold text-slate-800">畢業門檻影響</h4>
            <div className="mt-3 space-y-3 text-sm">
              <ProgressSummary label="總學分" value={stats.total} target={data.targets.total} />
              <ProgressSummary label="本系必修" value={stats.homeCompulsory} target={data.targets.home_compulsory} />
              <ProgressSummary label="通識" value={stats.gen_ed} target={data.targets.gen_ed} />
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function OfficialRegisteredList({
  data,
  selection,
  actionCourseNo,
  orderStatus,
  onRemoveOfficialCourse,
  onSaveOfficialOrder,
}: {
  data: AppData;
  selection: OfficialSelectionSyncResponse;
  actionCourseNo: string | null;
  orderStatus: 'idle' | 'loading';
  onRemoveOfficialCourse: (courseNo: string, courseName: string) => void;
  onSaveOfficialOrder: (orderedCourseNos: string[]) => void;
}) {
  const originalOrder = selection.registered_courses.map((course) => course.course_no.trim().toUpperCase()).join('|');
  const draftSyncKey = `${selection.synced_at}:${originalOrder}`;
  const [draftState, setDraftState] = useState({
    syncKey: draftSyncKey,
    courses: selection.registered_courses,
  });
  const draftCourses = draftState.syncKey === draftSyncKey ? draftState.courses : selection.registered_courses;

  if (selection.registered_courses.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-blue-200 bg-blue-50 px-3 py-4 text-center text-sm text-blue-700">
        官方目前沒有已登記志願。
      </div>
    );
  }

  const draftOrder = draftCourses.map((course) => course.course_no.trim().toUpperCase()).join('|');
  const isDirty = originalOrder !== draftOrder;
  const isOrderSaving = orderStatus === 'loading';
  const moveDraftCourse = (index: number, direction: -1 | 1) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= draftCourses.length || isOrderSaving) return;
    const nextCourses = [...draftCourses];
    const [item] = nextCourses.splice(index, 1);
    nextCourses.splice(nextIndex, 0, item);
    setDraftState({ syncKey: draftSyncKey, courses: nextCourses });
  };

  return (
    <div className="space-y-2">
      <p className="rounded-md bg-slate-50 px-2.5 py-2 text-xs text-slate-500">
        選上機率依目前選課人數與名額估算，僅供志願序排序參考。
      </p>
      {isDirty && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onSaveOfficialOrder(draftCourses.map((course) => course.course_no))}
            disabled={!isDirty || isOrderSaving}
            className="inline-flex flex-1 items-center justify-center gap-1 rounded-md bg-blue-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500"
          >
            {isOrderSaving && <Loader2 className="h-3 w-3 animate-spin" />}
            儲存志願序
          </button>
          <button
            type="button"
            onClick={() => setDraftState({ syncKey: draftSyncKey, courses: selection.registered_courses })}
            disabled={!isDirty || isOrderSaving}
            className="rounded-md border border-blue-200 bg-white px-2 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            還原
          </button>
        </div>
      )}

      {draftCourses.map((course, index) => {
        const normalizedCourseNo = course.course_no.trim().toUpperCase();
        const isLoading = actionCourseNo === normalizedCourseNo || isOrderSaving;
        const classification = classifyCourseByCode(course.course_no, course.require_option, data);
        return (
        <div key={`${course.raw_priority}-${course.course_no}`} className={`rounded-md border p-2.5 ${
          isDirty ? 'border-blue-200 bg-blue-50' : scheduleToneClass(classification.tone)
        }`}>
          <div className="flex items-start gap-2">
            <div className="mt-0.5 flex w-6 shrink-0 flex-col items-center gap-0.5">
              <div className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold ${badgeToneClass(classification.tone)}`}>
                {index + 1}
              </div>
              <div className="flex flex-col">
                <button
                  type="button"
                  onClick={() => moveDraftCourse(index, -1)}
                  disabled={index === 0 || isOrderSaving}
                  className="rounded p-0.5 text-slate-400 hover:bg-blue-100 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-30"
                  aria-label="提高官方志願序"
                >
                  <ArrowUp className="h-3 w-3" />
                </button>
                <button
                  type="button"
                  onClick={() => moveDraftCourse(index, 1)}
                  disabled={index === draftCourses.length - 1 || isOrderSaving}
                  className="rounded p-0.5 text-slate-400 hover:bg-blue-100 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-30"
                  aria-label="降低官方志願序"
                >
                  <ArrowDown className="h-3 w-3" />
                </button>
              </div>
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-900">{course.course_name}</p>
              <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1 text-xs text-slate-500">
                <span
                  className="min-w-0 truncate"
                  title={[
                    course.course_no,
                    classification.label,
                    course.credits != null ? `${formatCredits(course.credits)} 學分` : '',
                    course.require_option || '',
                    course.teacher || '',
                  ].filter(Boolean).join('・')}
                >
                  {[
                    course.course_no,
                    classification.label,
                    course.credits != null ? `${formatCredits(course.credits)} 學分` : '',
                  ].filter(Boolean).join('・')}
                </span>
                <GpaBadge gpa={course.gpa} status={course.gpa_status} />
                <SelectionChanceBadge selectedCount={course.selected_count} capacity={course.capacity} />
                <EnrollmentCountBadge selectedCount={course.selected_count} capacity={course.capacity} />
              </div>
            </div>
            <button
              type="button"
              onClick={() => onRemoveOfficialCourse(course.course_no, course.course_name)}
              disabled={isLoading}
              className="inline-flex shrink-0 items-center gap-1 rounded-md border border-blue-200 bg-white px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading && <Loader2 className="h-3 w-3 animate-spin" />}
              取消
            </button>
          </div>
        </div>
        );
      })}
    </div>
  );
}

function requiredPresetCoursesForDisplay(
  selection: OfficialSelectionSyncResponse,
): OfficialSelectionRequiredPresetCourse[] {
  const byCourseNo = new Map<string, OfficialSelectionRequiredPresetCourse>();
  (selection.required_preset_rows || []).forEach((row) => {
    const courseNo = rowValue(row, ['課碼', '課程代碼', '課號']).trim().toUpperCase();
    if (!courseNo) return;
    byCourseNo.set(courseNo, {
      course_no: courseNo,
      course_name: rowValue(row, ['課程名稱', '課名']),
    });
  });
  (selection.required_preset_courses || []).forEach((course) => {
    const courseNo = course.course_no.trim().toUpperCase();
    if (!courseNo) return;
    byCourseNo.set(courseNo, { ...byCourseNo.get(courseNo), ...course, course_no: courseNo });
  });

  const registeredByCourseNo = new Map(
    selection.registered_courses.map((course) => [course.course_no.trim().toUpperCase(), course]),
  );
  return Array.from(byCourseNo.values()).map((course) => {
    const registered = registeredByCourseNo.get(course.course_no.trim().toUpperCase());
    return {
      ...course,
      course_name: course.course_name || registered?.course_name || '',
      credits: course.credits ?? registered?.credits,
      require_option: course.require_option || registered?.require_option || '',
      teacher: course.teacher || registered?.teacher || '',
      classroom: course.classroom || registered?.classroom || '',
      node: course.node || registered?.node || '',
      contents: course.contents || registered?.contents || '',
      selected_count: course.selected_count ?? registered?.selected_count,
      capacity: course.capacity ?? registered?.capacity,
      gpa: course.gpa ?? registered?.gpa,
      gpa_status: course.gpa_status || registered?.gpa_status,
    };
  });
}

function OfficialAvailableList({
  selection,
  actionCourseNo,
  onJoinOfficialCourse,
}: {
  selection: OfficialSelectionSyncResponse;
  actionCourseNo: string | null;
  onJoinOfficialCourse: (courseNo: string, courseName: string) => void;
}) {
  if (selection.available_courses.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
        官方目前沒有待加入課程。
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {selection.available_courses.map((course) => {
        const normalizedCourseNo = course.course_no.trim().toUpperCase();
        const isLoading = actionCourseNo === normalizedCourseNo;
        return (
        <div key={course.course_no} className="rounded-md border border-slate-200 bg-white p-2.5">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{course.course_name}</p>
              <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1 text-xs text-slate-500">
                <span className="min-w-0 truncate" title={course.teacher || '未列教師'}>
                  {course.course_no}
                </span>
                <GpaBadge gpa={course.gpa} status={course.gpa_status} />
              </div>
            </div>
            <button
              type="button"
              onClick={() => onJoinOfficialCourse(course.course_no, course.course_name)}
              disabled={isLoading}
              className="inline-flex shrink-0 items-center gap-1 rounded-md border border-amber-300 px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading && <Loader2 className="h-3 w-3 animate-spin" />}
              加入登記
            </button>
          </div>
        </div>
        );
      })}
    </div>
  );
}

function formatSyncTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '剛剛';
  return date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
}

function WeekendToggleButton({
  showWeekend,
  onToggle,
}: {
  showWeekend: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={showWeekend}
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${
        showWeekend
          ? 'border-blue-200 bg-blue-50 text-blue-700'
          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
      }`}
    >
      <span className={`flex h-4 w-7 items-center rounded-full p-0.5 transition-colors ${
        showWeekend ? 'bg-blue-600' : 'bg-slate-300'
      }`}>
        <span className={`h-3 w-3 rounded-full bg-white shadow-sm transition-transform ${
          showWeekend ? 'translate-x-3' : ''
        }`} />
      </span>
      顯示週末
    </button>
  );
}

function PlanningScheduleGrid({
  officialScheduleRows,
  officialRegisteredCourses,
  officialRequiredPresetCourses,
  enrolledCourses,
  virtualCourses,
  showWeekend,
  mode,
  data,
  onDeleteCourse,
}: {
  officialScheduleRows: Record<string, string>[];
  officialRegisteredCourses: OfficialSelectionRegisteredCourse[];
  officialRequiredPresetCourses: OfficialSelectionRequiredPresetCourse[];
  enrolledCourses: Course[];
  virtualCourses: Course[];
  showWeekend: boolean;
  mode: PlanningMode;
  data: AppData;
  onDeleteCourse: (courseId: string) => void;
}) {
  return (
    <OfficialScheduleTable
      rows={officialScheduleRows}
      officialRegisteredCourses={officialRegisteredCourses}
      officialRequiredPresetCourses={officialRequiredPresetCourses}
      enrolledCourses={enrolledCourses}
      virtualCourses={virtualCourses}
      showWeekend={showWeekend}
      mode={mode}
      data={data}
      onDeleteVirtualCourse={onDeleteCourse}
    />
  );
}

function OfficialScheduleTable({
  rows,
  officialRegisteredCourses,
  officialRequiredPresetCourses,
  enrolledCourses,
  virtualCourses,
  showWeekend,
  mode,
  data,
  onDeleteVirtualCourse,
}: {
  rows: Record<string, string>[];
  officialRegisteredCourses: OfficialSelectionRegisteredCourse[];
  officialRequiredPresetCourses: OfficialSelectionRequiredPresetCourse[];
  enrolledCourses: Course[];
  virtualCourses: Course[];
  showWeekend: boolean;
  mode: PlanningMode;
  data: AppData;
  onDeleteVirtualCourse: (courseId: string) => void;
}) {
  const [hoveredEventId, setHoveredEventId] = useState<string | null>(null);
  const visibleWeekdays = showWeekend ? OFFICIAL_WEEKDAYS : OFFICIAL_WEEKDAYS.slice(0, 5);
  const displayRows = officialRowsForDisplay(rows);
  const events = layoutScheduleEvents([
    ...buildOfficialScheduleEvents(visibleWeekdays, officialRegisteredCourses, officialRequiredPresetCourses, data),
    // 已選上的課用 official 樣式畫：本地刪除不會真的退選，所以不給刪除鈕
    ...buildVirtualScheduleEvents(enrolledCourses, visibleWeekdays, data, 'official'),
    ...buildVirtualScheduleEvents(virtualCourses, visibleWeekdays, data),
  ]);
  const gridTemplateColumns = `72px repeat(${visibleWeekdays.length}, minmax(132px, 1fr))`;
  const gridTemplateRows = `42px repeat(${displayRows.length}, 64px)`;
  return (
    <div className="p-4">
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <div
          className="relative min-w-[780px] text-sm"
          style={{ display: 'grid', gridTemplateColumns, gridTemplateRows }}
        >
          <div className="sticky left-0 z-20 flex items-center justify-center border-b border-r border-slate-200 bg-slate-50 text-xs font-semibold text-slate-500">
            時間
          </div>
          {visibleWeekdays.map((weekday, index) => (
            <div
              key={weekday.label}
              className="flex items-center justify-center border-b border-r border-slate-200 bg-slate-50 text-sm font-semibold text-slate-700"
              style={{ gridColumn: index + 2, gridRow: 1 }}
            >
              {weekday.label.replace('星期', '週')}
            </div>
          ))}
          {displayRows.map((row, rowIndex) => {
            const period = getOfficialScheduleCell(row, '節次') || PERIODS[rowIndex] || String(rowIndex + 1);
            return (
              <div
                key={`time-${period}`}
                className="sticky left-0 z-10 flex flex-col items-center justify-center border-b border-r border-slate-200 bg-slate-50 text-center"
                style={{ gridColumn: 1, gridRow: rowIndex + 2 }}
              >
                <span className="text-sm font-semibold text-slate-800">{period}</span>
                <span className="mt-1 whitespace-pre-line text-[10px] leading-tight text-slate-500">
                  {formatOfficialTime(getOfficialScheduleCell(row, '時間'))}
                </span>
              </div>
            );
          })}
          {displayRows.flatMap((row, rowIndex) => (
            visibleWeekdays.map((weekday, dayIndex) => {
              const hasEvent = events.some((event) => (
                event.weekdayLabel === weekday.label
                && rowIndex >= event.startIndex
                && rowIndex < event.startIndex + event.span
              ));
              return (
                <div
                  key={`bg-${weekday.label}-${getOfficialScheduleCell(row, '節次') || rowIndex}`}
                  className={`border-b border-r border-slate-200 ${
                    hasEvent ? 'bg-blue-50/55' : 'bg-white'
                  }`}
                  style={{ gridColumn: dayIndex + 2, gridRow: rowIndex + 2 }}
                />
              );
            })
          ))}
          {events.map((event) => {
            const dayIndex = visibleWeekdays.findIndex((weekday) => weekday.label === event.weekdayLabel);
            if (dayIndex < 0) return null;
            const isHovered = hoveredEventId === event.id;
            const isVirtual = event.kind === 'virtual';
            const isGroup = event.kind === 'group';
            const isNarrow = event.laneCount > 1;
            const conflicting = isVirtual && mode !== 'lottery' && event.laneCount > 1;
            const showMeta = !isGroup && Boolean(event.meta) && (!isNarrow || event.span > 1);
            const stackOffset = isNarrow ? Math.min(event.lane, 4) : 0;
            const stackWidth = isNarrow ? 'calc(100% - 22px)' : 'calc(100% - 6px)';
            const overlapHoverClass = isNarrow
              ? 'hover:w-[calc(100%-6px)] hover:-translate-x-[var(--overlap-shift)] hover:scale-[1.02] hover:overflow-visible'
              : '';
            const titleText = isGroup && event.groupedEvents
              ? event.groupedEvents.map(formatGroupedEventLabel).join('\n')
              : event.rank ? `${event.rank}. ${event.title}` : event.title;
            const eventStyle: CSSProperties & { '--overlap-shift'?: string } = {
              gridColumn: dayIndex + 2,
              gridRow: `${event.startIndex + 2} / span ${event.span}`,
              width: stackWidth,
              marginLeft: `${3 + stackOffset * 7}px`,
              marginTop: `${4 + stackOffset * 7}px`,
              zIndex: isHovered ? 30 : 10 + Math.min(event.lane, 9),
              '--overlap-shift': `${stackOffset * 7}px`,
            };
            return (
              <div
                key={event.id}
                className={`group/event my-1 flex min-h-0 overflow-hidden rounded-md border shadow-sm transition-all duration-150 ease-out hover:-translate-y-0.5 hover:shadow-lg ${overlapHoverClass} ${
                  scheduleToneClass(event.tone, conflicting)
                }`}
                style={eventStyle}
                title={titleText}
                onMouseEnter={() => setHoveredEventId(event.id)}
                onMouseLeave={() => setHoveredEventId((current) => (current === event.id ? null : current))}
                onFocus={() => setHoveredEventId(event.id)}
                onBlur={() => setHoveredEventId((current) => (current === event.id ? null : current))}
              >
                <span className={`w-1 shrink-0 ${scheduleAccentClass(event.tone, conflicting)}`} />
                <div className="flex min-w-0 flex-1 flex-col px-1.5 py-1">
                  {isGroup && event.groupedEvents ? (
                    <GroupedScheduleEventContent event={event} />
                  ) : (
                    <div className="flex items-start gap-1">
                      {!isVirtual && event.rank ? (
                        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${badgeToneClass(event.tone, conflicting)}`}>
                          {event.rank}
                        </span>
                      ) : null}
                      <p className="min-w-0 flex-1 truncate text-xs font-semibold leading-5 group-hover/event:whitespace-normal group-hover/event:break-words">
                        {event.title}
                      </p>
                      {event.course ? (
                        <button
                          type="button"
                          onClick={() => onDeleteVirtualCourse(event.course!.id)}
                          className="shrink-0 rounded p-0.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
                          title="移除待加簽課程"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      ) : null}
                    </div>
                  )}
                  {(!isGroup && (showMeta || (isNarrow && event.meta))) ? (
                    <p className={`mt-0.5 truncate text-[11px] group-hover/event:whitespace-normal group-hover/event:break-words ${
                      conflicting ? 'text-red-700' : 'text-slate-600'
                    }`}>
                      {event.meta}
                    </p>
                  ) : null}
                  {conflicting ? (
                    <span className="mt-auto inline-flex w-fit items-center rounded-full bg-red-200/70 px-1.5 text-[10px] font-medium text-red-800">
                      衝堂
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function GroupedScheduleEventContent({ event }: { event: ScheduleEvent }) {
  const groupedEvents = event.groupedEvents || [];
  const visibleEvents = groupedEvents.slice(0, 3);
  const hiddenCount = Math.max(0, groupedEvents.length - visibleEvents.length);
  return (
    <div className="min-w-0">
      <div className="mb-1 flex items-center justify-between gap-1">
        <p className="truncate text-xs font-semibold leading-5 group-hover/event:whitespace-normal group-hover/event:break-words">
          {groupedEvents.length} 門同時段
        </p>
        {hiddenCount > 0 ? (
          <span className="shrink-0 rounded-full bg-white/75 px-1.5 text-[10px] font-medium text-slate-600">
            +{hiddenCount}
          </span>
        ) : null}
      </div>
      <div className="space-y-0.5">
        {visibleEvents.map((item) => (
          <div key={item.id} className={`flex min-w-0 items-start gap-1 rounded border px-1 py-0.5 ${groupedItemToneClass(item.tone)}`}>
            {item.rank ? (
              <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${badgeToneClass(item.tone)}`}>
                {item.rank}
              </span>
            ) : (
              <span className={`h-2 w-2 shrink-0 rounded-full ${scheduleAccentClass(item.tone)}`} />
            )}
            <span className="min-w-0 truncate text-[11px] font-medium leading-4 text-slate-800 group-hover/event:whitespace-normal group-hover/event:break-words">
              {item.title}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const OFFICIAL_WEEKDAYS = [
  { label: '星期一', aliases: ['星期一', '週一', '禮拜一', '一'] },
  { label: '星期二', aliases: ['星期二', '週二', '禮拜二', '二'] },
  { label: '星期三', aliases: ['星期三', '週三', '禮拜三', '三'] },
  { label: '星期四', aliases: ['星期四', '週四', '禮拜四', '四'] },
  { label: '星期五', aliases: ['星期五', '週五', '禮拜五', '五'] },
  { label: '星期六', aliases: ['星期六', '週六', '禮拜六', '六'] },
  { label: '星期日', aliases: ['星期日', '星期天', '週日', '週天', '禮拜日', '禮拜天', '日', '天'] },
];
const OFFICIAL_SCHEDULE_COLUMNS = ['節次', '時間', ...OFFICIAL_WEEKDAYS.map((weekday) => weekday.label)];
const OFFICIAL_DAY_CODE_BY_LABEL: Record<string, string> = {
  星期一: 'M',
  星期二: 'T',
  星期三: 'W',
  星期四: 'R',
  星期五: 'F',
  星期六: 'S',
  星期日: 'U',
};

function officialRowsForDisplay(rows: Record<string, string>[]): Record<string, string>[] {
  if (rows.length > 0) return rows;
  return PERIODS.map((period) => {
    const time = PERIOD_TIME_LABELS[period];
    return {
      節次: period,
      時間: time ? `${time.start}~${time.end}` : '',
    };
  });
}

function hasOfficialScheduleWeekdayData(rows: Record<string, string>[]): boolean {
  return rows.some((row) => (
    OFFICIAL_WEEKDAYS.some((weekday) => Boolean(getOfficialScheduleCell(row, weekday.label)))
  ));
}

type ScheduleEvent = {
  id: string;
  kind: 'official' | 'virtual' | 'group';
  weekdayLabel: string;
  startIndex: number;
  span: number;
  title: string;
  meta: string;
  tone: CourseTone;
  classificationLabel?: string;
  rank?: number;
  course?: Course;
  groupedEvents?: RawScheduleEvent[];
  lane: number;
  laneCount: number;
  overlapsOfficial: boolean;
};

type RawScheduleEvent = Omit<ScheduleEvent, 'lane' | 'laneCount' | 'overlapsOfficial'>;

function buildOfficialScheduleEvents(
  weekdays: typeof OFFICIAL_WEEKDAYS,
  registeredCourses: OfficialSelectionRegisteredCourse[],
  requiredPresetCourses: OfficialSelectionRequiredPresetCourse[],
  data: AppData,
): RawScheduleEvent[] {
  const presetCourseNos = new Set(requiredPresetCourses.map((course) => course.course_no.trim().toUpperCase()));
  const rankedRegisteredCourses = registeredCourses.filter((course) => (
    !presetCourseNos.has(course.course_no.trim().toUpperCase())
  ));
  return [
    ...buildOfficialRegisteredCourseEvents(requiredPresetCourses, weekdays, data, false),
    ...buildOfficialRegisteredCourseEvents(rankedRegisteredCourses, weekdays, data, true),
  ];
}

function buildOfficialRegisteredCourseEvents(
  courses: Array<OfficialSelectionRegisteredCourse | OfficialSelectionRequiredPresetCourse>,
  weekdays: typeof OFFICIAL_WEEKDAYS,
  data: AppData,
  showRank: boolean,
): RawScheduleEvent[] {
  const events: RawScheduleEvent[] = [];
  courses.forEach((course, courseIndex) => {
    weekdays.forEach((weekday) => {
      const dayCode = OFFICIAL_DAY_CODE_BY_LABEL[weekday.label];
      if (!dayCode) return;
      const slotPeriods = new Set(
        parseNodeSlots(course.node || '')
          .filter((slot) => slot.startsWith(dayCode))
          .map((slot) => slot.slice(dayCode.length)),
      );
      let periodIndex = 0;
      while (periodIndex < PERIODS.length) {
        if (!slotPeriods.has(PERIODS[periodIndex])) {
          periodIndex += 1;
          continue;
        }
        let endIndex = periodIndex + 1;
        while (endIndex < PERIODS.length && slotPeriods.has(PERIODS[endIndex])) {
          endIndex += 1;
        }
        const classification = classifyCourseByCode(course.course_no, course.require_option, data);
        events.push({
          id: `official-${showRank ? 'registered' : 'preset'}-${course.course_no}-${weekday.label}-${periodIndex}`,
          kind: 'official',
          weekdayLabel: weekday.label,
          startIndex: periodIndex,
          span: endIndex - periodIndex,
          title: course.course_name,
          meta: '',
          tone: classification.tone,
          classificationLabel: classification.label,
          rank: showRank ? ('priority' in course && course.priority ? course.priority : courseIndex + 1) : undefined,
        });
        periodIndex = endIndex;
      }
    });
  });
  return events;
}

function buildVirtualScheduleEvents(
  courses: Course[],
  weekdays: typeof OFFICIAL_WEEKDAYS,
  data: AppData,
  kind: 'virtual' | 'official' = 'virtual',
): RawScheduleEvent[] {
  const events: RawScheduleEvent[] = [];
  courses.forEach((course) => {
    weekdays.forEach((weekday) => {
      const dayCode = OFFICIAL_DAY_CODE_BY_LABEL[weekday.label];
      if (!dayCode) return;
      const slotPeriods = new Set(
        (course.scheduledOffering?.slots || [])
          .map((slot) => slot.trim().toUpperCase())
          .filter((slot) => slot.startsWith(dayCode))
          .map((slot) => slot.slice(dayCode.length)),
      );
      let periodIndex = 0;
      while (periodIndex < PERIODS.length) {
        if (!slotPeriods.has(PERIODS[periodIndex])) {
          periodIndex += 1;
          continue;
        }
        let endIndex = periodIndex + 1;
        while (endIndex < PERIODS.length && slotPeriods.has(PERIODS[endIndex])) {
          endIndex += 1;
        }
        const span = endIndex - periodIndex;
        const teacher = course.scheduledOffering?.teacher || course.details?.professor || '未列教師';
        const classification = classifyCourseByCode(
          course.scheduledOffering?.courseNo || '',
          course.scheduledOffering?.requireOption,
          data,
          kind === 'virtual' ? 'virtual' : 'other',
        );
        events.push({
          id: `${kind}-${course.id}-${weekday.label}-${periodIndex}`,
          kind,
          weekdayLabel: weekday.label,
          startIndex: periodIndex,
          span,
          title: course.name,
          meta: teacher,
          tone: classification.tone,
          classificationLabel: classification.label,
          course,
        });
        periodIndex = endIndex;
      }
    });
  });
  return events;
}

function layoutScheduleEvents(events: RawScheduleEvent[]): ScheduleEvent[] {
  const groupableEvents = groupSameSlotEvents(events);
  const grouped = new Map<string, RawScheduleEvent[]>();
  groupableEvents.forEach((event) => {
    grouped.set(event.weekdayLabel, [...(grouped.get(event.weekdayLabel) || []), event]);
  });

  const laidOut: ScheduleEvent[] = [];
  grouped.forEach((weekdayEvents) => {
    const sorted = [...weekdayEvents].sort((a, b) => (
      a.startIndex - b.startIndex
      || b.span - a.span
      || (a.kind === 'official' ? -1 : 1)
    ));
    const laneEnds: number[] = [];
    const assigned = sorted.map((event) => {
      const endIndex = event.startIndex + event.span;
      let lane = laneEnds.findIndex((laneEnd) => laneEnd <= event.startIndex);
      if (lane < 0) {
        lane = laneEnds.length;
        laneEnds.push(endIndex);
      } else {
        laneEnds[lane] = endIndex;
      }
      return { ...event, lane, laneCount: 1 };
    });

    assigned.forEach((event) => {
      const overlapping = assigned.filter((candidate) => (
        candidate.weekdayLabel === event.weekdayLabel
        && candidate.startIndex < event.startIndex + event.span
        && candidate.startIndex + candidate.span > event.startIndex
      ));
      laidOut.push({
        ...event,
        laneCount: Math.max(1, ...overlapping.map((candidate) => candidate.lane + 1)),
        overlapsOfficial: event.kind === 'virtual' && overlapping.some((candidate) => candidate.kind === 'official'),
      });
    });
  });

  return laidOut;
}

function groupSameSlotEvents(events: RawScheduleEvent[]): RawScheduleEvent[] {
  const groups = new Map<string, RawScheduleEvent[]>();
  events.forEach((event) => {
    const key = `${event.weekdayLabel}|${event.startIndex}|${event.span}`;
    groups.set(key, [...(groups.get(key) || []), event]);
  });

  return Array.from(groups.values()).flatMap((group) => {
    if (group.length <= 1) return group;
    const sorted = [...group].sort((a, b) => (
      (a.rank ?? 999) - (b.rank ?? 999)
      || a.title.localeCompare(b.title, 'zh-Hant')
    ));
    const first = sorted[0];
    return [{
      id: `group-${first.weekdayLabel}-${first.startIndex}-${first.span}-${sorted.map((event) => event.id).join('-')}`,
      kind: 'group',
      weekdayLabel: first.weekdayLabel,
      startIndex: first.startIndex,
      span: first.span,
      title: `${sorted.length} 門同時段`,
      meta: sorted.map(formatGroupedEventLabel).join(' / '),
      tone: 'group',
      classificationLabel: '同時段',
      groupedEvents: sorted,
    }];
  });
}

function formatGroupedEventLabel(event: RawScheduleEvent): string {
  return [event.rank ? `${event.rank}` : '', event.title].filter(Boolean).join(' ');
}

function compactOfficialKey(value: string): string {
  return value.replace(/\s+/g, '').replace(/[：:]/g, '');
}

function rowValue(row: Record<string, string>, aliases: string[]): string {
  const compactAliases = new Set(aliases.map(compactOfficialKey));
  const matched = Object.entries(row).find(([key]) => compactAliases.has(compactOfficialKey(key)));
  return matched?.[1] || '';
}

function getOfficialScheduleCell(row: Record<string, string>, label: string): string {
  const aliases = OFFICIAL_WEEKDAYS.find((weekday) => weekday.label === label)?.aliases || [label];
  const directLabels = label === '節次' || label === '時間' ? [label] : aliases;
  for (const key of directLabels) {
    const value = row[key];
    if (value) return value;
  }

  const compactAliases = directLabels.map(compactOfficialKey);
  const matched = Object.entries(row).find(([key, value]) => (
    Boolean(value) && compactAliases.some((alias) => compactOfficialKey(key) === alias)
  ));
  if (matched?.[1]) return matched[1];

  // Positional fallback is only safe for header-less rows. JSONB storage
  // reorders keys, so Object.values() no longer follows column order and an
  // empty 星期二 would otherwise render 星期三's course.
  const hasNamedColumns = Object.keys(row).some((key) => (
    OFFICIAL_SCHEDULE_COLUMNS.includes(compactOfficialKey(key))
  ));
  if (hasNamedColumns) return '';

  const columnIndex = OFFICIAL_SCHEDULE_COLUMNS.indexOf(label);
  if (columnIndex < 0) return '';
  return Object.values(row)[columnIndex] || '';
}

function formatOfficialTime(value: string | undefined): string {
  if (!value) return '';
  return value.replace(/~/g, '\n').replace(/～/g, '\n');
}

function PlanningListCourse({
  course,
  data,
  onDelete,
}: {
  course: Course;
  data: AppData;
  /** 省略即為唯讀（例如學校那邊已選上的課，本地刪除不會真的退選） */
  onDelete?: () => void;
}) {
  const slots = course.scheduledOffering?.slots || [];
  const classification = classifyCourseByCode(
    course.scheduledOffering?.courseNo || '',
    course.scheduledOffering?.requireOption,
    data,
    'virtual',
  );
  return (
    <div className={`rounded-md border p-2.5 ${scheduleToneClass(classification.tone)}`}>
      <div className="flex items-start gap-2">
        <div className={`mt-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-medium ${badgeToneClass(classification.tone)}`}>
          {classification.label}
        </div>
        <div className="min-w-0 flex-1 text-left">
          <p className="truncate text-sm font-semibold text-slate-900">{course.name}</p>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1 text-xs text-slate-500">
            <span className="min-w-0 truncate">
              {formatCredits(course.credits)} 學分
              {course.scheduledOffering?.teacher ? `・${course.scheduledOffering.teacher}` : ''}
            </span>
            <GpaBadge gpa={course.scheduledOffering?.gpa} status={course.scheduledOffering?.gpaStatus} />
            <SelectionChanceBadge
              selectedCount={course.scheduledOffering?.selectedCount}
              capacity={course.scheduledOffering?.capacity}
            />
            <EnrollmentCountBadge
              selectedCount={course.scheduledOffering?.selectedCount}
              capacity={course.scheduledOffering?.capacity}
            />
            <span className="min-w-0 truncate">
              {slots.length > 0 ? `${displaySlots(slots)}・${displayClassroom(course.scheduledOffering?.classroom)}` : '未提供節次'}
            </span>
          </div>
        </div>
        {onDelete && (
          <button
            type="button"
            onClick={onDelete}
            className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
            title="移除待加簽課程"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

function MetricBox({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'emerald' | 'blue' | 'amber' | 'red' | 'slate';
}) {
  const toneClass = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    blue: 'border-blue-200 bg-blue-50 text-blue-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    red: 'border-red-200 bg-red-50 text-red-700',
    slate: 'border-slate-200 bg-slate-50 text-slate-700',
  }[tone];
  return (
    <div className={`rounded-lg border p-3 ${toneClass}`}>
      <p className="text-xs font-medium opacity-80">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function ProgressSummary({
  label,
  value,
  target,
}: {
  label: string;
  value: number;
  target: number;
}) {
  const ratio = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{label}</span>
        <span>{formatCredits(value)} / {formatCredits(target)}</span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-slate-100">
        <div className="h-2 rounded-full bg-blue-600" style={{ width: `${ratio}%` }} />
      </div>
    </div>
  );
}

export function RequirementRow({
  requirement,
  status,
  onOpen,
  onDelete,
  onMoveUp,
  onMoveDown,
  canMoveUp = false,
  canMoveDown = false,
  rank,
}: {
  requirement: PendingRequirement;
  status?: RequirementStatus;
  onOpen: () => void;
  onDelete: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  canMoveUp?: boolean;
  canMoveDown?: boolean;
  rank?: number;
}) {
  const completed = Boolean(status?.completed);
  const code = requirementCourseCode(requirement);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onOpen();
        }
      }}
      className={`cursor-pointer rounded-md border p-3 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${completed ? 'border-emerald-200 bg-emerald-50 hover:bg-emerald-100' : 'border-slate-200 bg-white hover:bg-slate-50'}`}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">
          {rank || (completed ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <Clock className="h-4 w-4 text-slate-400" />)}
        </div>
        <div className="min-w-0 flex-1 text-left">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-slate-900">{requirement.title}</p>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
              {requirement.kind === 'credit_pool' ? '學分池' : requirement.kind === 'choice' ? '擇一' : '課程'}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {formatCredits(status?.earnedCredits || 0)} / {formatCredits(status?.targetCredits || requirement.requiredCredits || requirement.credits || 0)} 學分
            {code ? `・課碼 ${code}` : requirement.note ? `・${requirement.note}` : ''}
          </p>
        </div>
        {(onMoveUp || onMoveDown) && (
          <div className="flex shrink-0 flex-col gap-1">
            <button
              onClick={(event) => {
                event.stopPropagation();
                onMoveUp?.();
              }}
              disabled={!canMoveUp}
              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-30"
              title="志願序上移"
            >
              <ArrowUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(event) => {
                event.stopPropagation();
                onMoveDown?.();
              }}
              disabled={!canMoveDown}
              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-30"
              title="志願序下移"
            >
              <ArrowDown className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        <button
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
          className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
          title="移除需求"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
