export type CourseCategory = 
  | 'compulsory'   // 系必修
  | 'elective'     // 系選修/一般選修
  | 'chinese'      // 國文
  | 'english'      // 英文
  | 'gen_ed'       // 通識
  | 'pe'           // 體育
  | 'social'       // 社會實踐
  | 'other'        // 其他
  | 'unclassified'; // 未歸類

export type GenEdDimension = 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'None';
export type CourseProgram = 'home' | 'double_major' | 'minor' | 'other';
export type RequirementKind = 'course' | 'choice' | 'course_group' | 'credit_pool';
export type GpaStatus = 'not_enabled' | 'found' | 'no_data' | 'error';

export interface GradingItem {
  id: string;
  name: string;
  weight: number;
  score?: number;
}

export interface CourseDetails {
  professor?: string;
  email?: string;
  location?: string;
  time?: string;
  link?: string;
  gradingPolicy: GradingItem[];
  notes?: string;
}

export interface ScheduledOffering {
  semester: string;
  courseNo: string;
  courseName: string;
  teacher: string;
  credits?: number | null;
  classroom: string;
  node: string;
  slots: string[];
  requireOption: string;
  contents: string;
  gpa?: number | null;
  gpaStatus?: GpaStatus;
  selectedCount?: number | null;
  capacity?: number | null;
}

export interface Course {
  id: string;
  name: string;
  credits: number;
  category: CourseCategory;
  program?: CourseProgram;
  dimension?: GenEdDimension; // For General Education
  grade?: string;
  details?: CourseDetails;
  sourceRequirementId?: string;
  sourceSetId?: string;
  scheduledOffering?: ScheduledOffering;
  virtualSelection?: {
    status: 'rejected' | 'manual';
    reason: string;
    createdAt: string;
  };
}

export interface Semester {
  id: string;
  name: string;
  courses: Course[];
}

export interface SelectionPlan {
  targetAcademicTerm: string;
  targetLabel?: string;
  courses: Course[];
  officialSelectionCache?: OfficialSelectionSyncResponse | null;
  updatedAt?: string;
}

export interface SchoolSyncStatus {
  scheduleSyncedAt?: string;
  scheduleCourseCount?: number;
  historyImportedAt?: string;
  historyRecordCount?: number;
}

export interface SchoolCredentials {
  username: string;
  hasPassword: boolean;
}

export interface AppTargets {
  total: number;
  chinese: number;
  english: number;
  gen_ed: number;
  pe_semesters: number;
  social: number;
  home_compulsory: number;
  home_elective: number;
  double_major: number;
  minor: number;
}

/** GPA 密鑰狀態；密鑰本身只存在後端 app_private，前端不持有。 */
export interface GpaApiKeyStatus {
  enabled: boolean;
  hasApiKey: boolean;
  updatedAt?: string | null;
}

export interface ProgramDepartmentSettings {
  homeDepartmentCode?: string;
  doubleMajorDepartmentCode?: string;
  minorDepartmentCode?: string;
}

export interface AppSettings {
  programDepartments?: ProgramDepartmentSettings;
  [key: string]: unknown;
}

export interface RequirementOption {
  name: string;
  credits?: number | null;
  courseNames: string[];
}

export interface RequirementSet {
  id: string;
  name: string;
  department?: string;
  source: 'pdf' | 'manual' | 'system';
  sourceFileName?: string | null;
  totalCredits?: number | null;
  notes?: string[];
}

export interface PendingRequirement {
  id: string;
  setId: string;
  kind: RequirementKind;
  title: string;
  credits?: number | null;
  requiredCredits?: number | null;
  courseNames: string[];
  options: RequirementOption[];
  note?: string;
  courseCodePrefix?: string | null;
}

export type AcademicHistoryStatus = 'passed' | 'in_progress' | 'failed';

export interface AcademicHistoryRecord {
  category: string;
  courseCode: string;
  courseName: string;
  academicTerm: string;
  grade: string;
  credits: number;
  status: AcademicHistoryStatus;
  dimension?: GenEdDimension;
}

export interface AppData {
  [key: string]: unknown;
  schemaVersion: number;
  semesters: Semester[];
  targets: AppTargets;
  settings?: AppSettings;
  selectionPlan?: SelectionPlan;
  /** When school data was last pulled through the backend; shown as sync status. */
  schoolSync?: SchoolSyncStatus;
  requirementSets: RequirementSet[];
  pendingRequirements: PendingRequirement[];
  historyRecords: AcademicHistoryRecord[];
}

export interface PlannerStats {
  total: number;
  chinese: number;
  english: number;
  gen_ed: number;
  pe_semesters: number;
  social: number;
  homeCompulsory: number;
  homeElective: number;
  doubleMajor: number;
  minor: number;
  genEdDimensions: Set<string>;
}

export interface CourseSearchResult {
  semester: string;
  course_no: string;
  course_name: string;
  teacher: string;
  dimension: string;
  credits: number | null;
  require_option: string;
  classroom: string;
  node: string;
  contents: string;
  gpa?: number | null;
  gpa_status?: GpaStatus;
  selected_count?: number | null;
  capacity?: number | null;
}

export interface CourseSemesterInfo {
  semester: string;
  english_label?: string | null;
  current: boolean;
}

export interface RequirementPdfImportResponse {
  requirement_set: RequirementSet;
  pending_requirements: PendingRequirement[];
  warnings: string[];
  raw_text_preview: string;
}

export interface ScheduleSyncRequest {
  username: string;
  password: string;
  profile_key?: string | null;
  persist_to_supabase: boolean;
  verify_ssl: boolean;
}

export interface SyncedCourseRow {
  course_code: string;
  course_name: string;
  credits: number | string;
  required_type: string;
  professor: string;
  note: string;
}

export interface SyncedScheduleSlot {
  weekday_key: string;
  weekday_label: string;
  period: string;
  time: string;
  course_name: string;
  location: string;
  raw: string;
}

export interface ScheduleSyncResponse {
  profile_key: string;
  school_account: string;
  student_name?: string | null;
  source_url: string;
  page_title: string;
  total_credits_text: string;
  total_credits: number | null;
  synced_at: string;
  course_count: number;
  scheduled_slot_count: number;
  schedule_entry_count: number;
  persisted_to_supabase: boolean;
  courses: SyncedCourseRow[];
  slots: SyncedScheduleSlot[];
}

export interface HistoryCourseRecord {
  category: string;
  course_code: string;
  course_name: string;
  academic_term: string;
  grade: string;
  earned_credits: string;
  ge_dimension?: string;
}

export interface HistoryImportResponse {
  profile_key: string;
  school_account: string;
  student_name?: string | null;
  student_no?: string | null;
  department?: string | null;
  status?: string | null;
  source_url: string;
  page_title: string;
  imported_at: string;
  record_count: number;
  persisted_to_supabase: boolean;
  summary_texts: string[];
  records: HistoryCourseRecord[];
}

export interface OfficialSelectionAvailableCourse {
  course_no: string;
  course_name: string;
  teacher: string;
  gpa?: number | null;
  gpa_status?: GpaStatus;
}

export interface OfficialSelectionRegisteredCourse {
  priority?: number | null;
  raw_priority: string;
  course_no: string;
  course_name: string;
  credits?: number | null;
  require_option?: string;
  teacher?: string;
  classroom?: string;
  node?: string;
  contents?: string;
  selected_count?: number | null;
  capacity?: number | null;
  gpa?: number | null;
  gpa_status?: GpaStatus;
}

export interface OfficialSelectionRequiredPresetCourse {
  course_no: string;
  course_name: string;
  credits?: number | null;
  require_option?: string;
  teacher?: string;
  classroom?: string;
  node?: string;
  contents?: string;
  selected_count?: number | null;
  capacity?: number | null;
  gpa?: number | null;
  gpa_status?: GpaStatus;
}

export interface OfficialSelectionSyncResponse {
  profile_key: string;
  school_account: string;
  source_url: string;
  page_title: string;
  synced_at: string;
  session_valid: boolean;
  available_count: number;
  registered_count: number;
  available_courses: OfficialSelectionAvailableCourse[];
  registered_courses: OfficialSelectionRegisteredCourse[];
  schedule_rows: Record<string, string>[];
  selection_list_rows: Record<string, string>[];
  required_preset_rows: Record<string, string>[];
  required_preset_courses: OfficialSelectionRequiredPresetCourse[];
  notices: string[];
}
