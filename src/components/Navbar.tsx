import React from 'react';
import { GraduationCap, Settings, Upload, LogOut, CircleHelp } from 'lucide-react';
import { supabase } from '../supabase';

interface NavbarProps {
  userEmail: string;
  syncStatus: 'idle' | 'saving' | 'saved' | 'error';
  onOpenSettings: () => void;
  onImport: (html: string) => void;
  onReset: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ userEmail, syncStatus, onOpenSettings, onImport }) => {
  
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
  
    const reader = new FileReader();
    reader.onload = (event) => {
      const htmlContent = event.target?.result as string;
      onImport(htmlContent);
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleLogout = async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
    // onReset(); // 移除這行，不要觸發重置警告
    window.location.reload(); // 直接重新整理頁面，App 會自動回到登入畫面
  };

  return (
    <nav className="bg-white shadow-sm sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center gap-2">
            <GraduationCap className="w-8 h-8 text-blue-600" />
            <span className="text-xl font-bold text-gray-900">修課規劃助手</span>
            {syncStatus === 'saving' && <span className="text-xs text-gray-400 ml-2">儲存中...</span>}
            {syncStatus === 'saved' && <span className="text-xs text-green-500 ml-2">已儲存</span>}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600 hidden sm:block">{userEmail}</span>
            <button
              onClick={onOpenSettings}
              className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <Settings className="w-4 h-4" />
              <span className="hidden sm:inline">設定門檻</span>
            </button>
            <div className="flex items-center gap-1">
              <label className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors cursor-pointer">
                <Upload className="w-4 h-4" />
                <span className="hidden sm:inline">匯入成績</span>
                <input
                  type="file"
                  accept=".html"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
              <button
                onClick={() => alert('匯入說明：\n1. 前往臺科大成績查詢系統 (https://stuinfosys.ntust.edu.tw/StuScoreQueryServ/StuScoreQuery)\n2. 在頁面上點擊右鍵，選擇「另存新檔」或「網頁儲存為...」\n3. 下載 .html 檔案\n4. 點擊「匯入成績」按鈕並選擇該檔案即可匯入課程資料')}
                className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                title="匯入說明"
              >
                <CircleHelp className="w-5 h-5" />
              </button>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">登出</span>
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};
