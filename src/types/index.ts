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

export interface Course {
  id: string;
  name: string;
  credits: number;
  category: CourseCategory;
  program?: CourseProgram;
  dimension?: GenEdDimension; // For General Education
  grade?: string;
  details?: CourseDetails;
}

export interface Semester {
  id: string;
  name: string;
  courses: Course[];
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

export interface AppData {
  semesters: Semester[];
  targets: AppTargets;
}
