import React, { useRef, useEffect, useState } from 'react';
import {
  PlaySquare,
  CheckCircle,
  Trash2,
  Clock,
  AlertCircle,
  Bell,
  XCircle,
  Zap,
  Plus,
  PauseCircle,
  Activity
} from 'lucide-react';
import { supabase } from './supabaseClient';
import { HEARTBEAT_INTERVAL_MS, HEARTBEAT_TIMEOUT_MS } from './workerStatus';
import { formatDateTime } from './format';

interface Log {
  id: number;
  time: string;
  type: string;
  message: string;
}

/** 依訊息內容判斷為加選日誌（含「加選」「已達最大嘗試」等） */
function isEnrollmentLog(message: string): boolean {
  const enrollmentKeywords = [
    '加選成功',
    '加選失敗',
    '加選延遲',
    '加選已完成',
    '停止加選',
    '無法加選',
    '已達最大嘗試次數',
    '自動加選'
  ];
  return enrollmentKeywords.some(k => message.includes(k));
}

// Only surface the heartbeat when it is late; a healthy worker pings every 60s.
const HEARTBEAT_STALE_WARN_MS = HEARTBEAT_INTERVAL_MS;

function formatIntervalSec(ms: number): string {
  const sec = ms / 1000;
  return Number.isInteger(sec) ? String(sec) : sec.toFixed(1);
}

function parseSchoolLatencyMs(message: string): number | null {
  const m = /延遲指標：學校系統\s*(\d+)ms/.exec(message);
  if (!m) return null;
  const value = Number(m[1]);
  return Number.isFinite(value) ? value : null;
}

interface DashboardCourse {
  id: string;
  course_code: string;
  course_name: string;
  status: string;
  current_enrolled: string;
  auto_enroll: boolean;
  last_check_time: string;
}

interface ProxyInfo {
  enabled: boolean;
  type: string;
  host: string;
  port: string;
}

interface DashboardViewProps {
  onNavigate?: (tab: string) => void;
  workerOnline: boolean;
}

const STATUS_POLL_INTERVAL_MS = 60_000;
const LOG_POLL_INTERVAL_MS = 10_000;
const MAX_LOG_ROWS = 200;
/** 超過此毫秒未收到心跳即凍結運行時間顯示 */
const UPTIME_FREEZE_AFTER_MS = HEARTBEAT_TIMEOUT_MS;

type LogTab = 'monitoring' | 'enrollment';

const DashboardView: React.FC<DashboardViewProps> = ({ onNavigate, workerOnline }) => {
  const logEndRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<Log[]>([]);
  const [logTab, setLogTab] = useState<LogTab>('monitoring');
  const [courses, setCourses] = useState<DashboardCourse[]>([]);
  const [stats, setStats] = useState({ monitoringCount: 0, successCount: 0 });
  const workerStatus = workerOnline ? 'Online' : 'Offline';
  const [workerOnlineSince, setWorkerOnlineSince] = useState<Date | null>(null);
  const [uptimeText, setUptimeText] = useState<string>('');
  const [proxyInfo, setProxyInfo] = useState<ProxyInfo | null>(null);
  const [backendLatencyMs, setBackendLatencyMs] = useState<number | null>(null);
  const [schoolLatencyMs, setSchoolLatencyMs] = useState<number | null>(null);
  const [checkIntervalMs, setCheckIntervalMs] = useState<number | null>(null);
  const [loginPause, setLoginPause] = useState<{ until: number; reason: string } | null>(null);
  // 1s clock so "上次檢查 N 秒前" keeps moving between course refreshes.
  const [nowMs, setNowMs] = useState<number>(() => Date.now());
  const currentUserIdRef = useRef<string | null>(null);
  /** 最後一次收到心跳的時間戳（毫秒） */
  const lastHeartbeatTimeRef = useRef<number>(0);
  const latestLogCreatedAtRef = useRef<string | null>(null);
  /** 防止 Realtime 心跳頻繁觸發 checkWorkerStatus 的節流標記 */
  const checkThrottleRef = useRef<boolean>(false);

  useEffect(() => {
    let logsChannel: ReturnType<typeof supabase.channel> | null = null;
    let coursesChannel: ReturnType<typeof supabase.channel> | null = null;
    let logPollInterval: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;
    (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user || cancelled) return;
      currentUserIdRef.current = user.id;

      fetchLogs();
      fetchStats();
      fetchCourses();

      logPollInterval = setInterval(() => {
        fetchNewLogs();
      }, LOG_POLL_INTERVAL_MS);

      logsChannel = supabase
        .channel(`dashboard_logs_${user.id}`)
        .on(
          'postgres_changes',
          {
            event: 'INSERT',
            schema: 'public',
            table: 'system_logs',
            filter: `user_id=eq.${user.id}`
          },
          (payload) => {
            const newLog = payload.new;
            const logTime = new Date(newLog.created_at);
            if (newLog.type === 'heartbeat') {
              lastHeartbeatTimeRef.current = Date.now();
              setBackendLatencyMs(0);
              const hbLatency = parseSchoolLatencyMs(newLog.message || '');
              if (hbLatency !== null) setSchoolLatencyMs(hbLatency);
              // 不直接設定 workerOnlineSince，改用 checkWorkerStatus 計算精確值
              if (!checkThrottleRef.current) {
                checkThrottleRef.current = true;
                checkWorkerStatus().finally(() => {
                  setTimeout(() => { checkThrottleRef.current = false; }, 10_000);
                });
              }
              return;
            }
            // 10 秒輪詢可能已先把同一筆放進來，避免重複（也避免 React key 重複）
            setLogs(prev => prev.some(l => l.id === newLog.id) ? prev : [...prev, {
              id: newLog.id,
              time: formatDateTime(logTime),
              type: newLog.type,
              message: newLog.message
            }].slice(-MAX_LOG_ROWS));
            latestLogCreatedAtRef.current = newLog.created_at;
            const parsed = parseSchoolLatencyMs(newLog.message || '');
            if (parsed !== null) setSchoolLatencyMs(parsed);
            if (!checkThrottleRef.current) {
              checkThrottleRef.current = true;
              checkWorkerStatus().finally(() => {
                setTimeout(() => { checkThrottleRef.current = false; }, 10_000);
              });
            }
          }
        )
        .subscribe();

      coursesChannel = supabase
        .channel(`dashboard_courses_${user.id}`)
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'monitored_courses',
            filter: `user_id=eq.${user.id}`
          },
          () => {
            fetchCourses();
            fetchStats();
          }
        )
        .subscribe();
    })();

    const statusInterval = setInterval(() => {
      checkWorkerStatus();
    }, STATUS_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (logsChannel) supabase.removeChannel(logsChannel);
      if (coursesChannel) supabase.removeChannel(coursesChannel);
      clearInterval(statusInterval);
      if (logPollInterval) clearInterval(logPollInterval);
    };
    // Mount-once subscription; fetch helpers below read refs, so re-running on their identity is unnecessary.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkWorkerStatus = async () => {
    const userId = currentUserIdRef.current;
    if (!userId) return;

    // 取最近 60 筆心跳，反向遍歷找到連續不中斷的最早一筆（= 本次上線起點）
    const { data } = await supabase
      .from('system_logs')
      .select('created_at, message')
      .eq('user_id', userId)
      .eq('type', 'heartbeat')
      .order('created_at', { ascending: false })
      .limit(60);

    if (!data || data.length === 0) {
      setWorkerOnlineSince(null);
      setBackendLatencyMs(null);
      return;
    }

    const latestTs = new Date(data[0].created_at).getTime();
    lastHeartbeatTimeRef.current = Math.max(lastHeartbeatTimeRef.current, latestTs);
    setBackendLatencyMs(Math.max(0, Date.now() - latestTs));
    // Worker embeds the latest school-API latency in the heartbeat message.
    const latestLatency = parseSchoolLatencyMs(data[0].message || '');
    if (latestLatency !== null) setSchoolLatencyMs(latestLatency);
    const isOnline = Date.now() - latestTs < HEARTBEAT_TIMEOUT_MS;

    if (!isOnline) {
      setWorkerOnlineSince(null);
      return;
    }

    // 從最新往前找，遇到相鄰心跳間隔 > timeout 就斷開，前一筆即為本次連線起始
    let onlineSinceTs = latestTs;
    for (let i = 0; i < data.length - 1; i++) {
      const curr = new Date(data[i].created_at).getTime();
      const prev = new Date(data[i + 1].created_at).getTime();
      if (curr - prev > HEARTBEAT_TIMEOUT_MS) break;   // 發現斷線間隙
      onlineSinceTs = prev;                // 這筆仍屬於同一連線階段
    }
    // 若搜完 60 筆都沒斷過，用最後一筆的時間（最早）
    if (data.length > 1) {
      const last = new Date(data[data.length - 1].created_at).getTime();
      const secondLast = new Date(data[data.length - 2].created_at).getTime();
      if (secondLast - last <= HEARTBEAT_TIMEOUT_MS) onlineSinceTs = Math.min(onlineSinceTs, last);
    }

    setWorkerOnlineSince(new Date(onlineSinceTs));
  };

  // 當 App 層判定離線時，清除 onlineSince；上線時立即查詢正確的起始時間
  useEffect(() => {
    if (!workerOnline) {
      setWorkerOnlineSince(null);
      lastHeartbeatTimeRef.current = 0;
    } else {
      // 上線後立即取得精確的 workerOnlineSince
      checkWorkerStatus();
    }
  }, [workerOnline]);

  // Uptime counter — ticks every second while worker is online
  // 若長時間未收到心跳，凍結計時器避免顯示不實的持續增長
  useEffect(() => {
    if (workerStatus !== 'Online' || !workerOnlineSince) {
      setUptimeText('');
      return;
    }
    const formatDiff = (totalSec: number) => {
      const d = Math.floor(totalSec / 86400);
      const h = Math.floor((totalSec % 86400) / 3600);
      const m = Math.floor((totalSec % 3600) / 60);
      const s = totalSec % 60;
      if (d > 0) return `${d}天 ${h}時 ${m}分`;
      if (h > 0) return `${h}時 ${m}分 ${s}秒`;
      if (m > 0) return `${m}分 ${s}秒`;
      return `${s}秒`;
    };
    const tick = () => {
      const now = Date.now();
      const lastHB = lastHeartbeatTimeRef.current;
      // 若超過 UPTIME_FREEZE_AFTER_MS 未收到心跳，凍結在最後心跳時間
      const endTime = (lastHB > 0 && now - lastHB > UPTIME_FREEZE_AFTER_MS)
        ? lastHB
        : now;
      const diff = Math.max(0, Math.floor((endTime - workerOnlineSince.getTime()) / 1000));
      setUptimeText(formatDiff(diff));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [workerStatus, workerOnlineSince]);

  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // Keep the heartbeat age display moving between realtime heartbeat inserts.
  useEffect(() => {
    if (workerStatus !== 'Online') {
      setBackendLatencyMs(null);
      return;
    }
    const tick = () => {
      const lastHB = lastHeartbeatTimeRef.current;
      setBackendLatencyMs(lastHB > 0 ? Math.max(0, Date.now() - lastHB) : null);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [workerStatus]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const fetchLogs = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    const { data } = await supabase
      .from('system_logs')
      .select('*')
      .eq('user_id', user.id)
      .neq('type', 'heartbeat')
      .order('created_at', { ascending: false })
      .limit(MAX_LOG_ROWS);
    if (data) {
      const latestLatencyLog = data.find(log => parseSchoolLatencyMs(log.message || '') !== null);
      if (latestLatencyLog) {
        const parsed = parseSchoolLatencyMs(latestLatencyLog.message || '');
        if (parsed !== null) setSchoolLatencyMs(parsed);
      }
      const ordered = data.reverse();
      latestLogCreatedAtRef.current = ordered.length > 0
        ? ordered[ordered.length - 1].created_at
        : null;
      setLogs(ordered.map(log => ({
        id: log.id,
        time: formatDateTime(log.created_at),
        type: log.type,
        message: log.message
      })));
      checkWorkerStatus();
    }
  };

  const fetchNewLogs = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const latestCreatedAt = latestLogCreatedAtRef.current;
    if (!latestCreatedAt) {
      await fetchLogs();
      return;
    }

    const { data } = await supabase
      .from('system_logs')
      .select('*')
      .eq('user_id', user.id)
      .neq('type', 'heartbeat')
      .gt('created_at', latestCreatedAt)
      .order('created_at', { ascending: true })
      .limit(MAX_LOG_ROWS);

    if (!data || data.length === 0) return;

    latestLogCreatedAtRef.current = data[data.length - 1].created_at;
    const latestLatencyLog = [...data].reverse().find(log => parseSchoolLatencyMs(log.message || '') !== null);
    if (latestLatencyLog) {
      const parsed = parseSchoolLatencyMs(latestLatencyLog.message || '');
      if (parsed !== null) setSchoolLatencyMs(parsed);
    }

    setLogs(prev => {
      const seen = new Set(prev.map(log => log.id));
      const incoming = data
        .filter(log => !seen.has(log.id))
        .map(log => ({
          id: log.id,
          time: formatDateTime(log.created_at),
          type: log.type,
          message: log.message
        }));
      if (incoming.length === 0) return prev;
      return [...prev, ...incoming].slice(-MAX_LOG_ROWS);
    });
    checkWorkerStatus();
  };

  const fetchCourses = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    const { data } = await supabase
      .from('monitored_courses')
      .select('id, course_code, course_name, status, current_enrolled, auto_enroll, last_check_time')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false });
    if (data) setCourses(data);
  };

  const fetchStats = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { count: monitoringCount } = await supabase
      .from('monitored_courses')
      .select('*', { count: 'exact', head: true })
      .eq('user_id', user.id)
      .eq('status', 'monitoring');

    const { count: successCount } = await supabase
      .from('monitored_courses')
      .select('*', { count: 'exact', head: true })
      .eq('user_id', user.id)
      .eq('status', 'enrolled');

    setStats({
      monitoringCount: monitoringCount || 0,
      successCount: successCount || 0
    });

    const { data } = await supabase
      .from('user_settings')
      .select('check_interval, proxy_enabled, proxy_type, proxy_host, proxy_port, login_paused_until, login_pause_reason')
      .eq('user_id', user.id)
      .single();
    if (data) {
      const intervalMs = data.check_interval ?? 30000;
      setCheckIntervalMs(intervalMs);
      setProxyInfo({
        enabled: data.proxy_enabled ?? false,
        type: data.proxy_type ?? 'socks5',
        host: data.proxy_host ?? '',
        port: data.proxy_port ?? '',
      });
      const pausedUntil = data.login_paused_until ? new Date(data.login_paused_until).getTime() : 0;
      setLoginPause(pausedUntil > Date.now() ? { until: pausedUntil, reason: data.login_pause_reason ?? '' } : null);
    }
  };

  const handleClearLogs = async () => {
    if (!confirm('確定要清除所有日誌嗎？此操作無法復原。')) return;
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      // 僅刪除非 heartbeat 的日誌，保留 heartbeat 以免前端誤判 Worker 離線
      const { error } = await supabase
        .from('system_logs')
        .delete()
        .eq('user_id', user.id)
        .neq('type', 'heartbeat');
      if (error) throw error;
      setLogs([]);
      await supabase.from('system_logs').insert({
        user_id: user.id,
        type: 'info',
        message: '日誌已由使用者手動清除',
        created_at: new Date().toISOString()
      });
    } catch (error) {
      console.error('Error clearing logs:', error);
      alert('清除日誌失敗');
    }
  };

  const toggleAutoAdd = async (id: string, current: boolean) => {
    try {
      const { error } = await supabase
        .from('monitored_courses')
        .update({ auto_enroll: !current })
        .eq('id', id);
      if (error) throw error;
      fetchCourses();
    } catch (error) {
      console.error('Error toggling auto-add:', error);
    }
  };

  const togglePause = async (course: DashboardCourse) => {
    try {
      const newStatus = course.status === 'paused' ? 'monitoring' : 'paused';
      const { error } = await supabase
        .from('monitored_courses')
        .update({ status: newStatus })
        .eq('id', course.id);
      if (error) throw error;
      fetchCourses();
      fetchStats();
    } catch (error) {
      console.error('Error toggling pause:', error);
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
      fetchStats();
    } catch (error) {
      console.error('Error deleting course:', error);
    }
  };

  const getLogIcon = (type: string) => {
    switch (type) {
      case 'success': return <CheckCircle size={16} className="text-green-500 mt-0.5" />;
      case 'error': return <XCircle size={16} className="text-red-500 mt-0.5" />;
      case 'warning':
      case 'warn': return <AlertCircle size={16} className="text-amber-500 mt-0.5" />;
      default: return <Bell size={16} className="text-blue-500 mt-0.5" />;
    }
  };

  // Newest last_check_time across monitored courses, as seconds ago.
  const latestCheckMs = courses.reduce((max, course) => {
    const ts = course.last_check_time ? new Date(course.last_check_time).getTime() : 0;
    return Number.isFinite(ts) && ts > max ? ts : max;
  }, 0);
  const lastCheckAgoSec = latestCheckMs > 0 ? Math.max(0, Math.floor((nowMs - latestCheckMs) / 1000)) : null;

  return (
    <>
      {/* Header — matches reference */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-slate-800">歡迎回來，同學</h2>
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold shadow-sm border ${
              workerStatus === 'Online'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-red-50 text-red-600 border-red-200'
            }`}>
              <span className={`relative flex h-2 w-2`}>
                {workerStatus === 'Online' && (
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                )}
                <span className={`relative inline-flex rounded-full h-2 w-2 ${
                  workerStatus === 'Online' ? 'bg-emerald-500' : 'bg-red-400'
                }`}></span>
              </span>
              {workerStatus === 'Online' ? 'Worker 運行中' : 'Worker 離線'}
            </span>
          </div>
          <p className="text-slate-500 text-sm mt-1">
            {workerStatus === 'Online' && uptimeText
              ? `已持續運行 ${uptimeText}，目前有 ${stats.monitoringCount} 門課程正在監控中。`
              : workerStatus === 'Offline'
                ? `⚠ 伺服器已中斷，${stats.monitoringCount} 門課程暫停監控。`
                : `目前有 ${stats.monitoringCount} 門課程正在監控中。`
            }
          </p>
        </div>
        <button
          onClick={() => onNavigate?.('courses')}
          className="flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
        >
          <Plus size={18} className="mr-2" />
          新增監聽課程
        </button>
      </header>

      {loginPause && loginPause.until > nowMs && (
        <div className="mb-6 flex items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-900">
          <AlertCircle size={20} className="mt-0.5 shrink-0 text-amber-600" />
          <div className="text-sm">
            <p className="font-semibold">已暫停自動登入，帳號可能被鎖定或密碼有誤</p>
            <p className="mt-1">
              連續登入失敗達上限，Worker 已暫停自動登入約 {Math.max(1, Math.ceil((loginPause.until - nowMs) / 60000))} 分鐘（至 {new Date(loginPause.until).toLocaleTimeString()}）以保護帳號。
              請先用瀏覽器登入 <a className="underline" href="https://courseselection.ntust.edu.tw" target="_blank" rel="noreferrer">選課系統</a> 確認帳密與 SSO 是否正常，必要時到「設定」更新校務密碼。
            </p>
            {loginPause.reason && <p className="mt-1 text-xs text-amber-700">最後錯誤：{loginPause.reason}</p>}
          </div>
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center">
          <div className="w-14 h-14 rounded-xl bg-blue-50 flex items-center justify-center mr-4">
            <PlaySquare className="text-blue-500" size={24} />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">監聽中課程</p>
            <p className="text-2xl font-bold text-slate-800 mt-1">{stats.monitoringCount}</p>
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center">
          <div className="w-14 h-14 rounded-xl bg-green-50 flex items-center justify-center mr-4">
            <CheckCircle className="text-green-500" size={24} />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">成功搶課次數</p>
            <p className="text-2xl font-bold text-slate-800 mt-1">{stats.successCount}</p>
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center">
          <div className="w-14 h-14 rounded-xl bg-purple-50 flex items-center justify-center mr-4">
            <Activity className="text-purple-500" size={24} />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">代理伺服器</p>
            {proxyInfo === null ? (
              <p className="text-lg font-bold text-slate-400 mt-1">—</p>
            ) : proxyInfo.enabled ? (
              <p className="text-sm font-bold text-purple-600 mt-1 font-mono truncate max-w-[180px]" title={`${proxyInfo.type.toUpperCase()} ${proxyInfo.host}:${proxyInfo.port}`}>
                {proxyInfo.type.toUpperCase()} {proxyInfo.host}:{proxyInfo.port}
              </p>
            ) : (
              <p className="text-lg font-bold text-slate-400 mt-1">直接連線</p>
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex items-center">
          <div className="w-14 h-14 rounded-xl bg-amber-50 flex items-center justify-center mr-4">
            <Clock className="text-amber-500" size={24} />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">監控狀態</p>
            <p className="text-xs text-slate-600 mt-1">
              學校查詢: {schoolLatencyMs !== null ? `${schoolLatencyMs} ms` : '—'}
            </p>
            <p className="text-xs text-slate-600 mt-0.5">
              檢查週期: {checkIntervalMs !== null ? `每 ${formatIntervalSec(checkIntervalMs)} 秒` : '—'}
              {lastCheckAgoSec !== null ? `，上次 ${lastCheckAgoSec} 秒前` : '，尚未檢查'}
            </p>
            {backendLatencyMs !== null && backendLatencyMs > HEARTBEAT_STALE_WARN_MS && (
              <p className="text-xs text-amber-600 mt-0.5">
                心跳延遲 {Math.floor(backendLatencyMs / 1000)} 秒
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Two-column: Courses + Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Course List */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <h3 className="font-semibold text-slate-800">監聽列表</h3>
            <span className="text-xs text-slate-500 bg-white px-2 py-1 rounded border border-slate-200 shadow-sm">
              {workerStatus === 'Online' ? '即時更新中' : '等待連線'}
            </span>
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
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-slate-800 text-lg">{course.course_name}</h4>
                        <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded font-mono">{course.course_code}</span>
                      </div>
                      <div className="flex items-center mt-2 text-xs text-slate-400">
                        <Clock size={12} className="mr-1" /> 最後檢查: {course.last_check_time ? formatDateTime(course.last_check_time) : '尚未檢查'}
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

                    {/* Capacity */}
                    <div className="text-center px-2">
                      <p className="text-xs text-slate-500 mb-1">目前人數</p>
                      <p className={`font-semibold ${isAvailable ? 'text-green-600' : 'text-slate-700'}`}>
                        {course.current_enrolled || '---'}
                      </p>
                    </div>

                    {/* Pause / Delete */}
                    <div className="flex gap-1 sm:gap-2 pl-2">
                      {isMonitoring || isPaused ? (
                        <button
                          onClick={() => togglePause(course)}
                          title={isMonitoring ? '暫停監聽' : '開始監聽'}
                          className={`p-2 rounded-lg transition-colors ${
                            isMonitoring
                              ? 'text-slate-400 hover:text-amber-500 hover:bg-amber-50'
                              : 'text-slate-400 hover:text-blue-500 hover:bg-blue-50'
                          }`}
                        >
                          {isMonitoring ? <PauseCircle size={20} /> : <PlaySquare size={20} />}
                        </button>
                      ) : (
                        <button disabled className="p-2 text-slate-200 cursor-not-allowed">
                          <PauseCircle size={20} />
                        </button>
                      )}
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
              <div className="p-12 text-center text-slate-400">
                <PlaySquare className="mx-auto text-slate-300 mb-3" size={36} />
                <p className="text-sm font-medium">尚未新增監聽課程</p>
                <p className="text-xs text-slate-400 mt-1">點擊右上角「新增監聽課程」開始使用</p>
              </div>
            )}
          </div>
        </div>

        {/* Logs */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden flex flex-col h-[400px]">
          <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setLogTab('monitoring')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  logTab === 'monitoring'
                    ? 'bg-blue-100 text-blue-700 border border-blue-200'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                監聽日誌
              </button>
              <button
                onClick={() => setLogTab('enrollment')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  logTab === 'enrollment'
                    ? 'bg-blue-100 text-blue-700 border border-blue-200'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                加選日誌
              </button>
            </div>
            {logs.length > 0 && (
              <button
                onClick={handleClearLogs}
                className="text-xs flex items-center gap-1.5 text-slate-500 hover:text-red-500 transition-colors px-2 py-1 rounded-md hover:bg-red-50"
              >
                <Trash2 size={14} />
                清除
              </button>
            )}
          </div>
          <div className="p-6 flex-1 overflow-y-auto space-y-4">
            {(() => {
              const filtered = logTab === 'enrollment' ? logs.filter(l => isEnrollmentLog(l.message)) : logs.filter(l => !isEnrollmentLog(l.message));
              return filtered.length > 0 ? filtered.map(log => (
              <div key={log.id} className="flex items-start gap-3 text-sm animate-fadeIn">
                <div className="shrink-0">{getLogIcon(log.type)}</div>
                <div>
                  <p className={`text-slate-700 ${log.type === 'success' ? 'font-medium' : ''}`}>
                    {log.message}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">{log.time}</p>
                </div>
              </div>
            )) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-3 opacity-80">
                <CheckCircle size={36} className="text-slate-300" />
                <p className="text-sm font-medium">{logTab === 'enrollment' ? '目前沒有加選日誌' : '目前沒有監聽日誌'}</p>
              </div>
            );
            })()}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </>
  );
};

export default DashboardView;
