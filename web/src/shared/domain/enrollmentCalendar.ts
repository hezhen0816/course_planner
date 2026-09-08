/**
 * 選課作業時程表（教務處公告，來源：「115 學年度第 1 學期選課作業時程表」PDF）。
 *
 * 用途：把「現在是哪個選課階段」變成可推導的事實，而不是靠使用者在設定裡手選。
 * 選課工作台的預設模式、以及監控頁「選課時段」是否與當期一致，都由這裡判斷。
 *
 * 換學期時只需要新增一組 `SemesterEnrollmentCalendar`；日期用民國年換算後的西元日期。
 */

export type EnrollmentPhaseKind =
  | 'preregistration'      // 初選（含臺灣大學系統、新生轉學生初選）
  | 'addDrop'              // 全校加退選
  | 'correction'           // 選課更正期間
  | 'secondWithdrawal'     // 二次退選
  | 'closed';              // 非任何選課階段

export interface EnrollmentPhase {
  kind: EnrollmentPhaseKind;
  label: string;
  /** 起始（含），本地時間 */
  start: Date;
  /** 結束（含），本地時間 */
  end: Date;
  note?: string;
}

export interface SemesterEnrollmentCalendar {
  /** 學年期代碼，例如 1151 */
  semester: string;
  phases: EnrollmentPhase[];
}

/** 民國年月日時分 → Date（本地時間）。 */
function roc(year: number, month: number, day: number, hour = 0, minute = 0): Date {
  return new Date(year + 1911, month - 1, day, hour, minute, 0, 0);
}

export const ENROLLMENT_CALENDARS: SemesterEnrollmentCalendar[] = [
  {
    semester: '1151',
    phases: [
      {
        kind: 'preregistration',
        label: '本校課程初選',
        start: roc(115, 6, 12, 9, 0),
        end: roc(115, 6, 24, 17, 0),
        note: '6/12 09:00–6/15 17:00 上機登記；6/16–6/17 志願序抽籤；6/18 09:00 查抽籤結果；6/22 09:00–6/24 17:00 繼續選課',
      },
      {
        kind: 'preregistration',
        label: '臺灣大學系統課程初選',
        start: roc(115, 8, 6, 9, 0),
        end: roc(115, 8, 11, 23, 59),
        note: '8/6 09:00–8/10 12:00 上機登記；8/10 下午抽籤；8/11 09:00 查結果',
      },
      {
        kind: 'preregistration',
        label: '新生及轉學生初選',
        start: roc(115, 8, 14, 9, 0),
        end: roc(115, 8, 24, 17, 0),
      },
      {
        kind: 'addDrop',
        label: '全校加退選',
        start: roc(115, 9, 7, 9, 0),
        end: roc(115, 9, 21, 17, 0),
        note: '先選先上，至額滿為止；人工選課採授權碼方式',
      },
      {
        kind: 'correction',
        label: '選課更正期間',
        start: roc(115, 9, 22, 0, 0),
        end: roc(115, 9, 24, 23, 59),
        note: '僅更正錯誤，不得藉以辦理加退選',
      },
      {
        kind: 'secondWithdrawal',
        label: '二次退選',
        start: roc(115, 11, 16, 9, 0),
        end: roc(115, 12, 3, 17, 0),
      },
    ],
  },
];

const CLOSED_PHASE: EnrollmentPhase = {
  kind: 'closed',
  label: '非選課階段',
  start: new Date(0),
  end: new Date(0),
};

export function calendarForSemester(semester: string): SemesterEnrollmentCalendar | undefined {
  return ENROLLMENT_CALENDARS.find((item) => item.semester === semester);
}

/** 目前所處階段；沒有時程資料或不在任何區間時回 `closed`。 */
export function currentEnrollmentPhase(semester: string, now: Date = new Date()): EnrollmentPhase {
  const calendar = calendarForSemester(semester);
  if (!calendar) return CLOSED_PHASE;
  return calendar.phases.find((phase) => now >= phase.start && now <= phase.end) ?? CLOSED_PHASE;
}

/** 下一個即將到來的階段，用來在非選課期告訴使用者「下一次是什麼時候」。 */
export function nextEnrollmentPhase(semester: string, now: Date = new Date()): EnrollmentPhase | undefined {
  const calendar = calendarForSemester(semester);
  if (!calendar) return undefined;
  return calendar.phases
    .filter((phase) => phase.start > now)
    .sort((a, b) => a.start.getTime() - b.start.getTime())[0];
}

export function formatPhaseRange(phase: EnrollmentPhase): string {
  const fmt = (d: Date) => `${d.getMonth() + 1}/${d.getDate()}`;
  const time = (d: Date) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return `${fmt(phase.start)} ${time(phase.start)} – ${fmt(phase.end)} ${time(phase.end)}`;
}

/** 監控 worker 的選課時段代碼：加退選走 B01，初選（含抽籤後繼續選課）走 A06。 */
export function enrollmentPeriodCode(phase: EnrollmentPhase): 'A06' | 'B01' {
  return phase.kind === 'addDrop' ? 'B01' : 'A06';
}
