import React, { useState, useEffect } from 'react';
import {
  Search,
  Clock,
  Plus,
  Settings,
  Trash2,
  Loader2,
  X,
  Save,
  PauseCircle,
  PlayCircle,
  Zap,
  RotateCcw
} from 'lucide-react';
import { supabase } from './supabaseClient';

interface Course {
  id: string;
  course_code: string;
  course_name: string;
  status: string;
  current_enrolled: string;
  auto_enroll: boolean;
  last_check_time: string;
  max_attempts: number;
  attempt_count: number;
  semester: string;
}

interface SemesterOption {
  semester: string;
  english_label: string;
  current: boolean;
}

interface CourseSettingsModalProps {
  course: Course;
  semesterOptions: SemesterOption[];
  onClose: () => void;
  onSaved: () => void;
}

const CourseSettingsModal: React.FC<CourseSettingsModalProps> = ({ course, semesterOptions, onClose, onSaved }) => {
  const [paused, setPaused] = useState(course.status === 'paused');
  const [maxAttempts, setMaxAttempts] = useState(course.max_attempts ?? 3);
  const [semester, setSemester] = useState(course.semester);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { error } = await supabase
        .from('monitored_courses')
        .update({
          status: paused ? 'paused' : (course.status === 'paused' ? 'monitoring' : course.status),
          max_attempts: maxAttempts,
          semester,
        })
        .eq('id', course.id);
      if (error) throw error;
      onSaved();
      onClose();
    } catch (e) {
      alert('儲存失敗：' + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden animate-zoomIn">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
          <div>
            <h3 className="text-base font-bold text-slate-800">課程設定</h3>
            <p className="text-xs text-slate-500 font-mono mt-0.5">{course.course_code} · {course.course_name}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-200">
            <div className="flex items-center gap-3">
              {paused
                ? <PauseCircle size={18} className="text-yellow-500" />
                : <PlayCircle size={18} className="text-green-500" />}
              <div>
                <div className="text-sm font-medium text-slate-800">監控狀態</div>
                <div className="text-xs text-slate-500">{paused ? '已暫停，Worker 不會檢查此課程' : '監控中'}</div>
              </div>
            </div>
            <button
              onClick={() => setPaused(p => !p)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${paused ? 'bg-yellow-500' : 'bg-green-500'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${paused ? 'translate-x-1' : 'translate-x-6'}`} />
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">學期</label>
            <select
              value={semester}
              onChange={e => setSemester(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              {mergeSemesterOptions(semesterOptions.length > 0 ? semesterOptions : FALLBACK_SEMESTER_OPTIONS, [course.semester]).map(option => (
                <option key={option.semester} value={option.semester}>
                  {formatSemesterLabel(option)}{option.current ? '（最新）' : ''}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-2">Worker 會以此學期查詢人數；換學期後下次檢查即生效。</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">最大自動加選次數</label>
            <div className="flex items-center gap-3">
              <input
                type="number"
                min={1}
                max={20}
                value={maxAttempts}
                onChange={e => setMaxAttempts(Math.min(20, Math.max(1, parseInt(e.target.value) || 1)))}
                className="w-24 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 text-center focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono"
              />
              <span className="text-xs text-slate-500">次（達上限後停止自動加選）</span>
            </div>
            <p className="text-xs text-slate-500 mt-2">達到上限後可重設次數以繼續嘗試加選。</p>
          </div>

          <div className="flex items-center justify-between p-4 bg-amber-50 rounded-xl border border-amber-200">
            <div>
              <div className="text-sm font-medium text-amber-800">重設加選次數</div>
              <div className="text-xs text-amber-600 mt-0.5">目前已嘗試 {course.attempt_count ?? 0} 次；歸零後下次檢查時會重新嘗試加選</div>
            </div>
            <button
              onClick={async () => {
                setResetting(true);
                try {
                  const { error } = await supabase
                    .from('monitored_courses')
                    .update({ attempt_count: 0 })
                    .eq('id', course.id);
                  if (error) throw error;
                  alert('已重設加選次數，Worker 下次檢查時會重新嘗試加選。');
                  onSaved();
                  onClose();
                } catch (e) {
                  alert('重設失敗：' + (e instanceof Error ? e.message : String(e)));
                } finally {
                  setResetting(false);
                }
              }}
              disabled={resetting}
              className="flex items-center gap-2 px-3 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {resetting ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
              重設
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700 transition-colors">取消</button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg flex items-center gap-2 disabled:opacity-50 transition-colors"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            儲存
          </button>
        </div>
      </div>
    </div>
  );
};

const NTUST_API = 'https://querycourse.ntust.edu.tw/QueryCourse/api/courses';
const NTUST_SEMESTERS_API = 'https://querycourse.ntust.edu.tw/QueryCourse/api/semestersinfo';
const isValidSemester = (semester: string) => /^[0-9]{4}$/.test(semester);
const FALLBACK_SEMESTER_OPTIONS: SemesterOption[] = [
  { semester: '1151', english_label: '2026 Fall', current: true },
  { semester: '1142', english_label: '2026 Spring', current: false },
  { semester: '1141', english_label: '2025 Fall', current: false },
  { semester: '1132', english_label: '2025 Spring', current: false },
];

const fetchSemesterOptions = async (): Promise<SemesterOption[]> => {
  try {
    const res = await fetch(NTUST_SEMESTERS_API, {
      headers: { Accept: 'application/json' },
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) {
        return data
          .map((item) => ({
            semester: String(item?.Semester || '').trim(),
            english_label: String(item?.EngSemester || '').trim(),
            current: Boolean(item?.CurrentSemester && item?.Static === false),
          }))
          .filter((item): item is SemesterOption => isValidSemester(item.semester));
      }
    }
  } catch {
    // Fall back below.
  }
  return FALLBACK_SEMESTER_OPTIONS;
};

const pickDefaultSemester = (options: SemesterOption[]): string => (
  options.find((item) => item.current)?.semester
  || options[0]?.semester
  || ''
);

const formatSemesterLabel = (option: SemesterOption): string => (
  option.english_label ? `${option.semester}・${option.english_label}` : option.semester
);

const mergeSemesterOptions = (base: SemesterOption[], extraSemesters: string[]): SemesterOption[] => {
  const merged = [...base];
  for (const semester of extraSemesters) {
    const value = String(semester || '').trim();
    if (!isValidSemester(value) || merged.some((item) => item.semester === value)) continue;
    merged.push({ semester: value, english_label: '', current: false });
  }
  return merged;
};

const lookupCourseInfo = async (courseCode: string, semester: string): Promise<{ name: string; enrolled: string; found: boolean | null }> => {
  try {
    const res = await fetch(NTUST_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        Semester: semester,
        CourseNo: courseCode,
        CourseName: '', CourseTeacher: '', Dimension: '',
        CourseNotes: '', CampusNotes: '',
        ForeignLanguage: 0, OnlyIntensive: 0, OnlyGeneral: 0,
        OnlyNTUST: 0, OnlyMaster: 0, OnlyUnderGraduate: 0, OnlyNode: 0,
        Language: 'zh'
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.length > 0) {
        const course = data[0];
        const enrolled = course.Restrict1 && course.Restrict1 !== '9999'
          ? `${course.ChooseStudent}/${course.Restrict1}`
          : `${course.ChooseStudent ?? '---'}`;
        return { name: course.CourseName || courseCode, enrolled, found: true };
      }
      // API 正常回應但沒有資料：這個學期查無此課程代碼
      return { name: courseCode, enrolled: '---', found: false };
    }
  } catch {
    // CORS or network issue — let Worker update later
  }
  return { name: courseCode, enrolled: '---', found: null };
};

const CoursesView: React.FC = () => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [newCourseCode, setNewCourseCode] = useState('');
  const [adding, setAdding] = useState(false);
  const [settingsCourse, setSettingsCourse] = useState<Course | null>(null);
  const [semesterOptions, setSemesterOptions] = useState<SemesterOption[]>([]);
  const [selectedSemester, setSelectedSemester] = useState('');

  useEffect(() => {
    let channel: ReturnType<typeof supabase.channel> | null = null;

    const init = async () => {
      const options = await fetchSemesterOptions();
      setSemesterOptions(options);
      setSelectedSemester(pickDefaultSemester(options));
      await fetchCourses();
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      channel = supabase
        .channel('courses_changes')
        .on('postgres_changes', {
          event: '*',
          schema: 'public',
          table: 'monitored_courses',
          filter: `user_id=eq.${user.id}`
        }, () => {
          fetchCourses();
        })
        .subscribe();
    };

    init();

    return () => {
      if (channel) supabase.removeChannel(channel);
    };
  }, []);

  const fetchCourses = async (silent = false) => {
    try {
      const { data, error } = await supabase
        .from('monitored_courses')
        .select('*')
        .order('created_at', { ascending: false });
      if (error) throw error;
      const nextCourses = data || [];
      setCourses(nextCourses);
      setSemesterOptions((prev) => mergeSemesterOptions(prev.length > 0 ? prev : FALLBACK_SEMESTER_OPTIONS, nextCourses.map((course) => course.semester)));
    } catch (error) {
      console.error('Error fetching courses:', error);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const addCourse = async () => {
    const code = newCourseCode.trim().toUpperCase();
    if (!code) return;
    const semester = selectedSemester || pickDefaultSemester(semesterOptions);
    if (!semester) {
      alert('無法載入學期清單，請稍後再試。');
      return;
    }
    if (courses.some(c => c.course_code.toUpperCase() === code && c.semester === semester)) {
      alert(`課程代碼 ${code}（學期 ${semester}）已在監控清單中`);
      return;
    }
    setAdding(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const courseInfo = await lookupCourseInfo(code, semester);
      if (courseInfo.found === false) {
        alert(`學期 ${semester} 查無課程代碼 ${code}，請確認代碼或改選其他學期。`);
        return;
      }
      const { error } = await supabase
        .from('monitored_courses')
        .insert({
          user_id: user.id,
          course_code: code,
          course_name: courseInfo.name,
          semester,
          status: 'pending',
          current_enrolled: courseInfo.enrolled,
          auto_enroll: false
        });
      if (error) throw error;
      setNewCourseCode('');
      fetchCourses();
    } catch (error) {
      console.error('Error adding course:', error);
      alert('新增失敗');
    } finally {
      setAdding(false);
    }
  };

  const toggleAutoAdd = async (id: string, currentStatus: boolean) => {
    try {
      const { error } = await supabase
        .from('monitored_courses')
        .update({ auto_enroll: !currentStatus })
        .eq('id', id);
      if (error) throw error;
      fetchCourses();
    } catch (error) {
      console.error('Error updating course:', error);
    }
  };

  const deleteCourse = async (id: string) => {
    if (!confirm('確定要刪除此監控任務嗎？')) return;
    try {
      const { error } = await supabase
        .from('monitored_courses')
        .delete()
        .eq('id', id);
      if (error) throw error;
      fetchCourses();
    } catch (error) {
      console.error('Error deleting course:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {settingsCourse && (
        <CourseSettingsModal
          course={settingsCourse}
          semesterOptions={semesterOptions}
          onClose={() => setSettingsCourse(null)}
          onSaved={() => fetchCourses()}
        />
      )}

      <header className="mb-8">
        <h2 className="text-2xl font-bold text-slate-800">課程管理</h2>
        <p className="text-slate-500 text-sm mt-1">輸入課程代碼以搜尋並加入監聽列表</p>
      </header>

      {/* Add Course */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-[220px_minmax(0,1fr)_auto]">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">學期</label>
            <select
              value={selectedSemester}
              onChange={(e) => setSelectedSemester(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {semesterOptions.length === 0 && selectedSemester && (
                <option value={selectedSemester}>{selectedSemester}</option>
              )}
              {semesterOptions.map((semester) => (
                <option key={semester.semester} value={semester.semester}>
                  {formatSemesterLabel(semester)}{semester.current ? '（最新）' : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
            <input
              type="text"
              value={newCourseCode}
              onChange={(e) => setNewCourseCode(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addCourse()}
              placeholder="例如：CS3001 或 AB1234"
              className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors text-slate-800"
            />
          </div>
          <button
            onClick={addCourse}
            disabled={adding || !newCourseCode || !selectedSemester}
            className="px-6 py-3 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 transition-colors whitespace-nowrap flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {adding ? <Loader2 className="animate-spin" size={18} /> : <Plus size={18} />}
            {adding ? '查詢中...' : '新增課程'}
          </button>
        </div>
      </div>

      {/* Course List */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <h3 className="font-semibold text-slate-800">已加入的課程 ({courses.length})</h3>
        </div>
        <div className="divide-y divide-slate-100">
          {courses.length > 0 ? courses.map(course => {
            const isMonitoring = course.status === 'monitoring';
            const isAvailable = course.status === 'available';
            const isPaused = course.status === 'paused';
            const isEnrolled = course.status === 'enrolled';

            return (
              <div key={course.id} className="p-6 flex flex-col sm:flex-row sm:items-center justify-between hover:bg-slate-50 transition-colors">
                <div className="flex items-start mb-4 sm:mb-0">
                  <div className={`mt-1 w-2.5 h-2.5 rounded-full mr-4 shrink-0 ${
                    isAvailable ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' :
                    isMonitoring ? 'bg-blue-500 animate-pulse' :
                    isEnrolled ? 'bg-emerald-500' :
                    isPaused ? 'bg-yellow-400' :
                    'bg-slate-300'
                  }`} />
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="font-bold text-slate-800 text-lg">{course.course_name}</h4>
                      <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded font-mono">{course.course_code}</span>
                      <span className="text-xs px-2 py-0.5 bg-slate-50 text-slate-500 rounded border border-slate-200">{course.semester}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                        isMonitoring ? 'bg-blue-50 text-blue-600 border-blue-200' :
                        isEnrolled   ? 'bg-emerald-50 text-emerald-600 border-emerald-200' :
                        isPaused     ? 'bg-yellow-50 text-yellow-600 border-yellow-200' :
                        course.status === 'error' ? 'bg-red-50 text-red-600 border-red-200' :
                        'bg-slate-50 text-slate-500 border-slate-200'
                      }`}>
                        {{ monitoring: '監控中', enrolled: '已加選', paused: '已暫停', pending: '待處理', error: '錯誤' }[course.status] ?? course.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-sm text-slate-500">
                      <span>人數: <span className={isAvailable ? 'text-green-600 font-medium' : 'text-slate-700'}>{course.current_enrolled}</span></span>
                      {course.auto_enroll && (
                        <span
                          title="加選嘗試次數／上限"
                          className={(course.attempt_count ?? 0) >= (course.max_attempts ?? 3) ? 'text-red-600 font-medium' : ''}
                        >
                          加選 {course.attempt_count ?? 0}/{course.max_attempts ?? 3}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock size={13} />
                        {course.last_check_time ? new Date(course.last_check_time).toLocaleTimeString() : '---'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between sm:justify-end w-full sm:w-auto gap-4 sm:gap-6 ml-6 sm:ml-0 border-t sm:border-0 border-slate-100 pt-4 sm:pt-0">
                  {/* Auto-add toggle */}
                  <div className="flex flex-col items-center justify-center border-r border-slate-200 pr-4 sm:pr-6">
                    <p className="text-[10px] text-slate-500 mb-1.5 font-medium flex items-center gap-1">
                      <Zap size={10} className={course.auto_enroll ? 'text-amber-500' : 'text-slate-300'} />
                      自動加選
                    </p>
                    <button
                      onClick={() => toggleAutoAdd(course.id, course.auto_enroll)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${course.auto_enroll ? 'bg-blue-600' : 'bg-slate-200'}`}
                    >
                      <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${course.auto_enroll ? 'translate-x-4' : 'translate-x-0.5'}`} />
                    </button>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-1 sm:gap-2 pl-2">
                    <button
                      onClick={() => setSettingsCourse(course)}
                      title="課程設定"
                      className="p-2 text-slate-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-colors"
                    >
                      <Settings size={20} />
                    </button>
                    <button
                      onClick={() => deleteCourse(course.id)}
                      title="刪除"
                      className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 size={20} />
                    </button>
                  </div>
                </div>
              </div>
            );
          }) : (
            <div className="p-12 text-center text-slate-500">
              <Search className="mx-auto text-slate-300 mb-4" size={48} />
              <p>尚未新增任何課程，請在上方輸入課程代碼</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CoursesView;
