type CourseDepartment = {
  code: string;
  name: string;
};

const COURSE_DEPARTMENTS: Record<string, string> = {
  AC: '自動化及控制研究所／工程技術研究所',
  AD: '建築系',
  AE: '先進科技全英語學士學位學程',
  AI: '人工智慧跨域科技研究所',
  AS: '先進半導體科技研究所',
  AT: '應用科技學士學位學程',
  BA: '企業管理系',
  BB: '醫學工程學士學位學程',
  BE: '醫學工程研究所',
  CC: '人文社會學科／語言中心',
  CD: '創意設計學士班',
  CE: '工程學士班',
  CH: '化學工程系',
  CI: '色彩與照明科技研究所',
  CS: '資訊工程系',
  CT: '營建工程系',
  CX: '色彩影像與照明科技學士學位學程',
  DE: '設計研究所',
  DT: '設計系',
  EC: '電資學士班',
  EE: '電機工程系',
  EN: '應用科技研究所／工程技術研究所',
  EO: '光電工程研究所',
  EP: '師資培育中心',
  ES: '能源永續科技研究所',
  ET: '電子工程系',
  FB: '財務金融學士學位學程',
  FE: '語言中心',
  FL: '應用外語系',
  FN: '財務金融研究所',
  GD: '全球發展工程學士學位學程',
  GE: '人文社會學科',
  GX: '綠能產業機電工程學士學位學程',
  HC: '不分系學士班',
  IB: '智慧財產權學士學位學程',
  IC: '資通科技國際學士學位學程',
  IM: '工業管理系',
  IS: '國際半導體製程設備學士後外國學生專班',
  MA: 'MBA Program',
  MB: '管理學士班',
  ME: '機械工程系',
  MG: '管理研究所',
  MI: '資訊管理系',
  MS: '材料科技學程／材料科技研究所',
  PA: '專利研究所',
  PE: '體育室',
  RD: '高階科技研發碩士學位學程',
  SA: '學務處服務型通識課程／軍訓課程',
  SD: '半導體高階經營暨研發碩士在職學位學程',
  SG: '新加坡管理碩士在職專班',
  SI: '智慧製造科技研究所',
  TB: '科技管理學士學位學程',
  TC: '通識教育中心／軍訓課程',
  TE: '先進科技全英語外國學生專班',
  TM: '科技管理研究所',
  TX: '材料科學與工程系／高分子工程系',
  VE: '數位學習與教育研究所／技術及職業教育研究所',
  '3N': '校際課程（國立臺灣師範大學）',
  '3T': '校際課程（國立臺灣大學）',
  ZA: '校際課程（AI 聯盟課程）',
};

export function parseCourseDepartment(courseNo: string): CourseDepartment | null {
  const code = courseNo.trim().slice(0, 2).toUpperCase();
  if (!code) return null;
  const name = COURSE_DEPARTMENTS[code];
  return name ? { code, name } : { code, name: '未識別' };
}

export function listCourseDepartments(): CourseDepartment[] {
  return Object.entries(COURSE_DEPARTMENTS).map(([code, name]) => ({ code, name }));
}
