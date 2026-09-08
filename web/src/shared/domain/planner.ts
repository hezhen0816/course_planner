import type {
  AcademicHistoryRecord,
  AppData,
  AppSettings,
  Course,
  CourseCategory,
  CourseProgram,
  HistoryCourseRecord,
  HistoryImportResponse,
  CourseSearchResult,
  PendingRequirement,
  RequirementOption,
  RequirementSet,
  ScheduleSyncResponse,
  ScheduledOffering,
  SyncedCourseRow,
} from '../types';
import { searchCourses } from '../api';
import { parseCourseDepartment } from './courseDepartments';

export const DAY_COLUMNS = [
  { code: 'M', label: '一' },
  { code: 'T', label: '二' },
  { code: 'W', label: '三' },
  { code: 'R', label: '四' },
  { code: 'F', label: '五' },
  { code: 'S', label: '六' },
  { code: 'U', label: '日' },
];

export const PERIODS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'A', 'B', 'C', 'D'];
export const MANUAL_SET_ID = 'manual-requirements';
export const RETAKE_SET_ID = 'retake-requirements';
export const DOUBLE_MAJOR_RECOGNITION_SET_ID = 'manual-double-major-recognition';
export const MINOR_RECOGNITION_SET_ID = 'manual-minor-recognition';
export const HISTORY_IMPORT_NOTE_MARKER = '已修紀錄匯入';
let generatedIdCounter = 0;

export type SearchMode = 'name' | 'code';
export type ApiImportPreview = {
  requirement_set: Record<string, unknown>;
  pending_requirements: Array<Record<string, unknown>>;
  warnings: string[];
  raw_text_preview: string;
};

export type RequirementStatus = {
  completed: boolean;
  earnedCredits: number;
  targetCredits: number;
  scheduledCount: number;
};

export type ManualSearchSummary = {
  query: string;
  mode: SearchMode;
  semester: string;
  resultCount: number;
};

export type CapacityStatus = 'available' | 'full' | 'unknown';
export type CapacityFilter = 'all' | CapacityStatus;
// 'addCode'（加簽追蹤）於 2026-09-08 移除：它沒有任何模式專屬行為（唯一的判斷是
// `!== 'lottery'`），與 'addDrop' 完全等價；待加簽課程本身不依賴模式，仍照常顯示。
export type PlanningMode = 'lottery' | 'addDrop';

export type HistoricalScheduleLookup = {
  status: 'matched' | 'ambiguous' | 'missing' | 'skipped';
  candidateCount: number;
  offering?: CourseSearchResult;
};

export function parseNodeSlots(node: string): string[] {
  return (node || '')
    .split(/[,、\s]+/)
    .map((slot) => slot.trim().toUpperCase())
    .filter(Boolean);
}

const DAY_LABEL_BY_CODE: Record<string, string> = Object.fromEntries(DAY_COLUMNS.map((day) => [day.code, day.label]));

/**
 * Render slots grouped by weekday with the Chinese day annotated once, e.g.
 * ["M6","M7","M8"] -> "M（一）6, 7, 8" and ["W8","R3","R4"] -> "W（三）8、R（四）3, 4".
 */
export function displaySlots(slots: string[]): string {
  if (slots.length === 0) return '未提供節次';
  const groups: { day: string; periods: string[] }[] = [];
  slots.forEach((slot) => {
    const match = slot.trim().toUpperCase().match(/^([A-Z])(\d{1,2}|[A-D])$/);
    if (!match || !DAY_LABEL_BY_CODE[match[1]]) {
      groups.push({ day: '', periods: [slot] });
      return;
    }
    const [, day, period] = match;
    const last = groups[groups.length - 1];
    if (last && last.day === day) {
      last.periods.push(period);
    } else {
      groups.push({ day, periods: [period] });
    }
  });
  return groups
    .map((group) => (group.day ? `${group.day}（${DAY_LABEL_BY_CODE[group.day]}）${group.periods.join(', ')}` : group.periods.join(', ')))
    .join('、');
}

const OFFICIAL_SCHEDULE_WEEKDAYS = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'];
const OFFICIAL_SCHEDULE_PERIOD_TIMES: Record<string, string> = {
  '1': '08:10～09:00', '2': '9:10～10:00', '3': '10:20～11:10', '4': '11:20～12:10', '5': '12:20～13:10',
  '6': '13:20～14:10', '7': '14:20～15:10', '8': '15:30～16:20', '9': '16:30～17:20', '10': '17:30～18:20',
  A: '18:25～19:15', B: '19:20～20:10', C: '20:15～21:05', D: '21:10～22:00',
};

/**
 * Build the official-timetable grid rows (節次/時間/星期一…星期日) from a schedule
 * sync, mirroring the backend's _schedule_rows_from_slots, so a plain schedule
 * sync refreshes the workbench grid without an official-selection sync.
 */
export function officialScheduleRowsFromSlots(slots: ScheduleSyncResponse['slots']): Record<string, string>[] {
  const rows = PERIODS.map((period) => {
    const row: Record<string, string> = { 節次: period, 時間: OFFICIAL_SCHEDULE_PERIOD_TIMES[period] || '' };
    OFFICIAL_SCHEDULE_WEEKDAYS.forEach((weekday) => {
      row[weekday] = '';
    });
    return row;
  });
  const rowByPeriod = new Map(rows.map((row) => [row.節次, row]));
  slots.forEach((slot) => {
    const period = slot.period.trim().toUpperCase();
    const weekday = slot.weekday_label.trim();
    const courseName = slot.course_name.trim();
    const row = rowByPeriod.get(period);
    if (!row || !OFFICIAL_SCHEDULE_WEEKDAYS.includes(weekday) || !courseName) return;
    row[weekday] = [row[weekday], courseName].filter(Boolean).join('、');
  });
  return rows;
}

export function displayClassroom(classroom: string | null | undefined): string {
  return classroom?.trim() || '教室未公告';
}

export function formatCredits(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0';
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function capacityStatus(offering: CourseSearchResult): CapacityStatus {
  if (offering.capacity === null || offering.capacity === undefined || offering.selected_count === null || offering.selected_count === undefined) {
    return 'unknown';
  }
  return offering.selected_count >= offering.capacity ? 'full' : 'available';
}

export function capacityLabel(offering: CourseSearchResult): string {
  if (offering.capacity === null || offering.capacity === undefined || offering.selected_count === null || offering.selected_count === undefined) {
    return '未公告';
  }
  return `${offering.selected_count} / ${offering.capacity}`;
}

export function requirementLabel(value: string): string {
  if (value === 'R') return '必修';
  if (value === 'E') return '選修';
  return value || '未列';
}

export function requirementCourseCode(requirement: PendingRequirement): string {
  const explicit = requirement.courseCodePrefix?.trim();
  if (explicit) return explicit.toUpperCase();
  const noteMatch = requirement.note?.match(/[A-Z]{2,}\d+[A-Z0-9]*/i);
  return noteMatch?.[0]?.toUpperCase() || '';
}

export function nextPlannerId(): string {
  generatedIdCounter += 1;
  return `${generatedIdCounter}`;
}

export function inferCourseCategory(offering: CourseSearchResult): CourseCategory {
  const name = offering.course_name.toLowerCase();
  const code = offering.course_no.toUpperCase();
  if (code.startsWith('PE') || name.includes('體育')) return 'pe';
  if (name.includes('國文') || name.includes('中文')) return 'chinese';
  if (name.includes('英文') || name.includes('english') || name.includes('英語')) return 'english';
  if (name.includes('社會實踐')) return 'social';
  if (code.startsWith('GE') || offering.dimension) return 'gen_ed';
  if (offering.require_option === 'R') return 'compulsory';
  if (offering.require_option === 'E') return 'elective';
  return 'unclassified';
}

export function programFromOfferingSettings(
  offering: Pick<CourseSearchResult, 'course_no'>,
  settings?: AppSettings,
): CourseProgram {
  const departmentCode = parseCourseDepartment(offering.course_no)?.code;
  const programDepartments = settings?.programDepartments;
  if (departmentCode && departmentCode === programDepartments?.doubleMajorDepartmentCode) return 'double_major';
  if (departmentCode && departmentCode === programDepartments?.minorDepartmentCode) return 'minor';
  if (departmentCode && departmentCode === programDepartments?.homeDepartmentCode) return 'home';
  return 'other';
}

export function categoryFromOfferingForProgram(
  offering: CourseSearchResult,
  program: CourseProgram,
): CourseCategory {
  const inferred = inferCourseCategory(offering);
  if (program === 'double_major' || program === 'minor' || program === 'home') {
    const requireOption = offering.require_option.trim().toUpperCase();
    if (requireOption === 'R' || requireOption.includes('必')) return 'compulsory';
    if (requireOption === 'E' || requireOption.includes('選')) return 'elective';
  }
  return inferred;
}

export function toScheduledOffering(offering: CourseSearchResult): ScheduledOffering {
  return {
    semester: offering.semester,
    courseNo: offering.course_no,
    courseName: offering.course_name,
    teacher: offering.teacher,
    credits: offering.credits,
    classroom: offering.classroom,
    node: offering.node,
    slots: parseNodeSlots(offering.node),
    requireOption: offering.require_option,
    contents: offering.contents,
    gpa: offering.gpa,
    gpaStatus: offering.gpa_status,
    selectedCount: offering.selected_count,
    capacity: offering.capacity,
  };
}

export function courseFromOffering(
  offering: CourseSearchResult,
  requirement?: PendingRequirement,
  program: CourseProgram = requirement ? 'double_major' : 'other'
): Course {
  const scheduledOffering = toScheduledOffering(offering);
  const credits = offering.credits ?? requirement?.credits ?? requirement?.requiredCredits ?? 0;
  return {
    id: `${offering.course_no || offering.course_name}-${nextPlannerId()}`,
    name: offering.course_name,
    credits,
    category: categoryFromOfferingForProgram(offering, program),
    program,
    dimension: offering.dimension ? 'None' : undefined,
    sourceRequirementId: requirement?.id,
    sourceSetId: requirement?.setId,
    scheduledOffering,
    details: {
      professor: offering.teacher,
      location: offering.classroom,
      time: displaySlots(scheduledOffering.slots),
      gradingPolicy: [],
      notes: offering.contents,
    },
  };
}

export function categoryFromSyncedCourse(course: SyncedCourseRow): CourseCategory {
  const name = course.course_name.toLowerCase();
  const code = course.course_code.toUpperCase();
  if (code.startsWith('PE') || name.includes('體育')) return 'pe';
  if (name.includes('國文') || name.includes('中文') || name.includes('文學閱讀')) return 'chinese';
  if (name.includes('英文') || name.includes('english') || name.includes('英語')) return 'english';
  if (code.startsWith('GE')) return 'gen_ed';
  if (course.required_type === '必修') return 'compulsory';
  if (course.required_type === '選修') return 'elective';
  return 'unclassified';
}

export function slotCodeFromSyncedSlot(slot: ScheduleSyncResponse['slots'][number]): string {
  const weekdayCodes: Record<string, string> = {
    monday: 'M',
    tuesday: 'T',
    wednesday: 'W',
    thursday: 'R',
    friday: 'F',
    saturday: 'S',
    sunday: 'U',
  };
  const dayCode = weekdayCodes[slot.weekday_key] || '';
  return dayCode && slot.period ? `${dayCode}${slot.period}` : '';
}

export function uniqueTextValues(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];
  values.forEach((value) => {
    const text = value?.trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    normalized.push(text);
  });
  return normalized;
}

export function coursesFromScheduleSync(payload: ScheduleSyncResponse): Course[] {
  return payload.courses.map((course) => {
    const matchingSlots = payload.slots.filter((slot) => slot.course_name === course.course_name);
    const slots = uniqueTextValues(matchingSlots.map(slotCodeFromSyncedSlot));
    const classrooms = uniqueTextValues(matchingSlots.map((slot) => slot.location));
    const classroomText = classrooms.join(', ');
    const credits = typeof course.credits === 'number' ? course.credits : Number(course.credits) || 0;
    const scheduledOffering: ScheduledOffering = {
      semester: '1151',
      courseNo: course.course_code,
      courseName: course.course_name,
      teacher: course.professor,
      credits,
      classroom: classroomText,
      node: slots.join(', '),
      slots,
      requireOption: course.required_type,
      contents: course.note,
    };
    return {
      id: `school-${course.course_code || normalizeName(course.course_name)}-${nextPlannerId()}`,
      name: course.course_name,
      credits,
      category: categoryFromSyncedCourse(course),
      program: 'home',
      scheduledOffering,
      details: {
        professor: course.professor,
        location: classroomText,
        time: displaySlots(slots),
        gradingPolicy: [],
        notes: course.note,
      },
    };
  });
}

export function sanitizedHistoryCourseName(value: string): string {
  return value.replace(/★|◆/g, '').trim();
}

export function isZeroCreditCourse(record: HistoryCourseRecord): boolean {
  const name = record.course_name;
  const code = record.course_code.toUpperCase();
  return code.startsWith('PE') || name.includes('體育');
}

export function isFailedHistoryRecord(record: HistoryCourseRecord): boolean {
  const grade = record.grade.trim().toUpperCase();
  if (!grade || grade === '修習中') return false;
  if (['E', 'F', 'X'].includes(grade) || grade.includes('不及格')) return true;
  const credits = Number(record.earned_credits);
  return Number.isFinite(credits) && credits <= 0 && !isZeroCreditCourse(record);
}

export function historyStatus(record: HistoryCourseRecord): AcademicHistoryRecord['status'] {
  if (['修習中', '成績未到'].includes(record.grade.trim())) return 'in_progress';
  if (isFailedHistoryRecord(record)) return 'failed';
  return 'passed';
}

export function historyRecordKey(record: Pick<AcademicHistoryRecord, 'courseCode' | 'courseName'>): string {
  return record.courseCode.trim().toUpperCase() || normalizeName(record.courseName);
}

export function historicalLookupKey(record: AcademicHistoryRecord): string {
  return `${record.academicTerm}-${historyRecordKey(record)}`;
}

export function inferAdmissionYearFromStudentNo(studentNo: string): number | null {
  const match = studentNo.trim().toUpperCase().match(/^[A-Z]?(\d{3})/);
  if (!match) return null;
  const year = Number(match[1]);
  return Number.isFinite(year) ? year : null;
}

export function fallbackAdmissionYear(records: AcademicHistoryRecord[]): number | null {
  let earliestYear: number | null = null;
  records.forEach((record) => {
    const match = record.academicTerm.trim().match(/^(\d{3})[12]$/);
    if (!match) return;
    const year = Number(match[1]);
    if (!Number.isFinite(year)) return;
    earliestYear = earliestYear === null ? year : Math.min(earliestYear, year);
  });
  return earliestYear;
}

export function semesterIdForAcademicTerm(academicTerm: string, admissionYear: number | null): string | null {
  const match = academicTerm.trim().match(/^(\d{3})([12])$/);
  if (!match || admissionYear === null) return null;
  const academicYear = Number(match[1]);
  const semesterPart = match[2];
  if (!Number.isFinite(academicYear)) return null;
  const grade = academicYear - admissionYear + 1;
  if (grade < 1 || grade > 4) return null;
  return `${grade}-${semesterPart}`;
}

export function semesterNameForId(semesterId: string): string | null {
  const [grade, semesterPart] = semesterId.split('-');
  const gradeName = {
    '1': '大一',
    '2': '大二',
    '3': '大三',
    '4': '大四',
  }[grade];
  const termName = {
    '1': '上',
    '2': '下',
  }[semesterPart];
  return gradeName && termName ? `${gradeName}${termName}` : null;
}

export function resolveSemesterById(
  semesters: AppData['semesters'],
  semesterId: string
): AppData['semesters'][number] | undefined {
  const exact = semesters.find((semester) => semester.id === semesterId);
  if (exact) return exact;
  const fallbackName = semesterNameForId(semesterId);
  return fallbackName
    ? semesters.find((semester) => semester.name === fallbackName)
    : undefined;
}

export function semesterIdForStudentTerm(academicTerm: string, studentNo: string): string | null {
  return semesterIdForAcademicTerm(academicTerm, inferAdmissionYearFromStudentNo(studentNo));
}

export function semesterForStudentTerm(
  semesters: AppData['semesters'],
  academicTerm: string,
  studentNo: string
): AppData['semesters'][number] | null {
  const inferredSemesterId = semesterIdForStudentTerm(academicTerm, studentNo);
  if (!inferredSemesterId) return null;
  const inferredSemesterName = semesterNameForId(inferredSemesterId);
  return semesters.find((semester) => semester.id === inferredSemesterId)
    || semesters.find((semester) => semester.name === inferredSemesterName)
    || null;
}

export function semesterForAcademicTerm(
  semesters: AppData['semesters'],
  academicTerm: string,
  admissionYear: number | null
): AppData['semesters'][number] | null {
  const inferredSemesterId = semesterIdForAcademicTerm(academicTerm, admissionYear);
  if (!inferredSemesterId) return null;
  const inferredSemesterName = semesterNameForId(inferredSemesterId);
  return semesters.find((semester) => semester.id === inferredSemesterId)
    || semesters.find((semester) => semester.name === inferredSemesterName)
    || null;
}

export function historyRecordsFromImport(payload: HistoryImportResponse): AcademicHistoryRecord[] {
  return payload.records.map((record) => ({
    category: record.category,
    courseCode: record.course_code,
    courseName: sanitizedHistoryCourseName(record.course_name),
    academicTerm: record.academic_term,
    grade: record.grade,
    credits: Number(record.earned_credits) || 0,
    status: historyStatus(record),
    dimension: normalizeGenEdDimension(record.ge_dimension),
  }));
}

export function normalizeGenEdDimension(value: string | undefined): AcademicHistoryRecord['dimension'] {
  const normalized = value?.trim().toUpperCase();
  if (normalized && ['A', 'B', 'C', 'D', 'E', 'F'].includes(normalized)) {
    return normalized as AcademicHistoryRecord['dimension'];
  }
  return undefined;
}

export function categoryFromHistoryRecord(record: AcademicHistoryRecord): CourseCategory {
  const name = record.courseName;
  const code = record.courseCode.toUpperCase();
  if (code.startsWith('PE') || name.includes('體育')) return 'pe';
  if (name.includes('國文') || name.includes('中文') || name.includes('文學') || name.includes('表達')) return 'chinese';
  if (name.includes('英文') || name.includes('英語') || code.startsWith('CC101') || code.startsWith('CC105')) return 'english';
  if (name.includes('通識') || code.startsWith('GE') || record.category.includes('通識')) return 'gen_ed';
  if (record.category.includes('社會')) return 'social';
  if (record.category.includes('必修')) return 'compulsory';
  if (record.category.includes('選修')) return 'elective';
  return 'other';
}

export function historyStatusLabel(status: AcademicHistoryRecord['status']): string {
  if (status === 'in_progress') return '修習中';
  if (status === 'failed') return '不及格';
  return '已修過';
}

export function courseMatchesHistoryRecord(course: Course, record: AcademicHistoryRecord): boolean {
  if (normalizeName(course.name) === normalizeName(record.courseName)) return true;
  const recordCode = record.courseCode.trim().toUpperCase();
  const courseNo = course.scheduledOffering?.courseNo.trim().toUpperCase() || '';
  return Boolean(recordCode && courseNo && (courseNo.startsWith(recordCode) || recordCode.startsWith(courseNo)));
}

export function isHistoryImportedCourse(course: Course): boolean {
  return Boolean(course.details?.notes?.includes(HISTORY_IMPORT_NOTE_MARKER));
}

export function isFailedImportedHistoryCourse(course: Course): boolean {
  return isHistoryImportedCourse(course) && Boolean(course.details?.notes?.includes('狀態: 不及格'));
}

export function historicalLookupNote(lookup?: HistoricalScheduleLookup): string {
  if (!lookup) return '';
  if (lookup.status === 'matched') return '歷史節次: 已由課程查詢補查';
  if (lookup.status === 'ambiguous') return `歷史節次: 找到 ${lookup.candidateCount} 個候選班別，未自動排入`;
  if (lookup.status === 'missing') return '歷史節次: 查無開課資料';
  return '歷史節次: 課碼或學年期不足，未補查';
}

export function courseFromHistoryRecord(record: AcademicHistoryRecord, lookup?: HistoricalScheduleLookup): Course {
  const key = historyRecordKey(record).replace(/[^A-Z0-9_-]/gi, '-');
  const offering = lookup?.status === 'matched' ? lookup.offering : undefined;
  const scheduledOffering = offering ? toScheduledOffering(offering) : undefined;
  const notes = [
    HISTORY_IMPORT_NOTE_MARKER,
    record.courseCode ? `課碼: ${record.courseCode}` : '',
    record.academicTerm ? `學年期: ${record.academicTerm}` : '',
    record.grade ? `成績: ${record.grade}` : '',
    `狀態: ${historyStatusLabel(record.status)}`,
    historicalLookupNote(lookup),
    offering?.contents || '',
  ].filter(Boolean).join('\n');

  return {
    id: `history-${offering?.course_no || key}-${record.academicTerm || nextPlannerId()}`,
    name: offering?.course_name || record.courseName,
    credits: offering?.credits ?? (Number.isFinite(record.credits) ? record.credits : 0),
    category: categoryFromHistoryRecord(record),
    program: 'home',
    dimension: record.dimension,
    grade: record.grade || historyStatusLabel(record.status),
    scheduledOffering,
    details: {
      professor: offering?.teacher || '',
      location: offering?.classroom || '',
      time: scheduledOffering ? displaySlots(scheduledOffering.slots) : '',
      gradingPolicy: [],
      notes,
    },
  };
}

export function mergeCourseNotes(existingNotes: string | undefined, importedNotes: string | undefined): string {
  return uniqueTextValues([
    ...(existingNotes || '').split('\n'),
    ...(importedNotes || '').split('\n'),
  ]).join('\n');
}

export function mergeCourseWithHistoryRecord(existingCourse: Course, historyCourse: Course): Course {
  const existingDetails = existingCourse.details;
  const historyDetails = historyCourse.details;
  const existingGradingPolicy = existingDetails?.gradingPolicy || [];
  return {
    ...existingCourse,
    name: historyCourse.name || existingCourse.name,
    credits: historyCourse.credits || existingCourse.credits,
    category: historyCourse.category === 'unclassified' ? existingCourse.category : historyCourse.category,
    program: existingCourse.program ?? historyCourse.program,
    dimension: historyCourse.dimension ?? existingCourse.dimension,
    grade: historyCourse.grade || existingCourse.grade,
    scheduledOffering: historyCourse.scheduledOffering ?? existingCourse.scheduledOffering,
    details: {
      professor: historyDetails?.professor || existingDetails?.professor || '',
      email: existingDetails?.email || historyDetails?.email || '',
      location: historyDetails?.location || existingDetails?.location || '',
      time: historyDetails?.time || existingDetails?.time || '',
      link: existingDetails?.link || historyDetails?.link || '',
      gradingPolicy: existingGradingPolicy.length > 0 ? existingGradingPolicy : historyDetails?.gradingPolicy || [],
      notes: mergeCourseNotes(existingDetails?.notes, historyDetails?.notes),
    },
  };
}

export function mergeHistoryRecordsIntoSemesters(
  semesters: AppData['semesters'],
  records: AcademicHistoryRecord[],
  studentNo: string,
  lookups: Map<string, HistoricalScheduleLookup> = new Map()
): {
  semesters: AppData['semesters'];
  firstSemesterId: string | null;
  importedCourseCount: number;
  scheduledHistoryCourseCount: number;
} {
  const admissionYear = inferAdmissionYearFromStudentNo(studentNo) ?? fallbackAdmissionYear(records);
  let firstSemesterId: string | null = null;
  let importedCourseCount = 0;
  let scheduledHistoryCourseCount = 0;
  const seenHistoryKeys = new Set<string>();

  const nextSemesters = semesters.map((semester) => ({
    ...semester,
    courses: semester.courses.filter((course) => !isHistoryImportedCourse(course)),
  }));

  records.forEach((record) => {
    const targetSemester = semesterForAcademicTerm(nextSemesters, record.academicTerm, admissionYear);
    if (!targetSemester) return;

    const historyKey = `${targetSemester.id}-${record.academicTerm}-${historyRecordKey(record)}`;
    if (seenHistoryKeys.has(historyKey)) return;
    seenHistoryKeys.add(historyKey);

    const course = courseFromHistoryRecord(record, lookups.get(historicalLookupKey(record)));
    const existingCourseIndex = targetSemester.courses.findIndex((item) => courseMatchesHistoryRecord(item, record));
    if (existingCourseIndex >= 0) {
      targetSemester.courses = targetSemester.courses.map((item, index) => (
        index === existingCourseIndex ? mergeCourseWithHistoryRecord(item, course) : item
      ));
      importedCourseCount += 1;
      if (course.scheduledOffering?.slots.length) scheduledHistoryCourseCount += 1;
      if (!firstSemesterId) firstSemesterId = targetSemester.id;
      return;
    }

    targetSemester.courses = [...targetSemester.courses, course];
    importedCourseCount += 1;
    if (course.scheduledOffering?.slots.length) scheduledHistoryCourseCount += 1;
    if (!firstSemesterId) firstSemesterId = targetSemester.id;
  });

  return { semesters: nextSemesters, firstSemesterId, importedCourseCount, scheduledHistoryCourseCount };
}

export function retakeRequirementsFromHistory(records: AcademicHistoryRecord[]): PendingRequirement[] {
  const nonFailedKeys = new Set(records.filter((record) => record.status !== 'failed').map(historyRecordKey));
  return records
    .filter((record) => record.status === 'failed' && !nonFailedKeys.has(historyRecordKey(record)))
    .map((record) => ({
      id: `retake-${historyRecordKey(record)}`,
      setId: RETAKE_SET_ID,
      kind: 'course',
      title: record.courseName,
      credits: null,
      requiredCredits: null,
      courseNames: [record.courseName],
      options: [{ name: record.courseName, credits: null, courseNames: [record.courseName] }],
      note: `不及格待重修・${record.academicTerm}・${record.grade}`,
      courseCodePrefix: record.courseCode || null,
    }));
}

export function selectHistoricalOffering(record: AcademicHistoryRecord, results: CourseSearchResult[]): HistoricalScheduleLookup {
  const recordCode = record.courseCode.trim().toUpperCase();
  const normalizedCourseName = normalizeName(record.courseName);
  const codeMatched = results.filter((result) => {
    const courseNo = result.course_no.trim().toUpperCase();
    return Boolean(recordCode && (courseNo === recordCode || courseNo.startsWith(recordCode)));
  });
  const candidates = codeMatched.length > 0 ? codeMatched : results;
  const nameMatched = candidates.filter((result) => normalizeName(result.course_name) === normalizedCourseName);
  const plausible = nameMatched.length > 0 ? nameMatched : candidates;
  const withSlots = plausible.filter((result) => parseNodeSlots(result.node).length > 0);

  if (withSlots.length === 1) {
    return { status: 'matched', candidateCount: plausible.length, offering: withSlots[0] };
  }
  if (plausible.length === 0) {
    return { status: 'missing', candidateCount: 0 };
  }
  return { status: 'ambiguous', candidateCount: plausible.length };
}

export async function lookupHistoricalSchedules(records: AcademicHistoryRecord[]): Promise<Map<string, HistoricalScheduleLookup>> {
  const lookupEntries = await Promise.all(records.map(async (record): Promise<[string, HistoricalScheduleLookup]> => {
    const key = historicalLookupKey(record);
    if (!record.courseCode.trim() || !record.academicTerm.trim()) {
      return [key, { status: 'skipped', candidateCount: 0 }];
    }
    try {
      const results = await searchCourses(record.academicTerm, record.courseCode, 'code');
      return [key, selectHistoricalOffering(record, results)];
    } catch {
      return [key, { status: 'missing', candidateCount: 0 }];
    }
  }));
  return new Map(lookupEntries);
}

export function normalizeName(value: string): string {
  return value.replace(/\s+/g, '').replace(/（/g, '(').replace(/）/g, ')').toLowerCase();
}

export function getRequirementStatus(requirement: PendingRequirement, data: AppData): RequirementStatus {
  const scheduledCourses = [
    ...data.semesters.flatMap((semester) => semester.courses),
    ...(data.selectionPlan?.courses || []),
  ];
  const targetCredits = requirement.requiredCredits ?? requirement.credits ?? 0;
  const candidateNames = new Set(requirement.courseNames.map(normalizeName));
  const candidateCodePrefix = requirement.courseCodePrefix?.trim().toUpperCase() || '';
  let matched = scheduledCourses.filter((course) => course.sourceRequirementId === requirement.id);

  if (matched.length === 0 && candidateNames.size > 0) {
    matched = scheduledCourses.filter((course) => candidateNames.has(normalizeName(course.name)));
  }

  if (requirement.kind === 'credit_pool' && requirement.courseCodePrefix) {
    matched = scheduledCourses.filter((course) => {
      const code = course.scheduledOffering?.courseNo || '';
      return course.sourceRequirementId === requirement.id || code.startsWith(requirement.courseCodePrefix || '');
    });
  }

  const historyMatched = (data.historyRecords || []).filter((record) => {
    if (record.status === 'failed') return false;
    if (candidateNames.has(normalizeName(record.courseName))) return true;
    if (candidateCodePrefix && record.courseCode.toUpperCase().startsWith(candidateCodePrefix)) return true;
    return false;
  });
  const scheduledCredits = matched.reduce((sum, course) => sum + (Number.isFinite(course.credits) ? course.credits : 0), 0);
  const historyCredits = historyMatched.reduce((sum, record) => sum + record.credits, 0);
  const earnedCredits = Math.max(scheduledCredits, historyCredits);
  const matchedCount = Math.max(matched.length, historyMatched.length);
  const completed = requirement.kind === 'credit_pool'
    ? earnedCredits >= targetCredits
    : matchedCount > 0 && (targetCredits === 0 || earnedCredits >= Math.min(targetCredits, earnedCredits || targetCredits));

  return {
    completed,
    earnedCredits,
    targetCredits,
    scheduledCount: matchedCount,
  };
}

export function findConflicts(offering: CourseSearchResult, data: AppData, semesterId: string): Course[] {
  const slots = parseNodeSlots(offering.node);
  if (slots.length === 0) return [];
  const semester = data.semesters.find((item) => item.id === semesterId);
  if (!semester) return [];
  const slotSet = new Set(slots);
  return semester.courses.filter((course) =>
    !isHistoryImportedCourse(course) &&
    !isSameScheduledOffering(course, offering) &&
    (course.scheduledOffering?.slots || []).some((slot) => slotSet.has(slot))
  );
}

export function isSameScheduledOffering(course: Course, offering: CourseSearchResult): boolean {
  const scheduled = course.scheduledOffering;
  if (!scheduled) return false;
  if (scheduled.courseNo && offering.course_no) {
    return scheduled.courseNo === offering.course_no;
  }
  return (
    normalizeName(scheduled.courseName || course.name) === normalizeName(offering.course_name) &&
    scheduled.teacher === offering.teacher &&
    normalizeOfferingNode(scheduled.node) === normalizeOfferingNode(offering.node)
  );
}

export function normalizeOfferingNode(value: string): string {
  return parseNodeSlots(value).join(',');
}

export function findScheduledCourseByOffering(offering: CourseSearchResult, data: AppData, semesterId: string): Course | undefined {
  const semester = data.semesters.find((item) => item.id === semesterId);
  return semester?.courses.find((course) => !isHistoryImportedCourse(course) && isSameScheduledOffering(course, offering));
}

export function ensureManualSet(data: AppData): RequirementSet[] {
  if (data.requirementSets.some((set) => set.id === MANUAL_SET_ID)) return data.requirementSets;
  return [
    ...data.requirementSets,
    {
      id: MANUAL_SET_ID,
      name: '手動加入',
      department: '',
      source: 'manual',
      totalCredits: null,
      notes: [],
    },
  ];
}

export function uniqueId(base: string, existing: Set<string>): string {
  if (!existing.has(base)) return base;
  let index = 2;
  while (existing.has(`${base}-${index}`)) index += 1;
  return `${base}-${index}`;
}

export function normalizeImportPreview(preview: ApiImportPreview, data: AppData): { set: RequirementSet; requirements: PendingRequirement[] } {
  const rawSet = preview.requirement_set;
  const existingSetIds = new Set(data.requirementSets.map((set) => set.id));
  const setId = uniqueId(String(rawSet.id || `pdf-set-${nextPlannerId()}`), existingSetIds);
  const set: RequirementSet = {
    id: setId,
    name: String(rawSet.name || 'PDF 匯入需求'),
    department: String(rawSet.department || ''),
    source: 'pdf',
    sourceFileName: rawSet.source_file_name ? String(rawSet.source_file_name) : null,
    totalCredits: typeof rawSet.total_credits === 'number' ? rawSet.total_credits : null,
    notes: Array.isArray(rawSet.notes) ? rawSet.notes.map(String) : [],
  };

  const existingRequirementIds = new Set(data.pendingRequirements.map((requirement) => requirement.id));
  const requirements = preview.pending_requirements.map((rawRequirement, index) => {
    const id = uniqueId(String(rawRequirement.id || `pdf-req-${nextPlannerId()}-${index}`), existingRequirementIds);
    existingRequirementIds.add(id);
    const rawOptions = Array.isArray(rawRequirement.options) ? rawRequirement.options : [];
    const options: RequirementOption[] = rawOptions.map((option) => {
      const record = option as Record<string, unknown>;
      return {
        name: String(record.name || ''),
        credits: typeof record.credits === 'number' ? record.credits : null,
        courseNames: Array.isArray(record.course_names) ? record.course_names.map(String) : [],
      };
    });
    return {
      id,
      setId,
      kind: String(rawRequirement.kind || 'course') as PendingRequirement['kind'],
      title: String(rawRequirement.title || ''),
      credits: typeof rawRequirement.credits === 'number' ? rawRequirement.credits : null,
      requiredCredits: typeof rawRequirement.required_credits === 'number' ? rawRequirement.required_credits : null,
      courseNames: Array.isArray(rawRequirement.course_names) ? rawRequirement.course_names.map(String) : [],
      options,
      note: String(rawRequirement.note || ''),
      courseCodePrefix: rawRequirement.course_code_prefix ? String(rawRequirement.course_code_prefix) : null,
    };
  });

  return { set, requirements };
}
