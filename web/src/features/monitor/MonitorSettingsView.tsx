import ClampedNumberInput from './ClampedNumberInput';
import React, { useState, useEffect } from 'react';
import { Activity, Bell, Save, Loader2, Mail, Clock } from 'lucide-react';
import { supabase } from './supabaseClient';

type EnrollmentPeriod = 'A06' | 'B01';

interface MonitorSettings {
  line_notify_token: string;
  check_interval: number;
  random_interval: number;
  is_active: boolean;
  verify_ssl: boolean;
  email_notify: boolean;
  resend_api_key: string;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password: string;
  enrollment_open_start: string;
  enrollment_open_end: string;
  enrollment_period: EnrollmentPeriod;
}

/** Row written to user_settings; secret fields are optional so untouched encrypted values are not overwritten. */
type MonitorSettingsPayload = Partial<MonitorSettings> & { is_encrypted?: boolean };

const MonitorSettingsView: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testEmailSending, setTestEmailSending] = useState(false);
  const [isEncrypted, setIsEncrypted] = useState(false);
  const [settings, setSettings] = useState<MonitorSettings>({
    line_notify_token: '',
    check_interval: 1500,
    random_interval: 5,
    is_active: false,
    verify_ssl: true,
    email_notify: false,
    resend_api_key: '',
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    enrollment_open_start: '',
    enrollment_open_end: '',
    enrollment_period: 'A06'  // A06=電腦抽選後選課, B01=加退選課
  });

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data, error } = await supabase
        .from('user_settings')
        .select('*')
        .eq('user_id', user.id)
        .single();
      if (error && error.code !== 'PGRST116') {
        console.error('Error fetching settings:', error);
      }
      if (data) {
        setIsEncrypted(data.is_encrypted || false);
        setSettings({
          line_notify_token: data.line_notify_token || '',
          check_interval: data.check_interval || 1500,
          random_interval: data.random_interval ?? 5,
          is_active: data.is_active || false,
          verify_ssl: data.verify_ssl !== false,
          email_notify: data.email_notify ?? false,
          resend_api_key: data.is_encrypted && data.resend_api_key ? '' : (data.resend_api_key || ''),
          smtp_host: data.smtp_host || 'smtp.gmail.com',
          smtp_port: data.smtp_port ?? 587,
          smtp_username: data.smtp_username || '',
          smtp_password: data.is_encrypted && data.smtp_password ? '' : (data.smtp_password || ''),
          enrollment_open_start: data.enrollment_open_start || '',
          enrollment_open_end: data.enrollment_open_end || '',
          enrollment_period: (data.enrollment_period === 'B01' ? 'B01' : 'A06')
        });
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSendTestEmail = async () => {
    setTestEmailSending(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user?.email) {
        alert('無法取得您的登入信箱，請重新登入後再試。');
        return;
      }
      const { error } = await supabase
        .from('email_test_requests')
        .insert({ user_id: user.id, email: user.email });
      if (error) throw error;
      alert('已送出測試信請求，請稍候至信箱查收（約 1 分鐘內）。後端 Worker 需在運行中且已設定 Resend API Key 或 SMTP 才會發送。');
    } catch (e) {
      console.error('Send test email error:', e);
      alert('送出失敗，請稍後再試。');
    } finally {
      setTestEmailSending(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // 準備要儲存的資料（學號／選課密碼由 Compass 設定頁的校務帳密管理，這裡不觸碰）
      const payload: MonitorSettingsPayload = { ...settings };

      // 如果是已加密狀態，且密碼欄位為空，則不更新這些欄位（避免覆蓋掉原本的加密資料）
      if (isEncrypted) {
        if (payload.resend_api_key === '') delete payload.resend_api_key;
        if (payload.smtp_password === '') delete payload.smtp_password;
        if (payload.line_notify_token === '') delete payload.line_notify_token;
      }

      // 如果使用者有輸入新的 Resend Key 或 SMTP 密碼，則將 is_encrypted 設為 false，讓後端重新加密。
      // line_notify_token 後端不加密，不應觸發此旗標。
      if (
        (payload.resend_api_key && payload.resend_api_key !== '') ||
        (payload.smtp_password && payload.smtp_password !== '')
      ) {
        payload.is_encrypted = false;
      }

      const { error } = await supabase
        .from('user_settings')
        .upsert({
          user_id: user.id,
          ...payload,
          updated_at: new Date().toISOString()
        });
      if (error) throw error;
      
      // 儲存成功後，重新抓取設定以更新 UI 狀態
      await fetchSettings();
      alert('設定已儲存');
    } catch (error) {
      console.error('Error saving settings:', error);
      alert('儲存失敗');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <section id="monitor-settings" className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          載入監控設定…
        </div>
      </section>
    );
  }

  const toggleClass = (on: boolean) =>
    `relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${on ? 'bg-blue-600' : 'bg-slate-200'}`;
  const knobClass = (on: boolean) =>
    `pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform duration-200 ease-in-out ${on ? 'translate-x-5' : 'translate-x-0'}`;
  const inputClass =
    'w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 transition-colors focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500';

  return (
    <section id="monitor-settings" className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-blue-600" />
            <h2 className="text-base font-semibold text-slate-900">選課監控與通知</h2>
          </div>
          <p className="mt-2 text-sm text-slate-500">
            監聽節奏、選課時段與通知方式；監聽哪幾門課在「選課監控」頁管理。
          </p>
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center justify-center gap-2 self-start whitespace-nowrap rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          儲存監控設定
        </button>
      </div>

      <div className="divide-y divide-slate-100">
        {/* 監聽節奏 */}
        <div className="space-y-5 p-5">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-sm font-medium text-slate-700">基本監控間隔</label>
              <span className="rounded bg-blue-50 px-2 py-0.5 font-mono text-xs text-blue-600">
                {settings.check_interval >= 1000
                  ? `${(settings.check_interval / 1000).toFixed(1)}s`
                  : `${settings.check_interval}ms`}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="500"
                max="60000"
                step="500"
                value={Math.min(settings.check_interval, 60000)}
                onChange={(e) => setSettings({ ...settings, check_interval: parseInt(e.target.value) })}
                className="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-slate-200 accent-blue-500"
              />
              <div className="flex items-center gap-1.5">
                <ClampedNumberInput
                  min={500}
                  max={60000}
                  step={500}
                  value={settings.check_interval}
                  onCommit={(v) => setSettings({ ...settings, check_interval: v })}
                  className="w-20 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-center font-mono text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="whitespace-nowrap text-xs text-slate-400">ms</span>
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-500">每次向選課系統發送請求的基礎等待時間（建議偵測用 5000–30000ms）</p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">隨機間隔範圍（秒）</label>
              <div className="flex items-center gap-2">
                <ClampedNumberInput
                  min={0}
                  max={60}
                  value={settings.random_interval}
                  onCommit={(v) => setSettings({ ...settings, random_interval: v })}
                  className="w-20 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-center text-sm text-slate-800 transition-colors focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="whitespace-nowrap text-sm text-slate-400">秒</span>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                防止被系統識別為機器人，實際間隔會加上此隨機值（例如 {(settings.check_interval / 1000).toFixed(0)} ± {settings.random_interval} 秒）。設為 0 表示不加隨機。
              </p>
            </div>

            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-sm font-medium text-slate-700">SSL 憑證驗證</h3>
                <p className="mt-1 text-xs text-slate-500">關閉可忽略憑證錯誤。學校伺服器憑證過期導致抓取失敗時再關。</p>
              </div>
              <button
                type="button"
                aria-pressed={settings.verify_ssl}
                onClick={() => setSettings({ ...settings, verify_ssl: !settings.verify_ssl })}
                className={toggleClass(settings.verify_ssl)}
              >
                <span className={knobClass(settings.verify_ssl)} />
              </button>
            </div>
          </div>
        </div>

        {/* 選課時段：決定自動加選走 A06 或 B01 流程 */}
        <div className="space-y-5 p-5">
          <div>
            <h3 className="text-sm font-medium text-slate-700">當前選課時段</h3>
            <p className="mt-1 text-xs text-slate-500">自動加選會依此送出對應流程，請依學校公告的開放時段選擇。</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setSettings({ ...settings, enrollment_period: 'A06' })}
                className={`whitespace-nowrap rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
                  settings.enrollment_period === 'A06'
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                電腦抽選後選課（A06）
              </button>
              <button
                type="button"
                onClick={() => setSettings({ ...settings, enrollment_period: 'B01' })}
                className={`whitespace-nowrap rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
                  settings.enrollment_period === 'B01'
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                加退選課（B01）
              </button>
            </div>
          </div>

          <div>
            <h3 className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <Clock className="h-4 w-4 text-slate-400" />
              選課開放時間（台灣時間，含日期）
            </h3>
            <p className="mt-1 text-xs text-slate-500">僅在此範圍內送出加選請求；兩欄都留空表示不限制，可減少非開放時段的請求。</p>
            <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">開始日期時間</label>
                <input
                  type="datetime-local"
                  value={settings.enrollment_open_start}
                  onChange={(e) => setSettings({ ...settings, enrollment_open_start: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">結束日期時間</label>
                <input
                  type="datetime-local"
                  value={settings.enrollment_open_end}
                  onChange={(e) => setSettings({ ...settings, enrollment_open_end: e.target.value })}
                  className={inputClass}
                />
              </div>
            </div>
          </div>
        </div>

        {/* 通知 */}
        <div className="space-y-5 p-5">
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-blue-600" />
            <h3 className="text-sm font-semibold text-slate-900">通知</h3>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">LINE Notify 推播</label>
            <p className="mb-2 text-xs text-slate-500">綁定 LINE 帳號，第一時間接收名額釋出推播。</p>
            <div className="flex flex-wrap gap-2">
              <input
                type="password"
                value={settings.line_notify_token}
                onChange={(e) => setSettings({ ...settings, line_notify_token: e.target.value })}
                placeholder={isEncrypted ? '（已加密，若不修改請留空）' : '輸入 LINE Token…'}
                className={`${inputClass} min-w-[16rem] flex-1`}
              />
              <button
                type="button"
                className="cursor-not-allowed whitespace-nowrap rounded-md border border-slate-200 bg-slate-100 px-4 py-2 text-sm text-slate-400"
                disabled
              >
                測試（尚未完善）
              </button>
            </div>
          </div>

          <div className="flex items-start justify-between gap-4 border-t border-slate-100 pt-5">
            <div className="flex items-start gap-3">
              <Mail className="mt-0.5 h-4 w-4 text-blue-600" />
              <div>
                <h4 className="text-sm font-medium text-slate-700">Email 通知</h4>
                <p className="mt-1 text-xs text-slate-500">名額變動或加選結果會寄到你的登入信箱。</p>
              </div>
            </div>
            <button
              type="button"
              aria-pressed={settings.email_notify}
              onClick={() => setSettings({ ...settings, email_notify: !settings.email_notify })}
              className={toggleClass(settings.email_notify)}
            >
              <span className={knobClass(settings.email_notify)} />
            </button>
          </div>

          {settings.email_notify && (
            <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Resend API Key</label>
                <input
                  type="password"
                  value={settings.resend_api_key}
                  onChange={(e) => setSettings({ ...settings, resend_api_key: e.target.value })}
                  placeholder={isEncrypted ? '（已加密，若不修改請留空）' : 're_xxxxxxxxxxxx'}
                  className={`${inputClass} bg-white`}
                />
                <p className="mt-1 text-xs text-slate-500">
                  需先到 Resend 註冊取得 API Key，後端會用各使用者自己的 Key 發信。
                  <a href="https://resend.com" target="_blank" rel="noopener noreferrer" className="ml-1 text-blue-600 hover:underline">
                    前往 Resend →
                  </a>
                </p>
              </div>

              <div className="border-t border-slate-200 pt-4">
                <p className="mb-2 text-xs font-medium text-slate-500">進階：改用 SMTP（選填，本機或允許出站 SMTP 的環境）</p>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700">SMTP 主機</label>
                    <input
                      type="text"
                      value={settings.smtp_host}
                      onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })}
                      placeholder="smtp.gmail.com"
                      className={`${inputClass} bg-white`}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700">SMTP 埠號</label>
                    <ClampedNumberInput
                      min={1}
                      max={65535}
                      value={settings.smtp_port}
                      onCommit={(v) => setSettings({ ...settings, smtp_port: v })}
                      className={`${inputClass} bg-white`}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700">寄件者 Email / 帳號</label>
                    <input
                      type="email"
                      value={settings.smtp_username}
                      onChange={(e) => setSettings({ ...settings, smtp_username: e.target.value })}
                      placeholder="your@email.com"
                      className={`${inputClass} bg-white`}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700">SMTP 密碼 / 應用程式密碼</label>
                    <input
                      type="password"
                      value={settings.smtp_password}
                      onChange={(e) => setSettings({ ...settings, smtp_password: e.target.value })}
                      placeholder={isEncrypted ? '（已加密，若不修改請留空）' : '••••••••'}
                      className={`${inputClass} bg-white`}
                    />
                    <p className="mt-1 text-xs text-slate-500">Gmail 請到 Google 帳號設定產生「應用程式密碼」。</p>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleSendTestEmail}
                disabled={testEmailSending}
                className="inline-flex items-center gap-2 whitespace-nowrap rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {testEmailSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                發送測試信
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

export default MonitorSettingsView;
