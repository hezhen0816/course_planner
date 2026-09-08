import { supabase } from '../../shared/supabase';
import type { CourseSearchResult } from '../../shared/types';

export type AddMonitoredCourseResult =
  | { ok: true; message: string }
  | { ok: false; message: string };

/** 從課程查詢結果直接加入選課監控（狀態 pending，worker 下一輪會補課名與人數）。 */
export async function addMonitoredCourse(
  offering: Pick<CourseSearchResult, 'course_no' | 'course_name' | 'semester' | 'selected_count' | 'capacity'>,
): Promise<AddMonitoredCourseResult> {
  if (!supabase) return { ok: false, message: 'Supabase 未設定，無法加入監聽。' };
  const code = offering.course_no.trim().toUpperCase();
  const semester = (offering.semester || '').trim();
  if (!code || !semester) return { ok: false, message: '此筆結果缺少課程代碼或學期，無法加入監聽。' };

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, message: '請先登入後再加入監聽。' };

  const { data: existing, error: lookupError } = await supabase
    .from('monitored_courses')
    .select('id')
    .eq('user_id', user.id)
    .eq('course_code', code)
    .eq('semester', semester)
    .limit(1);
  if (lookupError) return { ok: false, message: `查詢監聽清單失敗：${lookupError.message}` };
  if (existing && existing.length > 0) return { ok: false, message: `${code}（學期 ${semester}）已在監聽清單中。` };

  const enrolled = offering.capacity && offering.capacity !== 9999 && offering.selected_count != null
    ? `${offering.selected_count}/${offering.capacity}`
    : offering.selected_count != null ? String(offering.selected_count) : null;

  const { error } = await supabase.from('monitored_courses').insert({
    user_id: user.id,
    course_code: code,
    course_name: offering.course_name || code,
    semester,
    status: 'pending',
    current_enrolled: enrolled,
    auto_enroll: false,
  });
  if (error) return { ok: false, message: `加入監聽失敗：${error.message}` };
  return { ok: true, message: `已將 ${offering.course_name || code}（${code}）加入監聽，可到「選課監控」頁開啟自動加選。` };
}
