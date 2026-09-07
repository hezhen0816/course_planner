import { Info, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type { AppData, Course, CourseProgram, PendingRequirement, PlannerStats, RequirementKind } from '../../shared/types';
import { CATEGORY_LABELS, PROGRAM_LABELS } from '../../shared/constants';
import {
  DOUBLE_MAJOR_RECOGNITION_SET_ID,
  MINOR_RECOGNITION_SET_ID,
  displayClassroom,
  displaySlots,
  formatCredits,
  getRequirementStatus,
  isFailedImportedHistoryCourse,
  isHistoryImportedCourse,
  normalizeName,
} from '../../shared/domain/planner';

type RecognitionRequirementDraft = {
  program: Extract<CourseProgram, 'double_major' | 'minor'>;
  kind: RequirementKind;
  title: string;
  requiredCredits?: number | null;
  courseNames: string[];
  courseCodePrefix?: string | null;
  note?: string;
};

type CourseTimelinePageProps = {
  data: AppData;
  stats: PlannerStats;
  onAddRecognitionRequirement: (draft: RecognitionRequirementDraft) => void;
  onDeleteRecognitionRequirement: (requirementId: string) => void;
  onOpenCourseDetail: (semesterId: string, semesterName: string, course: Course) => void;
};

export function CourseTimelinePage({
  data,
  stats,
  onAddRecognitionRequirement,
  onDeleteRecognitionRequirement,
  onOpenCourseDetail,
}: CourseTimelinePageProps) {
  const timelineSemesters = data.semesters.map((semester) => ({
    ...semester,
    courses: semester.courses.filter(isHistoryImportedCourse),
    plannedSourceLabel: '',
  }));
  const plannedCourses = data.selectionPlan?.courses || [];
  const plannedSemesterName = plannedSemesterNameFromLabel(data.selectionPlan?.targetLabel);
  const plannedTargetIndex = plannedCourses.length > 0 && plannedSemesterName
    ? timelineSemesters.findIndex((semester) => semester.name === plannedSemesterName)
    : -1;
  const displaySemesters = plannedCourses.length === 0
    ? timelineSemesters
    : plannedTargetIndex >= 0
      ? timelineSemesters.map((semester, index) => (
          index === plannedTargetIndex
            ? {
                ...semester,
                courses: [...semester.courses, ...plannedCourses],
                plannedSourceLabel: data.selectionPlan?.targetLabel || '未來規劃',
              }
            : semester
        ))
      : [
          ...timelineSemesters,
          {
            id: '__selection_plan__',
            name: data.selectionPlan?.targetLabel || '未來規劃',
            courses: plannedCourses,
            plannedSourceLabel: data.selectionPlan?.targetLabel || '未來規劃',
          },
        ];
  const historyCount = timelineSemesters.reduce((sum, semester) => sum + semester.courses.length, 0);
  const plannedCount = plannedCourses.length;
  const totalCourses = historyCount + plannedCount;
  const requirementById = new Map(data.pendingRequirements.map((requirement) => [requirement.id, requirement]));
  const failedCount = timelineSemesters.reduce((sum, semester) => (
    sum + semester.courses.filter(isFailedImportedHistoryCourse).length
  ), 0);

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">修課軌跡</p>
        <h1 className="mt-1 text-2xl font-semibold text-slate-950">歷史修課與未來規劃</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          這裡集中查看已修、未通過與從課程查詢加入的未來規劃；未來規劃只代表草稿或待加簽，不代表已選上。
        </p>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-4">
          <SummaryBox label="總課程" value={`${totalCourses} 門`} tone="slate" />
          <SummaryBox label="歷史匯入" value={`${historyCount} 門`} tone="blue" />
          <SummaryBox label="未來規劃" value={`${plannedCount} 門`} tone="amber" />
          <SummaryBox label="未通過" value={`${failedCount} 門`} tone={failedCount > 0 ? 'red' : 'emerald'} />
        </div>
      </section>

      <GraduationProgressPanel data={data} stats={stats} />

      <RecognitionRequirementsPanel
        data={data}
        onAddRecognitionRequirement={onAddRecognitionRequirement}
        onDeleteRecognitionRequirement={onDeleteRecognitionRequirement}
      />

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {displaySemesters.map((semester) => {
          const semesterCredits = semester.courses.reduce((sum, course) => (
            sum + (course.category === 'pe' ? 0 : course.credits)
          ), 0);
          return (
            <div key={semester.id} className="rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <div>
                  <h2 className="text-base font-semibold text-slate-900">{semester.name}</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    {semester.courses.length} 門課 · {formatCredits(semesterCredits)} 學分
                  </p>
                  {semester.plannedSourceLabel && (
                    <p className="mt-1 text-xs font-medium text-blue-600">
                      含 {semester.plannedSourceLabel} 的未來規劃
                    </p>
                  )}
                </div>
              </div>
              <div className="space-y-2 p-4">
                {semester.courses.length === 0 ? (
                  <div className="rounded-md border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">
                    尚未有修課或未來規劃資料。
                  </div>
                ) : (
                  semester.courses.map((course) => (
                    <TimelineCourseCard
                      key={course.id}
                      course={course}
                      recognitionLabel={course.sourceRequirementId ? requirementById.get(course.sourceRequirementId)?.title : undefined}
                      onOpen={() => onOpenCourseDetail(semester.id, semester.name, course)}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}

function plannedSemesterNameFromLabel(label: string | undefined): string | null {
  const matched = label?.match(/推定([^·\s]+)/);
  return matched?.[1] || null;
}

function GraduationProgressPanel({ data, stats }: { data: AppData; stats: PlannerStats }) {
  const rows = [
    { label: '總學分', value: stats.total, target: data.targets.total },
    { label: '國文', value: stats.chinese, target: data.targets.chinese },
    { label: '英文', value: stats.english, target: data.targets.english },
    { label: '通識', value: stats.gen_ed, target: data.targets.gen_ed },
    { label: '社會實踐', value: stats.social, target: data.targets.social },
    { label: '體育學期', value: stats.pe_semesters, target: data.targets.pe_semesters, unit: '學期' },
    { label: '本系必修', value: stats.homeCompulsory, target: data.targets.home_compulsory },
    { label: '本系選修', value: stats.homeElective, target: data.targets.home_elective },
    { label: '雙主修', value: stats.doubleMajor, target: data.targets.double_major },
    { label: '輔系', value: stats.minor, target: data.targets.minor },
  ].filter((row) => row.target > 0);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">畢業進度</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">門檻完成度</h2>
        </div>
        <p className="text-xs text-slate-500">包含已修課程與未來規劃課程；門檻數字可在設定頁調整。</p>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        {rows.map((row) => (
          <ProgressTile
            key={row.label}
            label={row.label}
            value={row.value}
            target={row.target}
            unit={row.unit || '學分'}
          />
        ))}
      </div>
    </section>
  );
}

function ProgressTile({
  label,
  value,
  target,
  unit,
}: {
  label: string;
  value: number;
  target: number;
  unit: string;
}) {
  const ratio = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
        <span className="font-medium">{label}</span>
        <span>{ratio}%</span>
      </div>
      <p className="mt-1 text-lg font-semibold text-slate-900">
        {formatCredits(value)} / {formatCredits(target)} {unit}
      </p>
      <div className="mt-2 h-2 rounded-full bg-white">
        <div className="h-2 rounded-full bg-blue-600" style={{ width: `${ratio}%` }} />
      </div>
    </div>
  );
}

function RecognitionRequirementsPanel({
  data,
  onAddRecognitionRequirement,
  onDeleteRecognitionRequirement,
}: {
  data: AppData;
  onAddRecognitionRequirement: (draft: RecognitionRequirementDraft) => void;
  onDeleteRecognitionRequirement: (requirementId: string) => void;
}) {
  const [program, setProgram] = useState<RecognitionRequirementDraft['program']>('double_major');
  const [kind, setKind] = useState<RequirementKind>('course');
  const [title, setTitle] = useState('');
  const [courseNamesText, setCourseNamesText] = useState('');
  const [courseCodePrefix, setCourseCodePrefix] = useState('');
  const [requiredCreditsText, setRequiredCreditsText] = useState('');
  const recognitionRequirements = data.pendingRequirements.filter((requirement) => (
    requirement.setId === DOUBLE_MAJOR_RECOGNITION_SET_ID || requirement.setId === MINOR_RECOGNITION_SET_ID
  ));
  const doubleMajorRequirements = recognitionRequirements.filter((requirement) => requirement.setId === DOUBLE_MAJOR_RECOGNITION_SET_ID);
  const minorRequirements = recognitionRequirements.filter((requirement) => requirement.setId === MINOR_RECOGNITION_SET_ID);

  const addRequirement = () => {
    const normalizedTitle = title.trim();
    if (!normalizedTitle) return;
    const courseNames = courseNamesText
      .split(/[／/、,，\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
    const requiredCredits = Number(requiredCreditsText);
    onAddRecognitionRequirement({
      program,
      kind,
      title: normalizedTitle,
      requiredCredits: Number.isFinite(requiredCredits) && requiredCredits > 0 ? requiredCredits : null,
      courseNames: courseNames.length > 0 ? courseNames : kind === 'credit_pool' ? [] : [normalizedTitle],
      courseCodePrefix: courseCodePrefix.trim().toUpperCase() || null,
      note: kind === 'credit_pool' ? '自訂學分池認列' : '自訂課程認列',
    });
    setTitle('');
    setCourseNamesText('');
    setCourseCodePrefix('');
    setRequiredCreditsText('');
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">雙主修 / 輔系認列</p>
        <h2 className="mt-1 text-lg font-semibold text-slate-950">自訂必修、選修與學分池</h2>
        <p className="mt-1 text-sm text-slate-500">
          用課名或課碼前綴比對歷史修課與未來規劃；這裡只做認列檢查，不會送出官方選課。
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 p-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
          <h3 className="text-sm font-semibold text-slate-800">新增認列規則</h3>
          <div className="mt-3 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <label>
                <span className="block text-xs font-medium text-slate-500">歸屬</span>
                <select
                  value={program}
                  onChange={(event) => setProgram(event.target.value as RecognitionRequirementDraft['program'])}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="double_major">雙主修</option>
                  <option value="minor">輔系</option>
                </select>
              </label>
              <label>
                <span className="block text-xs font-medium text-slate-500">類型</span>
                <select
                  value={kind}
                  onChange={(event) => setKind(event.target.value as RequirementKind)}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="course">必修課程</option>
                  <option value="choice">多選一</option>
                  <option value="credit_pool">選修學分池</option>
                </select>
              </label>
            </div>
            <label>
              <span className="block text-xs font-medium text-slate-500">規則名稱</span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="例如 資料結構 或 資工系選修"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </label>
            <label>
              <span className="block text-xs font-medium text-slate-500">可認列課名</span>
              <input
                value={courseNamesText}
                onChange={(event) => setCourseNamesText(event.target.value)}
                placeholder="多門可用 、 或換行分隔；空白時用規則名稱"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label>
                <span className="block text-xs font-medium text-slate-500">課碼前綴</span>
                <input
                  value={courseCodePrefix}
                  onChange={(event) => setCourseCodePrefix(event.target.value)}
                  placeholder="例如 CS"
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm uppercase outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
              <label>
                <span className="block text-xs font-medium text-slate-500">需求學分</span>
                <input
                  value={requiredCreditsText}
                  onChange={(event) => setRequiredCreditsText(event.target.value)}
                  inputMode="decimal"
                  placeholder="例如 3 或 20"
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
            </div>
            <button
              type="button"
              onClick={addRequirement}
              disabled={!title.trim()}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <Plus className="h-4 w-4" />
              新增規則
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <RecognitionRequirementList
            title="雙主修"
            requirements={doubleMajorRequirements}
            data={data}
            onDeleteRecognitionRequirement={onDeleteRecognitionRequirement}
          />
          <RecognitionRequirementList
            title="輔系"
            requirements={minorRequirements}
            data={data}
            onDeleteRecognitionRequirement={onDeleteRecognitionRequirement}
          />
        </div>
      </div>
    </section>
  );
}

function RecognitionRequirementList({
  title,
  requirements,
  data,
  onDeleteRecognitionRequirement,
}: {
  title: string;
  requirements: PendingRequirement[];
  data: AppData;
  onDeleteRecognitionRequirement: (requirementId: string) => void;
}) {
  return (
    <div className="rounded-md border border-slate-200">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">{requirements.length} 項</span>
      </div>
      <div className="space-y-2 p-3">
        {requirements.length === 0 ? (
          <div className="rounded-md border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
            尚未設定認列規則。
          </div>
        ) : (
          requirements.map((requirement) => (
            <RecognitionRequirementCard
              key={requirement.id}
              requirement={requirement}
              data={data}
              onDelete={() => onDeleteRecognitionRequirement(requirement.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function RecognitionRequirementCard({
  requirement,
  data,
  onDelete,
}: {
  requirement: PendingRequirement;
  data: AppData;
  onDelete: () => void;
}) {
  const status = getRequirementStatus(requirement, data);
  const matchedCourses = matchedRecognitionCourses(requirement, data);
  const targetCredits = status.targetCredits || requirement.requiredCredits || requirement.credits || 0;
  const ratio = targetCredits > 0 ? Math.min(100, Math.round((status.earnedCredits / targetCredits) * 100)) : status.completed ? 100 : 0;
  const kindLabel = requirement.kind === 'credit_pool' ? '學分池' : requirement.kind === 'choice' ? '多選一' : '課程';
  return (
    <div className={`rounded-md border p-3 ${status.completed ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-white'}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold text-slate-900">{requirement.title}</p>
            <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">{kindLabel}</span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${status.completed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
              {status.completed ? '已滿足或已規劃' : '尚缺'}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {formatCredits(status.earnedCredits)} / {formatCredits(targetCredits)} 學分
            {requirement.courseCodePrefix ? `・課碼 ${requirement.courseCodePrefix}` : ''}
            {requirement.courseNames.length > 0 ? `・${requirement.courseNames.join('、')}` : ''}
          </p>
          <div className="mt-2 h-1.5 rounded-full bg-white">
            <div className="h-1.5 rounded-full bg-emerald-500" style={{ width: `${ratio}%` }} />
          </div>
          {matchedCourses.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {matchedCourses.map((label) => (
                <span key={label} className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">
                  {label}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xs text-slate-400">尚未匹配到歷史修課或未來規劃。</p>
          )}
        </div>
        <button
          type="button"
          onClick={onDelete}
          className="rounded-md border border-slate-200 bg-white p-1.5 text-slate-500 hover:border-red-200 hover:bg-red-50 hover:text-red-700"
          title="刪除認列規則"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function matchedRecognitionCourses(requirement: PendingRequirement, data: AppData): string[] {
  const candidateNames = new Set(requirement.courseNames.map(normalizeName));
  const candidateCodePrefix = requirement.courseCodePrefix?.trim().toUpperCase() || '';
  const labels = new Set<string>();
  const plannedCourses = [
    ...data.semesters.flatMap((semester) => semester.courses),
    ...(data.selectionPlan?.courses || []),
  ];

  plannedCourses.forEach((course) => {
    const code = course.scheduledOffering?.courseNo?.trim().toUpperCase() || '';
    const matchedBySource = course.sourceRequirementId === requirement.id;
    const matchedByName = candidateNames.has(normalizeName(course.name));
    const matchedByPrefix = Boolean(candidateCodePrefix && code.startsWith(candidateCodePrefix));
    if (matchedBySource || matchedByName || matchedByPrefix) {
      labels.add(`規劃：${course.name}`);
    }
  });

  (data.historyRecords || []).forEach((record) => {
    if (record.status === 'failed') return;
    const matchedByName = candidateNames.has(normalizeName(record.courseName));
    const matchedByPrefix = Boolean(candidateCodePrefix && record.courseCode.toUpperCase().startsWith(candidateCodePrefix));
    if (matchedByName || matchedByPrefix) {
      labels.add(`歷史：${record.courseName}`);
    }
  });

  return Array.from(labels);
}

function SummaryBox({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'slate' | 'blue' | 'emerald' | 'red' | 'amber';
}) {
  const toneClass = {
    slate: 'border-slate-200 bg-slate-50 text-slate-700',
    blue: 'border-blue-200 bg-blue-50 text-blue-700',
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    red: 'border-red-200 bg-red-50 text-red-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
  }[tone];

  return (
    <div className={`rounded-lg border px-4 py-3 ${toneClass}`}>
      <p className="text-xs font-medium opacity-80">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function TimelineCourseCard({
  course,
  recognitionLabel,
  onOpen,
}: {
  course: Course;
  recognitionLabel?: string;
  onOpen: () => void;
}) {
  const isHistory = isHistoryImportedCourse(course);
  const isFailed = isFailedImportedHistoryCourse(course);
  const isRejected = course.virtualSelection?.status === 'rejected';
  const slots = course.scheduledOffering?.slots || [];
  const teacher = course.scheduledOffering?.teacher || course.details?.professor || '未列教師';
  const location = displayClassroom(course.scheduledOffering?.classroom || course.details?.location);
  const toneClass = isFailed
    ? 'border-red-200 bg-red-50 hover:bg-red-100'
    : isHistory
      ? 'border-emerald-200 bg-emerald-50 hover:bg-emerald-100'
      : isRejected
        ? 'border-amber-200 bg-amber-50 hover:bg-amber-100'
        : 'border-blue-200 bg-blue-50 hover:bg-blue-100';

  return (
    <button
      type="button"
      onClick={onOpen}
      className={`w-full rounded-md border p-3 text-left transition-colors ${toneClass}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-slate-900">{course.name}</h3>
            <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-medium text-slate-600">
              {CATEGORY_LABELS[course.category]}
            </span>
            {course.program && course.program !== 'home' && !recognitionLabel && (
              <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {PROGRAM_LABELS[course.program]}
              </span>
            )}
            {isHistory && (
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${isFailed ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
                {isFailed ? '未通過' : '歷史修課'}
              </span>
            )}
            {recognitionLabel && course.program && course.program !== 'home' && (
              <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {PROGRAM_LABELS[course.program]}・{recognitionLabel}
              </span>
            )}
            {!isHistory && (
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${isRejected ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>
                {isRejected ? '待加簽' : '未來規劃'}
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-slate-600">
            {formatCredits(course.credits)} 學分
            {course.grade ? `・成績 ${course.grade}` : ''}
            {teacher ? `・${teacher}` : ''}
          </p>
          <p className="mt-1 truncate text-xs text-slate-500">
            {slots.length > 0 ? `${displaySlots(slots)}・${location}` : location}
          </p>
        </div>
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
      </div>
    </button>
  );
}
