import type { Semester, CourseCategory, GenEdDimension, CourseProgram, AppTargets } from './types';

export const INITIAL_SEMESTERS: Semester[] = [
  { id: '1-1', name: '大一上', courses: [] },
  { id: '1-2', name: '大一下', courses: [] },
  { id: '2-1', name: '大二上', courses: [] },
  { id: '2-2', name: '大二下', courses: [] },
  { id: '3-1', name: '大三上', courses: [] },
  { id: '3-2', name: '大三下', courses: [] },
  { id: '4-1', name: '大四上', courses: [] },
  { id: '4-2', name: '大四下', courses: [] },
];

export const DEFAULT_TARGETS: AppTargets = {
  total: 133,
  chinese: 3,
  english: 12,
  gen_ed: 16,
  pe_semesters: 6,
  social: 1,
  home_compulsory: 0,
  home_elective: 0,
  double_major: 0,
  minor: 0,
};

export const CATEGORY_LABELS: Record<CourseCategory, string> = {
  compulsory: '必修',
  elective: '選修',
  chinese: '國文',
  english: '英文',
  gen_ed: '通識',
  pe: '體育',
  social: '社會實踐',
  other: '其他',
  unclassified: '未歸類',
};

export const GEN_ED_LABELS: Record<GenEdDimension, string> = {
  A: 'A.人文素養',
  B: 'B.當代文明',
  C: 'C.美感與人生',
  D: 'D.社會歷史',
  E: 'E.群己制度',
  F: 'F.自然生命',
  None: '無/未分類',
};

export const PROGRAM_LABELS: Record<CourseProgram, string> = {
  home: '本系',
  double_major: '雙主修',
  minor: '輔修',
  other: '其他歸屬',
};
