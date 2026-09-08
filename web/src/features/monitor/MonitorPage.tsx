import React, { useCallback, useEffect, useState } from 'react';
import { Activity, BookOpen, Loader2, Settings } from 'lucide-react';
import { supabase } from './supabaseClient';
import { HEARTBEAT_TIMEOUT_MS } from './workerStatus';
import DashboardView from './DashboardView';
import CoursesView from './CoursesView';
import MonitorSettingsView from './MonitorSettingsView';
import ProxyView from './ProxyView';

type MonitorTab = 'dashboard' | 'courses' | 'settings';

const tabs: Array<{ id: MonitorTab; icon: React.ComponentType<{ size?: number }>; label: string }> = [
  { id: 'dashboard', icon: Activity, label: '儀表板' },
  { id: 'courses', icon: BookOpen, label: '課程管理' },
  { id: 'settings', icon: Settings, label: '監控設定' },
];

/** 全域 Worker 存活偵測間隔（毫秒） */
const WORKER_POLL_MS = 10_000;

interface HeartbeatRow {
  type?: string;
}

/** Worker 存活偵測：輪詢最新心跳 + Realtime 心跳訂閱（原 NTUST_Course_Monitor App.tsx） */
function useWorkerOnline(): boolean | null {
  // null = 尚未查過（避免進頁後先閃「伺服器已中斷」）
  const [workerOnline, setWorkerOnline] = useState<boolean | null>(null);

  const checkWorkerAlive = useCallback(async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data } = await supabase
      .from('system_logs')
      .select('created_at')
      .eq('user_id', user.id)
      .eq('type', 'heartbeat')
      .order('created_at', { ascending: false })
      .limit(1);

    if (!data || data.length === 0) {
      setWorkerOnline(false);
      return;
    }
    const age = Date.now() - new Date(data[0].created_at).getTime();
    setWorkerOnline(age < HEARTBEAT_TIMEOUT_MS);
  }, []);

  useEffect(() => {
    // 首次立即檢查（以微任務排程，避免在 effect 內同步 setState）
    void Promise.resolve().then(checkWorkerAlive);
    const intervalId = setInterval(() => { void checkWorkerAlive(); }, WORKER_POLL_MS);

    // Realtime: 只訂閱本用戶 system_logs，避免跨使用者干擾
    let channel: ReturnType<typeof supabase.channel> | null = null;
    let cancelled = false;
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (cancelled || !user) return;
      channel = supabase
        .channel(`app_heartbeat_${user.id}`)
        .on(
          'postgres_changes',
          {
            event: 'INSERT',
            schema: 'public',
            table: 'system_logs',
            filter: `user_id=eq.${user.id}`,
          },
          (payload) => {
            if ((payload.new as HeartbeatRow)?.type === 'heartbeat') {
              setWorkerOnline(true);
            }
          },
        )
        .subscribe();
    })();

    return () => {
      cancelled = true;
      clearInterval(intervalId);
      if (channel) supabase.removeChannel(channel);
    };
  }, [checkWorkerAlive]);

  return workerOnline;
}

/** 監聽引擎開關（user_settings.is_active，原 Sidebar.tsx） */
const EngineToggle: React.FC<{ workerOnline: boolean | null }> = ({ workerOnline }) => {
  const [isActive, setIsActive] = useState(false);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    const fetchStatus = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase
        .from('user_settings')
        .select('is_active')
        .eq('user_id', user.id)
        .single();
      if (data) setIsActive(data.is_active ?? false);
    };
    void fetchStatus();

    const channel = supabase
      .channel('sidebar_settings')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'user_settings' }, () => {
        void fetchStatus();
      })
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, []);

  const handleToggle = async () => {
    setToggling(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const newValue = !isActive;
      const { error } = await supabase
        .from('user_settings')
        .upsert({ user_id: user.id, is_active: newValue, updated_at: new Date().toISOString() });
      if (error) throw error;
      setIsActive(newValue);
    } catch {
      // Dashboard will show the error
    } finally {
      setToggling(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Worker 離線警告 */}
      {isActive && workerOnline === false && (
        <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 flex items-center">
          <div className="w-2 h-2 rounded-full mr-2 bg-red-400" />
          <span className="text-xs font-medium text-red-600">伺服器已中斷</span>
        </div>
      )}
      <button
        onClick={() => { void handleToggle(); }}
        disabled={toggling}
        className={`px-3 py-2.5 rounded-lg flex items-center gap-3 transition-colors ${
          isActive && workerOnline ? 'bg-green-50' : isActive ? 'bg-amber-50' : 'bg-slate-50'
        } disabled:opacity-60`}
      >
        <div className="flex items-center">
          {toggling ? (
            <Loader2 size={12} className="text-slate-400 mr-2 animate-spin" />
          ) : (
            <div className={`w-2 h-2 rounded-full mr-2 ${
              isActive && workerOnline ? 'bg-green-500 animate-pulse' :
              isActive ? 'bg-amber-400' : 'bg-slate-300'
            }`} />
          )}
          <span className={`text-sm font-medium ${
            isActive && workerOnline ? 'text-green-700' :
            isActive ? 'text-amber-600' : 'text-slate-500'
          }`}>
            {isActive && workerOnline ? '監聽引擎運行中' :
             isActive && workerOnline === null ? '確認伺服器狀態…' :
             isActive ? '等待伺服器連線' : '監聽引擎已關閉'}
          </span>
        </div>
        <span className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${
          isActive && workerOnline ? 'bg-green-500' : isActive ? 'bg-amber-400' : 'bg-slate-300'
        }`}>
          <span className={`inline-block h-3 w-3 transform rounded-full bg-white shadow transition-transform ${isActive ? 'translate-x-3' : 'translate-x-0.5'}`} />
        </span>
      </button>
    </div>
  );
};

const WorkerBadge: React.FC<{ workerOnline: boolean | null }> = ({ workerOnline }) => (
  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
    workerOnline === true
      ? 'bg-green-50 text-green-700 border-green-200'
      : workerOnline === false
        ? 'bg-red-50 text-red-600 border-red-200'
        : 'bg-slate-50 text-slate-500 border-slate-200'
  }`}>
    <span className={`w-2 h-2 rounded-full ${
      workerOnline === true ? 'bg-green-500 animate-pulse' : workerOnline === false ? 'bg-red-400' : 'bg-slate-300'
    }`} />
    {workerOnline === true ? 'Worker 上線' : workerOnline === false ? 'Worker 離線' : 'Worker 狀態確認中'}
  </span>
);

export const MonitorPage: React.FC<{ onGoToCourseSearch?: () => void }> = ({ onGoToCourseSearch }) => {
  const [activeTab, setActiveTab] = useState<MonitorTab>('dashboard');
  const workerOnline = useWorkerOnline();

  return (
    <div className="space-y-4">
      {/* 與課程查詢／修課軌跡同一套：白卡片 + 藍色 eyebrow + text-2xl 標題 */}
      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 p-5 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">選課監控</p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold text-slate-950">名額監聽與自動加選</h1>
              <WorkerBadge workerOnline={workerOnline} />
            </div>
            <p className="mt-1 text-sm text-slate-500">監控課程名額並在釋出時自動加選。Worker 在本機電腦執行，需保持開機。</p>
          </div>
          <EngineToggle workerOnline={workerOnline} />
        </div>

        <div className="border-t border-slate-100 px-5">
          <div className="flex gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              aria-pressed={activeTab === tab.id}
              className={`flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
          </div>
        </div>
      </section>

      {activeTab === 'dashboard' && <DashboardView workerOnline={workerOnline === true} onGoToCourseSearch={onGoToCourseSearch} />}
      {activeTab === 'courses' && <CoursesView onGoToCourseSearch={onGoToCourseSearch} />}
      {activeTab === 'settings' && (
        <div className="space-y-4">
          <MonitorSettingsView />
          <ProxyView />
        </div>
      )}
    </div>
  );
};

export default MonitorPage;
