import { useMemo, useState } from 'react';
import type { Course, CourseCategory, GenEdDimension, PlannerStats } from './types';
import { useAuth } from './hooks/useAuth';
import { useCourseData } from './hooks/useCourseData';
import { AuthPage } from './components/AuthPage';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { SemesterGrid } from './components/SemesterGrid';
import { CourseModal } from './components/CourseModal';
import { SettingsModal } from './components/SettingsModal';
import { CourseDetailModal } from './components/CourseDetailModal';
import { OnboardingModal } from './components/OnboardingModal';
import { parseCourselistHTML } from './utils/parseCourselist';

export default function CoursePlannerWebApp() {
  const { session, loading: authLoading } = useAuth();
  const [isDemoMode, setIsDemoMode] = useState(false);
  
  const { data, setData, syncStatus, isLoading: dataLoading } = useCourseData(session);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCourse, setEditingCourse] = useState<{ semesterId: string, course: Course } | null>(null);
  
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailCourse, setDetailCourse] = useState<{ semesterId: string, course: Course } | null>(null);

  const [activeSemesterId, setActiveSemesterId] = useState<string>('1-1');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState<boolean>(() => {
    const hasSeenOnboarding = localStorage.getItem('hasSeenOnboarding');
    return !hasSeenOnboarding;
  });

  const handleCloseOnboarding = () => {
    setIsOnboardingOpen(false);
    localStorage.setItem('hasSeenOnboarding', 'true');
  };

  // --- Computed Stats ---
  const stats = useMemo<PlannerStats>(() => {
    const current: PlannerStats = {
      total: 0,
      chinese: 0,
      english: 0,
      gen_ed: 0,
      pe_semesters: 0,
      social: 0,
      homeCompulsory: 0,
      homeElective: 0,
      doubleMajor: 0,
      minor: 0,
      genEdDimensions: new Set<string>(),
    };

    data.semesters.forEach(sem => {
      let hasPE = false;
      sem.courses.forEach(course => {
        const credits = isNaN(course.credits) ? 0 : course.credits;
        const program = course.program ?? 'home';

        if (course.category === 'pe') {
          hasPE = true;
          return; 
        }
        
        if (course.category === 'social') {
            current.social += 1;
            return;
        }

        current.total += credits;

        if (course.category === 'chinese') current.chinese += credits;
        if (course.category === 'english') current.english += credits;
        if (course.category === 'gen_ed') {
            current.gen_ed += credits;
            if (course.dimension && course.dimension !== 'None') {
                current.genEdDimensions.add(course.dimension);
            }
        }
        if (program === 'double_major') current.doubleMajor += credits;
        if (program === 'minor') current.minor += credits;
        if (program === 'home' && course.category === 'compulsory') current.homeCompulsory += credits;
        if (program === 'home' && course.category === 'elective') current.homeElective += credits;
      });
      if (hasPE) current.pe_semesters += 1;
    });

    return current;
  }, [data]);

  // --- Handlers ---

  const handleOpenAdd = (semesterId: string) => {
    setActiveSemesterId(semesterId);
    setEditingCourse(null);
    setIsModalOpen(true);
  };

  const handleEdit = (semesterId: string, course: Course) => {
    setActiveSemesterId(semesterId);
    setEditingCourse({ semesterId, course });
    setIsModalOpen(true);
  };

  const handleOpenDetail = (semesterId: string, course: Course) => {
    setDetailCourse({ semesterId, course });
    setIsDetailOpen(true);
  };

  const handleDelete = (semesterId: string, courseId: string) => {
    if (!window.confirm('確定要刪除這門課程嗎？')) return;
    setData(prev => ({
      ...prev,
      semesters: prev.semesters.map(s => {
        if (s.id !== semesterId) return s;
        return { ...s, courses: s.courses.filter(c => c.id !== courseId) };
      })
    }));
  };

  const handleMoveCourse = (semesterId: string, courseId: string, direction: 'up' | 'down') => {
    setData(prev => ({
      ...prev,
      semesters: prev.semesters.map(s => {
        if (s.id !== semesterId) return s;

        const currentIndex = s.courses.findIndex(c => c.id === courseId);
        if (currentIndex === -1) return s;

        const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
        if (targetIndex < 0 || targetIndex >= s.courses.length) return s;

        const nextCourses = [...s.courses];
        [nextCourses[currentIndex], nextCourses[targetIndex]] = [nextCourses[targetIndex], nextCourses[currentIndex]];
        return { ...s, courses: nextCourses };
      })
    }));
  };

  const handleSortCoursesByCategory = (semesterId: string) => {
    const categoryOrder: Record<CourseCategory, number> = {
      compulsory: 1,
      elective: 2,
      gen_ed: 3,
      chinese: 4,
      english: 5,
      social: 6,
      pe: 7,
      other: 8,
      unclassified: 9,
    };

    setData(prev => ({
      ...prev,
      semesters: prev.semesters.map(s => {
        if (s.id !== semesterId) return s;
        const nextCourses = [...s.courses].sort((a, b) => {
          const categoryDiff = categoryOrder[a.category] - categoryOrder[b.category];
          if (categoryDiff !== 0) return categoryDiff;
          return a.name.localeCompare(b.name, 'zh-Hant');
        });
        return { ...s, courses: nextCourses };
      })
    }));
  };

  const handleSaveCourse = (newCourse: Course) => {
    setData(prev => {
      const newSemesters = prev.semesters.map(s => {
        if (s.id !== activeSemesterId) {
          if (editingCourse && editingCourse.semesterId === s.id && editingCourse.semesterId !== activeSemesterId) {
             return { ...s, courses: s.courses.filter(c => c.id !== editingCourse.course.id) };
          }
          return s;
        }

        if (editingCourse && editingCourse.semesterId === activeSemesterId) {
          return {
            ...s,
            courses: s.courses.map(c => c.id === editingCourse.course.id ? newCourse : c)
          };
        } else {
          return { ...s, courses: [...s.courses, newCourse] };
        }
      });

      return { ...prev, semesters: newSemesters };
    });

    setIsModalOpen(false);
  };

  const handleSaveDetail = (updatedCourse: Course) => {
    if (!detailCourse) return;
    
    setData(prev => {
      const newSemesters = prev.semesters.map(s => {
        if (s.id !== detailCourse.semesterId) return s;
        return {
          ...s,
          courses: s.courses.map(c => c.id === updatedCourse.id ? updatedCourse : c)
        };
      });
      return { ...prev, semesters: newSemesters };
    });
    setIsDetailOpen(false);
  };

  const handleSaveSettings = (newTargets: typeof data.targets) => {
    setData(prev => ({
      ...prev,
      targets: newTargets
    }));
    setIsSettingsOpen(false);
  };

  const parseAndImportData = (html: string) => {
    try {
      // 先嘗試解析為選課清單格式
      try {
        const newCourses = parseCourselistHTML(html);
        
        if (newCourses.length === 0) {
          alert('未找到可匯入的課程資料');
          return;
        }

        setData(prev => {
          const newSemesters = prev.semesters.map(sem => {
            const coursesToAdd = newCourses
              .filter(nc => nc.semesterId === sem.id)
              .map(nc => nc.course);
            
            const existingNames = new Set(sem.courses.map(c => c.name));
            const uniqueCoursesToAdd = coursesToAdd.filter(c => !existingNames.has(c.name));

            return {
              ...sem,
              courses: [...sem.courses, ...uniqueCoursesToAdd]
            };
          });
          return { ...prev, semesters: newSemesters };
        });

        alert(`成功匯入 ${newCourses.length} 門課程！`);
        return;
      } catch {
        // 如果選課清單解析失敗，嘗試成績列表格式
      }

      // 回退到原有的成績查詢系統 HTML 格式
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      
      const tables = doc.querySelectorAll('table');
      let targetTable: Element | null = null;
      
      for (const table of tables) {
        if (table.textContent?.includes('課程名稱') && table.textContent?.includes('學分數')) {
          targetTable = table;
          break;
        }
      }
    
      if (!targetTable) {
        alert('找不到成績列表或選課清單，請確認上傳的檔案是否正確 (需包含歷年學業成績列表或選課清單)');
        return;
      }
    
      const rows = targetTable.querySelectorAll('tbody tr');
      const newCourses: { semesterId: string, course: Course }[] = [];
      let minYear = 999;
    
      rows.forEach((row: Element) => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 8) return;
        const semStr = cells[1].textContent?.trim() || ''; 
        if (semStr.length === 4) {
          const y = parseInt(semStr.substring(0, 3));
          if (y < minYear) minYear = y;
        }
      });
    
      if (minYear === 999) {
         minYear = 114; 
      }
    
      rows.forEach((row: Element) => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 8) return;
    
        const semStr = cells[1].textContent?.trim() || '';
        const code = cells[2].textContent?.trim() || '';
        const name = cells[3].textContent?.trim() || '';
        const creditsStr = cells[4].textContent?.trim() || '0';
        const grade = cells[5].textContent?.trim() || '';
        const dimensionStr = cells[7].textContent?.trim() || '';
    
        if (!semStr || !name) return;
    
        const y = parseInt(semStr.substring(0, 3));
        const s = parseInt(semStr.substring(3, 4));
        const gradeLevel = y - minYear + 1;
        const semesterId = `${gradeLevel}-${s}`;
    
        let category: CourseCategory = 'unclassified'; 
        let dimension: GenEdDimension = 'None';
    
        if (dimensionStr) {
            category = 'gen_ed';
            const dimChar = dimensionStr.charAt(0).toUpperCase();
            if (['A','B','C','D','E','F'].includes(dimChar)) {
                dimension = dimChar as GenEdDimension;
            }
        } else if (code.startsWith('PE') || name.includes('體育')) {
            category = 'pe';
        } else if (name.includes('國文') || name.includes('中文')) {
            category = 'chinese';
        } else if (name.includes('英文') || name.includes('English')) {
            category = 'english';
        } else if (name.includes('社會實踐')) {
            category = 'social';
        }
    
        // 修正：加入 isNaN 檢查，若解析失敗則預設為 0
        let credits = parseFloat(creditsStr);
        if (isNaN(credits)) credits = 0;

        const course: Course = {
            id: code || Date.now().toString() + Math.random(),
            name: name,
            credits: credits,
            category: category,
            program: 'home',
            dimension: dimension,
            grade: grade
        };
    
        newCourses.push({ semesterId, course });
      });
    
      if (newCourses.length === 0) {
          alert('未找到可匯入的課程資料');
          return;
      }

      setData(prev => {
          const newSemesters = prev.semesters.map(sem => {
              const coursesToAdd = newCourses
                .filter(nc => nc.semesterId === sem.id)
                .map(nc => nc.course);
              
              const existingNames = new Set(sem.courses.map(c => c.name));
              const uniqueCoursesToAdd = coursesToAdd.filter(c => !existingNames.has(c.name));
    
              return {
                  ...sem,
                  courses: [...sem.courses, ...uniqueCoursesToAdd]
              };
          });
          return { ...prev, semesters: newSemesters };
      });
      
      alert(`成功匯入 ${newCourses.length} 門課程！`);
    } catch (error) {
      console.error('匯入失敗:', error);
      alert('匯入失敗，請確認檔案格式是否正確');
    }
  };

  if (authLoading || (session && dataLoading)) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-50">載入中...</div>;
  }

  if (!session && !isDemoMode) {
    return <AuthPage onDemoLogin={() => setIsDemoMode(true)} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar 
        userEmail={session?.user?.email || "功能演示模式"}
        syncStatus={session ? syncStatus : 'idle'}
        isDemoMode={isDemoMode}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onImport={parseAndImportData}
        onOpenHelp={() => setIsOnboardingOpen(true)}
        onExitDemo={() => setIsDemoMode(false)}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          <Sidebar data={data} stats={stats} />

          <SemesterGrid 
            data={data} 
            onEdit={handleEdit} 
            onDelete={handleDelete} 
            onAdd={handleOpenAdd} 
            onOpenDetail={handleOpenDetail}
            onMoveCourse={handleMoveCourse}
            onSortByCategory={handleSortCoursesByCategory}
          />
        </div>
      </main>

      {isModalOpen && (
        <CourseModal
          key={editingCourse?.course.id ?? `new-${activeSemesterId}`}
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSave={handleSaveCourse}
          editingCourse={editingCourse ? editingCourse.course : null}
        />
      )}

      {isDetailOpen && detailCourse && (
        <CourseDetailModal
          isOpen={isDetailOpen}
          onClose={() => {
            setIsDetailOpen(false);
            setDetailCourse(null);
          }}
          course={detailCourse.course}
          semesterId={detailCourse.semesterId}
          onSave={handleSaveDetail}
        />
      )}

      {isSettingsOpen && (
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          onSave={handleSaveSettings}
          initialSettings={data.targets}
        />
      )}

      {isOnboardingOpen && (
        <OnboardingModal
          isOpen={isOnboardingOpen}
          onClose={handleCloseOnboarding}
        />
      )}
    </div>
  );
}
