import React from 'react';
import { GraduationCap, LogOut, CircleHelp, BookOpen } from 'lucide-react';
import { supabase } from '../shared/supabase';

export type AppPage = 'course-search' | 'planning' | 'history' | 'settings';

interface NavbarProps {
  userEmail: string;
  syncStatus: 'idle' | 'saving' | 'saved' | 'error';
  isDemoMode: boolean;
  activePage: AppPage;
  pendingCount: number;
  onPageChange: (page: AppPage) => void;
  onOpenHelp: () => void;
  onExitDemo: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  userEmail,
  syncStatus,
  isDemoMode,
  activePage,
  pendingCount,
  onPageChange,
  onOpenHelp,
  onExitDemo,
}) => {
  const handleLogout = async () => {
    if (isDemoMode || !supabase) {
      onExitDemo();
      return;
    }

    await supabase.auth.signOut();
    window.location.reload();
  };

  const navItems: Array<{ page: AppPage; label: string }> = [
    { page: 'course-search', label: '課程查詢' },
    { page: 'planning', label: `選課工作台 ${pendingCount}` },
    { page: 'history', label: '修課軌跡 / 畢業進度' },
    { page: 'settings', label: '設定' },
  ];

  const syncText = syncStatus === 'saving'
    ? '同步中...'
    : syncStatus === 'saved'
      ? '資料已同步'
      : syncStatus === 'error'
        ? '同步失敗'
        : '資料同步';

  return (
    <nav
      className="sticky top-0 z-40 border-b border-slate-200 bg-white shadow-sm"
      style={{ paddingTop: 'env(safe-area-inset-top)' }}
    >
      <div className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 py-3 xl:h-16 xl:flex-row xl:items-center xl:justify-between xl:py-0">
          <div className="flex min-w-0 items-center gap-3 xl:w-[260px]">
            <GraduationCap className="h-8 w-8 flex-shrink-0 text-blue-600" />
            <div className="min-w-0">
              <span className="block truncate text-xl font-bold text-gray-900">修課羅盤</span>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>Course Compass</span>
                {isDemoMode && <span className="text-amber-600">略過登入模式</span>}
              </div>
            </div>
          </div>

          <div className="overflow-x-auto xl:flex-1">
            <div className="flex min-w-max items-center gap-5 text-sm font-medium">
              {navItems.map((item) => (
                <button
                  key={item.page}
                  onClick={() => onPageChange(item.page)}
                  className={`border-b-2 px-1 py-5 ${
                    activePage === item.page ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 xl:flex-nowrap xl:justify-end">
            <div className={`hidden text-xs xl:block ${syncStatus === 'error' ? 'text-red-600' : syncStatus === 'saved' ? 'text-emerald-600' : 'text-slate-500'}`}>
              {syncText}
            </div>
            <div className="grid grid-cols-3 items-center gap-1 sm:flex sm:w-auto">
              <button
                onClick={() => alert('平台分成課程查詢、選課工作台、修課軌跡與設定。修課軌跡整合歷史修課、未來規劃與畢業進度；選課工作台只輔助目前選課學期，不會自動搶課。')}
                className="flex items-center justify-center rounded-lg p-2 text-gray-500 transition-colors hover:bg-blue-50 hover:text-blue-600"
                title="匯入說明"
              >
                <CircleHelp className="h-5 w-5" />
              </button>

              <button
                onClick={onOpenHelp}
                className="flex items-center justify-center rounded-lg p-2 text-gray-500 transition-colors hover:bg-blue-50 hover:text-blue-600"
                title="功能導覽"
              >
                <BookOpen className="h-5 w-5" />
              </button>

              <button
                onClick={handleLogout}
                className="flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-red-600 transition-colors hover:bg-red-50"
                title={isDemoMode ? '離開略過登入模式' : '登出'}
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden md:inline">{isDemoMode ? '離開略過登入' : '登出'}</span>
              </button>
            </div>
            <div className="min-w-0 text-right text-xs text-slate-500">
              <span className="block max-w-[180px] truncate">{userEmail}</span>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
};
