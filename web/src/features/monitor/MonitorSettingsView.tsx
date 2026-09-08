import ClampedNumberInput from './ClampedNumberInput';
import React, { useState, useEffect } from 'react';
import { KeyRound, Activity, Bell, Save, Loader2, Mail, Clock } from 'lucide-react';
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
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Section 1: School Account (managed in Compass 設定 → 校務帳密) */}
      <section>
        <h3 className="text-lg font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <KeyRound size={20} className="text-blue-500" />
          學校帳號
        </h3>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
          <p className="text-sm text-slate-600">
            監控與自動加選使用的學號與選課密碼，請至「設定」頁的「校務帳密」設定；此處不再另外儲存。
          </p>
        </div>
      </section>

      {/* Section 2: Monitoring Strategy */}
      <section>
        <h3 className="text-lg font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <Activity size={20} className="text-purple-500" />
          進階監控設定
        </h3>
        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200 space-y-6">
          {/* Interval */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm font-medium text-slate-700">基本監控間隔</label>
              <span className="text-blue-600 text-xs font-mono bg-blue-50 px-2 py-0.5 rounded">
                {settings.check_interval >= 1000
                  ? `${(settings.check_interval / 1000).toFixed(1)}s`
                  : `${settings.check_interval}ms`}
              </span>
            </div>
            <div className="flex gap-3 items-center">
              <input
                type="range"
                min="500"
                max="60000"
                step="500"
                value={Math.min(settings.check_interval, 60000)}
                onChange={(e) => setSettings({ ...settings, check_interval: parseInt(e.target.value) })}
                className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
              <div className="flex items-center gap-1.5">
                <ClampedNumberInput
                  min={500}
                  max={60000}
                  step={500}
                  value={settings.check_interval}
                  onCommit={(v) => setSettings({ ...settings, check_interval: v })}
                  className="w-20 px-2 py-1 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 text-sm text-center focus:ring-2 focus:ring-blue-500 focus:outline-none font-mono"
                />
                <span className="text-slate-400 text-xs whitespace-nowrap">ms</span>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-2">每次向選課系統發送請求的基礎等待時間（建議偵測用 5000–30000ms）</p>
          </div>

          {/* 當前選課時段：決定自動加選使用 A06 或 B01 流程 */}
          <div className="pt-4 border-t border-slate-100">
            <h4 className="font-medium text-slate-800 mb-2">當前選課時段</h4>
            <p className="text-sm text-slate-500 mb-3">
              自動加選時會依此選項向選課系統送出對應流程。請依學校公告的開放時段選擇。
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setSettings({ ...settings, enrollment_period: 'A06' })}
                className={`px-4 py-2 rounded-lg border-2 text-sm font-medium transition-colors ${
                  settings.enrollment_period === 'A06'
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                電腦抽選後選課 (A06)
              </button>
              <button
                type="button"
                onClick={() => setSettings({ ...settings, enrollment_period: 'B01' })}
                className={`px-4 py-2 rounded-lg border-2 text-sm font-medium transition-colors ${
                  settings.enrollment_period === 'B01'
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                加退選課 (B01)
              </button>
            </div>
          </div>

          {/* 選課開放時間（台灣時間，含日期）：僅在時段內才送出加選請求 */}
          <div className="pt-4 border-t border-slate-100">
            <h4 className="font-medium text-slate-800 mb-2 flex items-center gap-2">
              <Clock size={18} className="text-slate-500" />
              選課開放時間（台灣時間，含日期）
            </h4>
            <p className="text-sm text-slate-500 mb-3">
              僅在此日期時間範圍內送出加選請求；若皆留空則不限制。可減少非開放時段的不必要請求。
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">開始日期時間</label>
                <input
                  type="datetime-local"
                  value={settings.enrollment_open_start}
                  onChange={(e) => setSettings({ ...settings, enrollment_open_start: e.target.value })}
                  className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                />
                <span className="text-xs text-slate-400 ml-2">例：2025-02-24 09:00</span>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">結束日期時間</label>
                <input
                  type="datetime-local"
                  value={settings.enrollment_open_end}
                  onChange={(e) => setSettings({ ...settings, enrollment_open_end: e.target.value })}
                  className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                />
                <span className="text-xs text-slate-400 ml-2">例：2025-02-28 17:00</span>
              </div>
            </div>
          </div>

          {/* Random Interval */}
          <div className="pt-4 border-t border-slate-100">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">隨機間隔範圍 (秒)</label>
                <div className="flex items-center gap-2">
                  <ClampedNumberInput
                    min={0}
                    max={60}
                    value={settings.random_interval}
                    onCommit={(v) => setSettings({ ...settings, random_interval: v })}
                    className="w-20 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors text-slate-800 text-center"
                  />
                  <span className="text-slate-400 text-sm whitespace-nowrap">秒</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  防止被系統識別為機器人，實際間隔將加上此隨機值（例如: {(settings.check_interval / 1000).toFixed(0)} ± {settings.random_interval} 秒）。設為 0 表示不加隨機。
                </p>
              </div>
            </div>
          </div>

          {/* SSL */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <div>
              <h4 className="font-medium text-slate-800">SSL 憑證驗證</h4>
              <p className="text-sm text-slate-500 mt-1">關閉此選項可忽略憑證錯誤。若學校伺服器憑證過期導致爬蟲失敗時可關閉。</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, verify_ssl: !settings.verify_ssl })}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${settings.verify_ssl ? 'bg-blue-600' : 'bg-slate-200'}`}
            >
              <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform duration-200 ease-in-out ${settings.verify_ssl ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
          </div>
        </div>
      </section>

      {/* Section 3: Notifications */}
      <section>
        <h3 className="text-lg font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <Bell size={20} className="text-blue-500" />
          通知設定
        </h3>
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
          {/* LINE Notify */}
          <div className="p-6 border-b border-slate-100">
            <h4 className="font-medium text-slate-800 mb-1">LINE Notify 推播</h4>
            <p className="text-sm text-slate-500 mb-3">綁定 LINE 帳號，第一時間接收名額釋出推播</p>
            <div className="flex gap-2">
              <input
                type="password"
                value={settings.line_notify_token}
                onChange={(e) => setSettings({ ...settings, line_notify_token: e.target.value })}
                placeholder={isEncrypted ? "(已加密，若不修改請留空)" : "輸入 Line Token..."}
                className="flex-1 px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors text-slate-800"
              />
              <button className="px-4 py-2 bg-slate-100 text-slate-400 text-sm rounded-lg cursor-not-allowed border border-slate-200" disabled>
                測試 (尚未完善)
              </button>
            </div>
          </div>

          {/* Email */}
          <div className="p-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mail size={18} className="text-blue-500" />
              <div>
                <h4 className="font-medium text-slate-800">Email 通知</h4>
                <p className="text-sm text-slate-500 mt-1">名額變動或加選結果將發送至您的登入信箱</p>
              </div>
            </div>
            <button
              onClick={() => setSettings({ ...settings, email_notify: !settings.email_notify })}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${settings.email_notify ? 'bg-blue-600' : 'bg-slate-200'}`}
            >
              <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform duration-200 ease-in-out ${settings.email_notify ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
          </div>
          {settings.email_notify && (
            <div className="px-6 pb-6 -mt-2 space-y-4">
              {/* Resend API Key（建議：適用 Railway 等限制 SMTP 的環境） */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Resend API Key</label>
                <input
                  type="password"
                  value={settings.resend_api_key}
                  onChange={(e) => setSettings({ ...settings, resend_api_key: e.target.value })}
                  placeholder={isEncrypted ? "(已加密，若不修改請留空)" : "re_xxxxxxxxxxxx"}
                  className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                />
                <p className="text-xs text-slate-500 mt-1">
                  需至 Resend 註冊並取得 API Key，發送時以後端依各使用者設定的 Key 發信。
                  <a href="https://resend.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline ml-1">前往 Resend →</a>
                </p>
              </div>

              {/* 進階：SMTP（本機或允許 SMTP 的環境可選填） */}
              <div className="pt-2 border-t border-slate-100">
                <p className="text-xs font-medium text-slate-500 mb-2">進階：使用 SMTP（選填，本機或允許出站 SMTP 的環境）</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">SMTP 主機</label>
                    <input
                      type="text"
                      value={settings.smtp_host}
                      onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })}
                      placeholder="smtp.gmail.com"
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">SMTP 埠號</label>
                    <ClampedNumberInput
                      min={1}
                      max={65535}
                      value={settings.smtp_port}
                      onCommit={(v) => setSettings({ ...settings, smtp_port: v })}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">寄件者 Email / 帳號</label>
                    <input
                      type="email"
                      value={settings.smtp_username}
                      onChange={(e) => setSettings({ ...settings, smtp_username: e.target.value })}
                      placeholder="your@email.com"
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">SMTP 密碼 / 應用程式密碼</label>
                    <input
                      type="password"
                      value={settings.smtp_password}
                      onChange={(e) => setSettings({ ...settings, smtp_password: e.target.value })}
                      placeholder={isEncrypted ? "(已加密，若不修改請留空)" : "••••••••"}
                      className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                    />
                    <p className="text-xs text-slate-500 mt-1">Gmail 請至 Google 帳號設定產生「應用程式密碼」</p>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleSendTestEmail}
                disabled={testEmailSending}
                className="inline-flex items-center gap-2 whitespace-nowrap px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg border border-slate-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {testEmailSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                發送測試信
              </button>
            </div>
          )}
        </div>
      </section>

      {/* Save Button */}
      <div className="pt-4 text-right">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-8 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg shadow-sm transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ml-auto"
        >
          {saving ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} />}
          儲存設定參數
        </button>
      </div>
    </div>
  );
};

export default MonitorSettingsView;
