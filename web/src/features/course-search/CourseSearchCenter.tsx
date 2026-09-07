import { ListChecks, Loader2, Plus, Search, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type { AppData, Course, CourseSearchResult, CourseSemesterInfo, PendingRequirement } from '../../shared/types';
import { listCourseDepartments, parseCourseDepartment } from '../../shared/domain/courseDepartments';
import {
  type CapacityFilter,
  type ManualSearchSummary,
  type SearchMode,
  DOUBLE_MAJOR_RECOGNITION_SET_ID,
  MINOR_RECOGNITION_SET_ID,
  capacityLabel,
  capacityStatus,
  displayClassroom,
  displaySlots,
  findConflicts,
  findScheduledCourseByOffering,
  formatCredits,
  parseNodeSlots,
  requirementLabel,
} from '../../shared/domain/planner';

type CourseSearchCenterProps = {
  data: AppData;
  courseSemesters: CourseSemesterInfo[];
  querySemester: string;
  currentCourseSemesterLabel: string;
  manualMode: SearchMode;
  manualQuery: string;
  exactCourseNameSearch: boolean;
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
  canRunManualSearch: boolean;
  virtualCourseCredits: number;
  activeSemesterId: string;
  onQuerySemesterChange: (semester: string) => void;
  onManualModeChange: (mode: SearchMode) => void;
  onManualQueryChange: (query: string) => void;
  onExactCourseNameSearchChange: (enabled: boolean) => void;
  onTeacherFilterChange: (teacher: string) => void;
  onCreditFilterChange: (credits: string) => void;
  onRequireOptionFilterChange: (option: string) => void;
  onTimeFilterChange: (time: string) => void;
  onCapacityFilterChange: (capacity: CapacityFilter) => void;
  onRunManualSearch: () => void | Promise<void>;
  onResetFilters: () => void;
  onExportResults: () => void;
  onAddPendingCourse: (group: PendingCourseGroup, courseName: string) => void;
  onDeletePendingCourse: (requirementId: string) => void;
  onSearchPendingCourse: (courseName: string) => void;
  officialActionCourseNo: string | null;
  onAddSelectionCourse: (offering: CourseSearchResult) => void;
  onAddPlannedCourse: (offering: CourseSearchResult, requirementId?: string) => void;
  onDeleteVirtualCourse: (courseId: string) => void;
  onOpenPlanning: () => void;
};

type PendingCourseGroup = 'double_major' | 'minor';

const PENDING_COURSE_GROUPS: Array<{ value: PendingCourseGroup; label: string; setId: string }> = [
  { value: 'double_major', label: '雙主修', setId: 'manual-double-major-todo' },
  { value: 'minor', label: '輔系', setId: 'manual-minor-todo' },
];

const COURSE_DEPARTMENT_LIST = listCourseDepartments();

export function CourseSearchCenter({
  data,
  courseSemesters,
  querySemester,
  currentCourseSemesterLabel,
  manualMode,
  manualQuery,
  exactCourseNameSearch,
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
  canRunManualSearch,
  virtualCourseCredits,
  activeSemesterId,
  onQuerySemesterChange,
  onManualModeChange,
  onManualQueryChange,
  onExactCourseNameSearchChange,
  onTeacherFilterChange,
  onCreditFilterChange,
  onRequireOptionFilterChange,
  onTimeFilterChange,
  onCapacityFilterChange,
  onRunManualSearch,
  onResetFilters,
  onExportResults,
  onAddPendingCourse,
  onDeletePendingCourse,
  onSearchPendingCourse,
  officialActionCourseNo,
  onAddSelectionCourse,
  onAddPlannedCourse,
  onDeleteVirtualCourse,
  onOpenPlanning,
}: CourseSearchCenterProps) {
  const virtualCourses = data.selectionPlan?.courses || [];
  const recognitionRequirements = data.pendingRequirements.filter((requirement) => (
    requirement.setId === DOUBLE_MAJOR_RECOGNITION_SET_ID || requirement.setId === MINOR_RECOGNITION_SET_ID
  ));
  const [activePendingGroup, setActivePendingGroup] = useState<PendingCourseGroup>('double_major');
  const [pendingCourseName, setPendingCourseName] = useState('');
  const activePendingSetId = PENDING_COURSE_GROUPS.find((group) => group.value === activePendingGroup)?.setId || '';
  const pendingCourses = data.pendingRequirements.filter((requirement) => requirement.setId === activePendingSetId);
  const addPendingCourse = () => {
    const courseName = pendingCourseName.trim();
    if (!courseName) return;
    onAddPendingCourse(activePendingGroup, courseName);
    setPendingCourseName('');
  };
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
      <section className="min-w-0 rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">課程查詢中心</h2>
            <p className="mt-1 text-sm text-slate-500">查詢官方開課資料，加入官方選課清單；若官方拒絕，會以待加簽標示在課表上。</p>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span>
              {manualSearchSummary
                ? `共找到 ${manualSearchSummary.resultCount} 筆，顯示 ${filteredManualResults.length} 筆`
                : '輸入條件後開始查詢'}
            </span>
            <button
              onClick={onExportResults}
              disabled={filteredManualResults.length === 0}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            >
              匯出結果
            </button>
          </div>
        </div>

        <div className="border-b border-slate-100 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-slate-900">篩選條件</h3>
            <button onClick={onResetFilters} className="shrink-0 text-sm font-medium text-blue-600 hover:text-blue-700">
              清除全部
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6">
            <div>
              <label className="block text-xs font-medium text-slate-500">學期</label>
              <select
                value={querySemester}
                onChange={(event) => onQuerySemesterChange(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              >
                {courseSemesters.length === 0 && <option value={querySemester}>{querySemester}</option>}
                {courseSemesters.map((semester) => (
                  <option key={semester.semester} value={semester.semester}>
                    {semester.semester}{semester.english_label ? `・${semester.english_label}` : ''}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500">目前查詢：{currentCourseSemesterLabel}</p>
            </div>

            <div className="md:col-span-2 xl:col-span-2">
              <div className="flex items-center justify-between gap-3">
                <label className="block text-xs font-medium text-slate-500">課名 / 課碼</label>
                <label className={`flex items-center gap-1.5 text-xs font-medium ${
                  manualMode === 'name' ? 'text-slate-600' : 'text-slate-400'
                }`}>
                  <input
                    type="checkbox"
                    checked={exactCourseNameSearch}
                    disabled={manualMode !== 'name'}
                    onChange={(event) => onExactCourseNameSearchChange(event.target.checked)}
                    className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed"
                  />
                  精確課名
                </label>
              </div>
              <div className="mt-1 grid grid-cols-[112px_minmax(0,1fr)] gap-2">
                <div className="inline-flex rounded-md border border-slate-300 bg-slate-50 p-0.5">
                  {(['name', 'code'] as SearchMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => onManualModeChange(mode)}
                      className={`flex-1 rounded px-2 py-1.5 text-sm font-medium ${
                        manualMode === mode ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      {mode === 'name' ? '課名' : '課碼'}
                    </button>
                  ))}
                </div>
                <input
                  value={manualQuery}
                  onChange={(event) => onManualQueryChange(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && canRunManualSearch) void onRunManualSearch();
                  }}
                  placeholder="資料結構"
                  className="min-w-0 rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500">教師</label>
              <input
                value={teacherFilter}
                onChange={(event) => onTeacherFilterChange(event.target.value)}
                placeholder="輸入教師姓名"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500">必選修</label>
              <select
                value={requireOptionFilter}
                onChange={(event) => onRequireOptionFilterChange(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="all">全部</option>
                <option value="R">必修</option>
                <option value="E">選修</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500">學分</label>
              <select
                value={creditFilter}
                onChange={(event) => onCreditFilterChange(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="all">不限</option>
                <option value="0">0 學分</option>
                <option value="1">1 學分</option>
                <option value="2">2 學分</option>
                <option value="3">3 學分</option>
                <option value="4">4 學分</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500">節次</label>
              <input
                value={timeFilter}
                onChange={(event) => onTimeFilterChange(event.target.value)}
                placeholder="例如 M3 或 W4"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500">名額狀態</label>
              <select
                value={capacityFilter}
                onChange={(event) => onCapacityFilterChange(event.target.value as CapacityFilter)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="all">全部</option>
                <option value="available">尚有名額</option>
                <option value="full">額滿</option>
                <option value="unknown">未公告</option>
              </select>
            </div>

            <div className="flex items-end gap-2">
              <button
                onClick={() => void onRunManualSearch()}
                disabled={!canRunManualSearch}
                className="min-h-10 flex-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                搜尋課程
              </button>
              <button
                onClick={onResetFilters}
                className="min-h-10 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                重設
              </button>
            </div>

            <PendingCoursePanel
              activeGroup={activePendingGroup}
              courseName={pendingCourseName}
              courses={pendingCourses}
              onAdd={addPendingCourse}
              onCourseNameChange={setPendingCourseName}
              onDelete={onDeletePendingCourse}
              onGroupChange={setActivePendingGroup}
              onSearch={onSearchPendingCourse}
            />

            <CourseDepartmentReference />
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
          <table className="min-w-[1160px] w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-xs font-semibold text-slate-500">
                <th className="border-b border-slate-200 px-3 py-3">課碼</th>
                <th className="border-b border-slate-200 px-3 py-3">開課系所</th>
                <th className="border-b border-slate-200 px-3 py-3">課名</th>
                <th className="border-b border-slate-200 px-3 py-3">教師</th>
                <th className="border-b border-slate-200 px-3 py-3">學分</th>
                <th className="border-b border-slate-200 px-3 py-3">GPA</th>
                <th className="border-b border-slate-200 px-3 py-3">節次</th>
                <th className="border-b border-slate-200 px-3 py-3">教室</th>
                <th className="border-b border-slate-200 px-3 py-3">名額</th>
                <th className="border-b border-slate-200 px-3 py-3">備註</th>
                <th className="border-b border-slate-200 px-3 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredManualResults.length === 0 && !manualSearchSummary && (
                <tr>
                  <td colSpan={11} className="px-4 py-12 text-center text-sm text-slate-500">
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
                  recognitionRequirements={recognitionRequirements}
                  officialActionCourseNo={officialActionCourseNo}
                  onAddSelectionCourse={() => onAddSelectionCourse(offering)}
                  onAddPlannedCourse={(requirementId) => onAddPlannedCourse(offering, requirementId)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-start justify-between border-b border-slate-100 p-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">未來規劃 ({virtualCourses.length})</h2>
            <p className="mt-1 text-xs text-slate-500">本地規劃與待加簽追蹤課程。</p>
          </div>
          <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
            明確標注
          </span>
        </div>
        <div className="max-h-[640px] overflow-y-auto p-4">
          {virtualCourses.length === 0 ? (
            <div className="rounded-md border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">
              從課程查詢加入的本地規劃或待加簽課程會出現在這裡。
            </div>
          ) : (
            <div className="space-y-3">
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
          <p className="text-xs text-slate-500">未來規劃學分：{formatCredits(virtualCourseCredits)} 學分</p>
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
            未來規劃已自動儲存
          </button>
        </div>
      </aside>
    </div>
  );
}

function CourseDepartmentReference() {
  return (
    <details className="md:col-span-2 xl:col-span-4 2xl:col-span-6 rounded-md border border-slate-200 bg-white px-3 py-2">
      <summary className="cursor-pointer text-sm font-semibold text-slate-800">
        開課系所代碼對照表
      </summary>
      <div className="mt-3 grid max-h-72 grid-cols-1 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3">
        {COURSE_DEPARTMENT_LIST.map((department) => (
          <div key={department.code} className="grid grid-cols-[42px_minmax(0,1fr)] gap-2 rounded-md border border-slate-100 bg-slate-50 px-2 py-1.5">
            <span className="font-mono text-xs font-semibold text-blue-700">{department.code}</span>
            <span className="text-xs text-slate-700">{department.name}</span>
          </div>
        ))}
      </div>
    </details>
  );
}

function PendingCoursePanel({
  activeGroup,
  courseName,
  courses,
  onAdd,
  onCourseNameChange,
  onDelete,
  onGroupChange,
  onSearch,
}: {
  activeGroup: PendingCourseGroup;
  courseName: string;
  courses: PendingRequirement[];
  onAdd: () => void;
  onCourseNameChange: (courseName: string) => void;
  onDelete: (requirementId: string) => void;
  onGroupChange: (group: PendingCourseGroup) => void;
  onSearch: (courseName: string) => void;
}) {
  const activeGroupLabel = PENDING_COURSE_GROUPS.find((group) => group.value === activeGroup)?.label || '待修';
  return (
    <div className="md:col-span-2 xl:col-span-4 2xl:col-span-6">
      <details className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
        <summary className="cursor-pointer list-none">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <ListChecks className="h-4 w-4 text-blue-600" />
                待修課程清單
                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                  {activeGroupLabel} {courses.length} 筆
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">展開後可新增待修課名或直接查課。</p>
            </div>
            <div className="text-xs font-medium text-blue-600">展開</div>
          </div>
        </summary>

        <div className="mt-3 border-t border-slate-200 pt-3">
          <div className="inline-flex w-fit rounded-md border border-slate-200 bg-white p-1">
            {PENDING_COURSE_GROUPS.map((group) => (
              <button
                key={group.value}
                type="button"
                onClick={() => onGroupChange(group.value)}
                className={`rounded px-3 py-1.5 text-xs font-medium ${
                  activeGroup === group.value ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                {group.label}
              </button>
            ))}
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
            <input
              value={courseName}
              onChange={(event) => onCourseNameChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') onAdd();
              }}
              placeholder="輸入待修課名，例如 資料結構"
              className="min-h-10 rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
            <button
              type="button"
              onClick={onAdd}
              disabled={!courseName.trim()}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <Plus className="h-4 w-4" />
              新增
            </button>
          </div>

          {courses.length === 0 ? (
            <div className="mt-3 rounded-md border border-dashed border-slate-300 bg-white px-3 py-4 text-center text-sm text-slate-500">
              目前沒有待修課程。
            </div>
          ) : (
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
              {courses.map((course) => (
                <div key={course.id} className="flex min-w-0 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2">
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">{course.title}</span>
                  <button
                    type="button"
                    onClick={() => onSearch(course.title)}
                    className="inline-flex shrink-0 items-center gap-1 rounded-md border border-blue-200 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50"
                  >
                    <Search className="h-3.5 w-3.5" />
                    查課
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(course.id)}
                    className="inline-flex shrink-0 items-center rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-500 hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                    title="刪除待修課程"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </details>
    </div>
  );
}

function CourseResultRow({
  offering,
  conflicts,
  alreadyVirtual,
  recognitionRequirements,
  officialActionCourseNo,
  onAddSelectionCourse,
  onAddPlannedCourse,
}: {
  offering: CourseSearchResult;
  conflicts: Course[];
  alreadyVirtual: boolean;
  recognitionRequirements: PendingRequirement[];
  officialActionCourseNo: string | null;
  onAddSelectionCourse: () => void;
  onAddPlannedCourse: (requirementId?: string) => void;
}) {
  const [selectedRequirementId, setSelectedRequirementId] = useState('');
  const slots = parseNodeSlots(offering.node);
  const status = capacityStatus(offering);
  const isOfficialActionLoading = officialActionCourseNo === offering.course_no.trim().toUpperCase();
  const department = parseCourseDepartment(offering.course_no);
  const gpaLabel = typeof offering.gpa === 'number' && Number.isFinite(offering.gpa)
    ? offering.gpa.toFixed(2)
    : offering.gpa_status === 'no_data'
      ? '查無資料'
      : offering.gpa_status === 'error'
        ? '錯誤'
        : '未啟用';
  const gpaTone = typeof offering.gpa === 'number' && Number.isFinite(offering.gpa)
    ? 'bg-indigo-50 text-indigo-700'
    : offering.gpa_status === 'error'
      ? 'bg-red-50 text-red-700'
      : offering.gpa_status === 'no_data'
        ? 'bg-amber-50 text-amber-700'
        : 'bg-slate-100 text-slate-500';
  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="border-b border-slate-100 px-3 py-3 font-medium text-blue-600">{offering.course_no || '未列'}</td>
      <td className="border-b border-slate-100 px-3 py-3">
        {department ? (
          <div className="max-w-[130px] truncate text-xs text-slate-700" title={department.name}>{department.name}</div>
        ) : (
          <span className="text-xs text-slate-400">未列</span>
        )}
      </td>
      <td className="border-b border-slate-100 px-3 py-3">
        <div className="font-semibold text-slate-900">{offering.course_name}</div>
          <div className="mt-1 flex flex-wrap gap-1">
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">{requirementLabel(offering.require_option)}</span>
          {alreadyVirtual && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-700">已列入規劃</span>}
          {conflicts.length > 0 && <span className="rounded bg-red-50 px-1.5 py-0.5 text-[11px] text-red-700">衝堂</span>}
        </div>
      </td>
      <td className="border-b border-slate-100 px-3 py-3 text-slate-700">{offering.teacher || '未列教師'}</td>
      <td className="border-b border-slate-100 px-3 py-3 text-slate-700">{formatCredits(offering.credits)}</td>
      <td className="border-b border-slate-100 px-3 py-3">
        <span className={`rounded-full px-2 py-1 text-xs font-medium ${gpaTone}`}>
          {gpaLabel}
        </span>
      </td>
      <td className="border-b border-slate-100 px-3 py-3 text-slate-700">{displaySlots(slots)}</td>
      <td className="border-b border-slate-100 px-3 py-3 text-slate-700">{displayClassroom(offering.classroom)}</td>
      <td className="border-b border-slate-100 px-3 py-3">
        <span className={`rounded-full px-2 py-1 text-xs font-medium ${
          status === 'available' ? 'bg-emerald-50 text-emerald-700' : status === 'full' ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-600'
        }`}>
          {capacityLabel(offering)}
        </span>
      </td>
      <td className="max-w-[240px] whitespace-normal break-words border-b border-slate-100 px-3 py-3 text-slate-500" title={offering.contents || undefined}>
        {offering.contents || (conflicts.length > 0 ? `與 ${conflicts.map((course) => course.name).join('、')} 衝堂` : '無備註')}
      </td>
      <td className="border-b border-slate-100 px-3 py-3">
        <div className="flex flex-col items-end gap-2">
          <div className="flex max-w-[260px] flex-wrap justify-end gap-2">
            <select
              value={selectedRequirementId}
              onChange={(event) => setSelectedRequirementId(event.target.value)}
              className="min-h-8 max-w-[160px] rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
              title="指定認列規則"
            >
              <option value="">不指定認列</option>
              {recognitionRequirements.map((requirement) => (
                <option key={requirement.id} value={requirement.id}>
                  {requirement.setId === DOUBLE_MAJOR_RECOGNITION_SET_ID ? '雙主修' : '輔系'}・{requirement.title}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => onAddPlannedCourse(selectedRequirementId || undefined)}
              disabled={!offering.course_no}
              className="inline-flex items-center gap-1 rounded-md border border-emerald-300 px-2.5 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            >
              {alreadyVirtual ? '更新規劃' : '加入未來規劃'}
            </button>
          </div>
          <button
            onClick={onAddSelectionCourse}
            disabled={!offering.course_no || isOfficialActionLoading}
            className="inline-flex items-center gap-1 rounded-md border border-blue-300 px-2.5 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
          >
            {isOfficialActionLoading && <Loader2 className="h-3 w-3 animate-spin" />}
            {isOfficialActionLoading ? '處理中' : alreadyVirtual ? '重新送出' : '加入選課清單'}
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
  const isRejected = course.virtualSelection?.status === 'rejected';
  return (
    <div className={`rounded-md border p-3 ${isRejected ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50'}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-bold text-amber-700">
          {rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-slate-900">{course.name}</p>
            <span className={`shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium ${isRejected ? 'text-amber-700' : 'text-emerald-700'}`}>
              {isRejected ? '待加簽' : '未來規劃'}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-600">
            {formatCredits(course.credits)} 學分
            {course.scheduledOffering?.teacher ? `・${course.scheduledOffering.teacher}` : ''}
          </p>
          <p className="mt-1 truncate text-xs text-slate-600">
            {slots.length > 0 ? `${displaySlots(slots)}・${displayClassroom(course.scheduledOffering?.classroom)}` : '未提供節次'}
          </p>
          <p className={`mt-2 line-clamp-2 text-xs ${isRejected ? 'text-amber-800' : 'text-emerald-800'}`}>
            {course.virtualSelection?.reason || '本地未來規劃。'}
          </p>
        </div>
        <button
          type="button"
          onClick={onDelete}
          className={`rounded-md border bg-white px-2 py-1 text-xs font-medium ${isRejected ? 'border-amber-200 text-amber-700 hover:bg-amber-100' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-100'}`}
        >
          移除
        </button>
      </div>
    </div>
  );
}
