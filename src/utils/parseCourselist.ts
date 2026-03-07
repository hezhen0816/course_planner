import type { Course, CourseCategory } from '../types';

interface ParsedCourseWithSemester {
  semesterId: string;
  course: Course;
}

/**
 * 從選課清單 HTML 中解析課程資訊
 * @param html 選課清單 HTML 內容
 * @returns 解析後的課程列表，包含學期資訊
 */
export function parseCourselistHTML(html: string): ParsedCourseWithSemester[] {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  // 解析學期資訊 (例如: 1142 = 114年第2學期)
  const semesterId = parseSemesterFromHTML(doc);

  // 尋找包含課程資訊的表格
  const tables = doc.querySelectorAll('table');
  let courseTable: Element | null = null;
  let maxRows = 0;

  // 查找選課清單表格（包含課碼、課程名稱、學分數、必選修等欄位）
  // 選擇有最多資料列的表格（因為頁面上可能有多個類似表格）
  for (const table of tables) {
    const firstRow = table.querySelector('tr');
    if (!firstRow) continue;
    
    const headerText = firstRow.textContent || '';
    
    if (
      headerText.includes('課碼') &&
      headerText.includes('課程名稱') &&
      headerText.includes('學分數')
    ) {
      // 計算這個表格有多少資料列
      const rows = table.querySelectorAll('tr');
      if (rows.length > maxRows) {
        maxRows = rows.length;
        courseTable = table;
      }
    }
  }

  if (!courseTable || maxRows <= 1) {
    throw new Error('找不到選課清單資訊，請確認上傳的檔案是否為選課清單頁面');
  }

  const rows = courseTable.querySelectorAll('tr');
  const courses: ParsedCourseWithSemester[] = [];

  // 從第二行開始解析（跳過表頭）
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const cells = row.querySelectorAll('td');
    if (cells.length < 5) continue;

    const courseCode = cells[0].textContent?.trim() || '';
    const courseName = cells[1].textContent?.trim() || '';
    const creditsStr = cells[2].textContent?.trim() || '0';
    const courseType = cells[3].textContent?.trim() || ''; // 必修/選修
    const professor = cells[4].textContent?.trim() || '';

    // 跳過空行或表頭行
    if (!courseCode || !courseName || courseName === '課程名稱' || courseCode === '課碼') continue;

    // 解析學分數
    let credits = parseFloat(creditsStr);
    if (isNaN(credits)) credits = 0;

    // 判斷課程類別
    const category = determineCourseCategory(courseName, courseCode, courseType);

    // 建立課程物件
    const course: Course = {
      id: courseCode || `course-${Date.now()}-${Math.random()}`,
      name: courseName,
      credits: credits,
      category: category,
      program: 'home',
      dimension: 'None',
      details: professor
        ? {
            professor: professor,
            gradingPolicy: []
          }
        : undefined
    };

    courses.push({
      semesterId,
      course
    });
  }

  if (courses.length === 0) {
    throw new Error('未找到任何課程資料，請確認檔案內容');
  }

  return courses;
}

/**
 * 從 HTML 中解析學期資訊
 * 例如: 1142 = 114年第2學期 (下學期)
 */
function parseSemesterFromHTML(doc: Document): string {
  // 嘗試從頁面中尋找學期資訊 (例如: "選課清單(1142)" 或 "1142")
  const bodyText = doc.body.textContent || '';

  // 匹配學期格式: 1141, 1142, 1131, 1132 等
  const semesterMatch = bodyText.match(/\((\d{3})([12])\)/) || bodyText.match(/\b(\d{3})([12])\b/);

  if (semesterMatch) {
    const academicYear = parseInt(semesterMatch[1], 10);
    const semester = parseInt(semesterMatch[2], 10);
    return convertToSemesterId(academicYear, semester);
  }

  // 如果找不到學期資訊，預設為大一上
  return '1-1';
}

function convertToSemesterId(academicYear: number, semester: number): string {
  const currentAcademicYear = getCurrentAcademicYear();
  // 以目前學年度為大一，往前推估年級；避免超出既有 1-4 年級欄位
  const estimatedGrade = currentAcademicYear - academicYear + 1;
  const gradeLevel = Math.max(1, Math.min(4, estimatedGrade));
  const semesterSuffix = semester === 2 ? '2' : '1';
  return `${gradeLevel}-${semesterSuffix}`;
}

function getCurrentAcademicYear(): number {
  const now = new Date();
  const rocYear = now.getFullYear() - 1911;
  // 台灣學年度通常從 8 月開始
  return now.getMonth() >= 7 ? rocYear : rocYear - 1;
}

/**
 * 根據課程資訊判斷課程類別
 */
function determineCourseCategory(
  courseName: string,
  courseCode: string,
  courseType: string
): CourseCategory {
  const name = courseName.toLowerCase();
  const code = courseCode.toUpperCase();

  // 檢查特定課程類別
  if (code.startsWith('PE') || name.includes('體育')) {
    return 'pe';
  }

  if (
    name.includes('國文') ||
    name.includes('中文') ||
    name.includes('文學') ||
    name.includes('表達')
  ) {
    return 'chinese';
  }

  if (
    name.includes('英文') ||
    name.includes('english') ||
    name.includes('英語')
  ) {
    return 'english';
  }

  if (name.includes('社會實踐')) {
    return 'social';
  }

  // 通識課程 (課碼以 GE 開頭)
  if (code.startsWith('GE')) {
    return 'gen_ed';
  }

  // 根據課程類型判斷
  if (courseType.includes('必修')) {
    return 'compulsory';
  }

  if (courseType.includes('選修')) {
    return 'elective';
  }

  // 預設為未分類
  return 'unclassified';
}
