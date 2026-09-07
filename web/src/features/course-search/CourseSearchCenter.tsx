import type { ReactNode } from 'react';
import { FileText, Loader2 } from 'lucide-react';
import type { AppData, Course, CourseSearchResult, CourseSemesterInfo } from '../../types';
import {
  type CapacityFilter,
  type ManualSearchSummary,
  type SearchMode,
  capacityLabel,
  capacityStatus,
  displayClassroom,
  displaySlots,
  findConflicts,
  findScheduledCourseByOffering,
  formatCredits,
  parseNodeSlots,
  requirementLabel,
} from '../../domain/planner';

type CourseSearchCenterProps = {
  data: AppData;
  courseSemesters: CourseSemesterInfo[];
  querySemester: string;
  currentCourseSemesterLabel: string;
  manualMode: SearchMode;
  manualQuery: string;
  manualStatus: 'idle' | 'loading' | 'error';
  manualError: string;
  manualSearchSummary: ManualSearchSummary | null;
  manualResults: CourseSearchResult[];
  filteredManualResults: CourseSearchResult[];
  teacherFilter: string;
  creditFilter: string;
  requireOptionFilter: string;
  timeFilter: string;
  capacityFilter: CapacityFilter;
  importStatus: 'idle' | 'loading' | 'error';
  importError: string;
  canRunManualSearch: boolean;
  virtualCourseCredits: number;
  activeSemesterId: string;
  onQuerySemesterChange: (semester: string) => void;
  onManualModeChange: (mode: SearchMode) => void;
  onManualQueryChange: (query: string) => void;
  onTeacherFilterChange: (teacher: string) => void;
  onCreditFilterChange: (credits: string) => void;
  onRequireOptionFilterChange: (option: string) => void;
  onTimeFilterChange: (time: string) => void;
  onCapacityFilterChange: (capacity: CapacityFilter) => void;
  onRunManualSearch: () => void | Promise<void>;
  onResetFilters: () => void;
  onPdfUpload: (file: File | undefined) => void | Promise<void>;
  onExportResults: () => void;
  officialActionCourseNo: string | null;
  onAddSelectionCourse: (offering: CourseSearchResult) => void;
  onDeleteVirtualCourse: (courseId: string) => void;
  onOpenPlanning: () => void;
};

export function CourseSearchCenter({
  data,
  courseSemesters,
  querySemester,
  currentCourseSemesterLabel,
  manualMode,
  manualQuery,
  manualStatus,
  manualError,
  manualSearchSummary,
  manualResults,
  filteredManualResults,
  teacherFilter,
  creditFilter,
  requireOptionFilter,
  timeFilter,
  capacityFilter,
  importStatus,
  importError,
  canRunManualSearch,
  virtualCourseCredits,
  activeSemesterId,
  onQuerySemesterChange,
  onManualModeChange,
  onManualQueryChange,
  onTeacherFilterChange,
  onCreditFilterChange,
  onRequireOptionFilterChange,
  onTimeFilterChange,
  onCapacityFilterChange,
  onRunManualSearch,
  onResetFilters,
  onPdfUpload,
  onExportResults,
  officialActionCourseNo,
  onAddSelectionCourse,
  onDeleteVirtualCourse,
  onOpenPlanning,
}: CourseSearchCenterProps) {
  const virtualCourses = data.selectionPlan?.courses || [];
  return (
    <div className="search-layout flex flex-col gap-5">
      {/* Filters live in a horizontal toolbar so the results table gets the full
          width and the 備註 column can show its text instead of truncating. */}
      <section className="search-filters rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">官方開課查詢</h2>
            <p className="mt-1 text-sm text-slate-500">以課名或課碼查詢台科大開課資料，比較節次與名額後加入選課清單。</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700">
              {importStatus === 'loading' ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              上傳雙主修 PDF
              <input
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(event) => {
                  void onPdfUpload(event.target.files?.[0]);
                  event.currentTarget.value = '';
                }}
              />
            </label>
          </div>
        </div>
        <form
          className="flex flex-wrap items-end gap-3 p-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (canRunManualSearch) void onRunManualSearch();
          }}
        >
          <FilterField label="學期" className="w-44">
            <select
              aria-label="查詢學期"
              value={querySemester}
              onChange={(event) => onQuerySemesterChange(event.target.value)}
              className={SELECT_CLASS}
            >
              {courseSemesters.length === 0 && <option value={querySemester}>{querySemester}</option>}
              {courseSemesters.map((semester) => (
                <option key={semester.semester} value={semester.semester}>
                  {semester.semester}{semester.english_label ? `・${semester.english_label}` : ''}
                </option>
              ))}
            </select>
          </FilterField>
          <FilterField label="課名 / 課碼" className="min-w-[260px] flex-1">
            <div className="grid grid-cols-[82px_minmax(0,1fr)] gap-2">
              <select
                aria-label="搜尋方式"
                value={manualMode}
                onChange={(event) => onManualModeChange(event.target.value as SearchMode)}
                className={SELECT_CLASS}
              >
                <option value="name">課名</option>
                <option value="code">課碼</option>
              </select>
              <input
                aria-label="課名或課碼"
                value={manualQuery}
                onChange={(event) => onManualQueryChange(event.target.value)}
                placeholder="資料結構"
                autoFocus
                className={INPUT_CLASS}
              />
            </div>
          </FilterField>
          <FilterField label="教師" className="w-36">
            <input
              aria-label="教師"
              value={teacherFilter}
              onChange={(event) => onTeacherFilterChange(event.target.value)}
              placeholder="教師姓名"
              className={INPUT_CLASS}
            />
          </FilterField>
          <FilterField label="必選修" className="w-24">
            <select
              aria-label="必選修"
              value={requireOptionFilter}
              onChange={(event) => onRequireOptionFilterChange(event.target.value)}
              className={SELECT_CLASS}
            >
              <option value="all">全部</option>
              <option value="R">必修</option>
              <option value="E">選修</option>
            </select>
          </FilterField>
          <FilterField label="學分" className="w-24">
            <select
              aria-label="學分"
              value={creditFilter}
              onChange={(event) => onCreditFilterChange(event.target.value)}
              className={SELECT_CLASS}
            >
              <option value="all">不限</option>
              <option value="0">0</option>
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
              <option value="4">4</option>
            </select>
          </FilterField>
          <FilterField label="節次" className="w-32">
            <input
              aria-label="節次"
              value={timeFilter}
              onChange={(event) => onTimeFilterChange(event.target.value)}
              placeholder="M3 或 W4"
              className={INPUT_CLASS}
            />
          </FilterField>
          <FilterField label="名額" className="w-28">
            <select
              aria-label="名額狀態"
              value={capacityFilter}
              onChange={(event) => onCapacityFilterChange(event.target.value as CapacityFilter)}
              className={SELECT_CLASS}
            >
              <option value="all">全部</option>
              <option value="available">尚有名額</option>
              <option value="full">額滿</option>
              <option value="unknown">未公告</option>
            </select>
          </FilterField>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={!canRunManualSearch}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              搜尋課程
            </button>
            <button
              type="button"
              onClick={onResetFilters}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              重設
            </button>
          </div>
          {importError && <p className="w-full text-sm text-red-600">{importError}</p>}
        </form>
      </section>

      <section className="min-w-0 rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div className="flex items-baseline gap-3">
            <h3 className="text-lg font-semibold text-slate-900">查詢結果</h3>
            <span className="text-sm text-slate-500">
              {manualSearchSummary
                ? `共找到 ${manualSearchSummary.resultCount} 筆，顯示 ${filteredManualResults.length} 筆`
                : `${currentCourseSemesterLabel} · 輸入條件後開始查詢`}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-3 text-sm text-slate-500">
            <button
              onClick={onExportResults}
              disabled={filteredManualResults.length === 0}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            >
              匯出結果
            </button>
          </div>
        </div>

        {manualStatus === 'loading' && <p className="p-5 text-sm text-slate-500">查詢中...</p>}
        {manualError && <p className="m-5 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{manualError}</p>}
        {manualStatus === 'idle' && manualSearchSummary && manualResults.length === 0 && (
          <div className="m-5 rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            查無符合「{manualSearchSummary.query}」的開課資料，請改用課碼或切換查詢學期。
          </div>
        )}
        {manualStatus === 'idle' && manualResults.length > 0 && filteredManualResults.length === 0 && (
          <div className="m-5 rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            目前篩選條件沒有符合結果，請放寬教師、節次或名額條件。
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="min-w-[1080px] w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-xs font-semibold text-slate-500">
                <th className="border-b border-slate-200 px-3 py-3">課碼</th>
                <th className="border-b border-slate-200 px-3 py-3">課名</th>
                <th className="border-b border-slate-200 px-3 py-3">教師</th>
                <th className="border-b border-slate-200 px-3 py-3">學分</th>
                <th className="border-b border-slate-200 px-3 py-3">節次</th>
                <th className="border-b border-slate-200 px-3 py-3">教室</th>
                <th className="border-b border-slate-200 px-3 py-3">名額</th>
                <th className="border-b border-slate-200 px-3 py-3">備註</th>
                <th className="sticky right-0 border-b border-slate-200 bg-slate-50 px-3 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredManualResults.length === 0 && !manualSearchSummary && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-sm text-slate-500">
                    先在上方輸入課名或課碼搜尋官方開課資料。
                  </td>
                </tr>
              )}
              {filteredManualResults.map((offering) => (
                <CourseResultRow
                  key={`${offering.course_no}-${offering.node}-${offering.teacher}`}
                  offering={offering}
                  conflicts={findConflicts(offering, data, activeSemesterId)}
                  alreadyVirtual={Boolean(findScheduledCourseByOffering(offering, data, activeSemesterId))}
                  officialActionCourseNo={officialActionCourseNo}
                  onAddSelectionCourse={() => onAddSelectionCourse(offering)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <details className="virtual-tray rounded-lg border border-slate-200 bg-white">
        <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-slate-700">虛擬加入 {virtualCourses.length} 門 · {formatCredits(virtualCourseCredits)} 學分 <span className="ml-2 font-normal text-slate-500">查看追蹤清單</span></summary>
        <div className="flex items-start justify-between border-b border-slate-100 p-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">虛擬加入 ({virtualCourses.length})</h2>
            <p className="mt-1 text-xs text-slate-500">未被官方正式接受的課程。</p>
          </div>
          <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
            明確標注
          </span>
        </div>
        <div className="max-h-[640px] overflow-y-auto p-4">
          {virtualCourses.length === 0 ? (
            <div className="rounded-md border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">
              官方拒絕或需要加簽追蹤的課程會出現在這裡。
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {virtualCourses.map((course, index) => (
                <VirtualCourseCard
                  key={course.id}
                  course={course}
                  rank={index + 1}
                  onDelete={() => onDeleteVirtualCourse(course.id)}
                />
              ))}
            </div>
          )}
        </div>
        <div className="space-y-2 border-t border-slate-100 p-4">
          <p className="text-xs text-slate-500">虛擬課程學分：{formatCredits(virtualCourseCredits)} 學分</p>
          <button
            onClick={onOpenPlanning}
            className="w-full rounded-md bg-blue-600 px-3 py-2 text-center text-sm font-semibold text-white hover:bg-blue-700"
          >
            前往選課工作台
          </button>
          <button
            disabled
            className="w-full cursor-not-allowed rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-400"
          >
            虛擬清單已自動儲存
          </button>
        </div>
      </details>
    </div>
  );
}

const INPUT_CLASS = 'w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100';
const SELECT_CLASS = 'w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm text-slate-800 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100';

function FilterField({ label, className = '', children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function CourseResultRow({
  offering,
  conflicts,
  alreadyVirtual,
  officialActionCourseNo,
  onAddSelectionCourse,
}: {
  offering: CourseSearchResult;
  conflicts: Course[];
  alreadyVirtual: boolean;
  officialActionCourseNo: string | null;
  onAddSelectionCourse: () => void;
}) {
  const slots = parseNodeSlots(offering.node);
  const status = capacityStatus(offering);
  const isOfficialActionLoading = officialActionCourseNo === offering.course_no.trim().toUpperCase();
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="border-b border-slate-100 px-3 py-3 font-medium text-blue-600">{offering.course_no || '未列'}</td>
      <td className="border-b border-slate-100 px-3 py-3">
        <div className="font-semibold text-slate-900">{offering.course_name}</div>
          <div className="mt-1 flex flex-wrap gap-1">
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">{requirementLabel(offering.require_option)}</span>
          {alreadyVirtual && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-700">已虛擬加入</span>}
          {conflicts.length > 0 && <span className="rounded bg-red-50 px-1.5 py-0.5 text-[11px] text-red-700">衝堂</span>}
        </div>
      </td>
      <td className="border-b border-slate-100 px-3 py-3 text-slate-700">{offering.teacher || '未列教師'}</td>
      <td className="border-b border-slate-100 px-3 py-3 text-slate-700">{formatCredits(offering.credits)}</td>
      <td className="whitespace-nowrap border-b border-slate-100 px-3 py-3 text-slate-700">{displaySlots(slots)}</td>
      <td className="whitespace-nowrap border-b border-slate-100 px-3 py-3 text-slate-700">{displayClassroom(offering.classroom)}</td>
      <td className="border-b border-slate-100 px-3 py-3">
        <span className={`whitespace-nowrap rounded-full px-2 py-1 text-xs font-medium ${
          status === 'available' ? 'bg-emerald-50 text-emerald-700' : status === 'full' ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-600'
        }`}>
          {capacityLabel(offering)}
        </span>
      </td>
      <td className="min-w-[260px] max-w-xl whitespace-normal border-b border-slate-100 px-3 py-3 text-xs leading-relaxed text-slate-600">
        {offering.contents || (conflicts.length > 0 ? `與 ${conflicts.map((course) => course.name).join('、')} 衝堂` : '無備註')}
      </td>
      <td className="sticky right-0 border-b border-slate-100 bg-white px-3 py-3">
        <div className="flex justify-end gap-2">
          <button
            onClick={onAddSelectionCourse}
            disabled={!offering.course_no || isOfficialActionLoading || alreadyVirtual}
            className="inline-flex items-center gap-1 rounded-md border border-blue-300 px-2.5 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
          >
            {isOfficialActionLoading && <Loader2 className="h-3 w-3 animate-spin" />}
            {isOfficialActionLoading ? '處理中' : alreadyVirtual ? '已虛擬加入' : '加入選課清單'}
          </button>
        </div>
      </td>
    </tr>
  );
}

function VirtualCourseCard({
  course,
  rank,
  onDelete,
}: {
  course: Course;
  rank: number;
  onDelete: () => void;
}) {
  const slots = course.scheduledOffering?.slots || [];
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-bold text-amber-700">
          {rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-slate-900">{course.name}</p>
            <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-amber-700">
              虛擬
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-600">
            {formatCredits(course.credits)} 學分
            {course.scheduledOffering?.teacher ? `・${course.scheduledOffering.teacher}` : ''}
          </p>
          <p className="mt-1 truncate text-xs text-slate-600">
            {slots.length > 0 ? `${displaySlots(slots)}・${displayClassroom(course.scheduledOffering?.classroom)}` : '未提供節次'}
          </p>
          <p className="mt-2 line-clamp-2 text-xs text-amber-800">
            {course.virtualSelection?.reason || '尚未被官方正式接受。'}
          </p>
        </div>
        <button
          type="button"
          onClick={onDelete}
          className="rounded-md border border-amber-200 bg-white px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100"
        >
          移除
        </button>
      </div>
    </div>
  );
}
