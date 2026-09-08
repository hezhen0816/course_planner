import React, { useState, useEffect } from 'react';
import { Shield, Save, Loader2, CheckCircle2, XCircle, Info } from 'lucide-react';
import { supabase } from './supabaseClient';

interface ProxySettings {
  proxy_enabled: boolean;
  proxy_type: 'http' | 'socks5';
  proxy_host: string;
  proxy_port: string;
  proxy_username: string;
  proxy_password: string;
}

const DEFAULT: ProxySettings = {
  proxy_enabled: false,
  proxy_type: 'socks5',
  proxy_host: '',
  proxy_port: '',
  proxy_username: '',
  proxy_password: '',
};

const ProxyView: React.FC = () => {
  const [settings, setSettings] = useState<ProxySettings>(DEFAULT);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase
        .from('user_settings')
        .select('proxy_enabled, proxy_type, proxy_host, proxy_port, proxy_username, proxy_password')
        .eq('user_id', user.id)
        .single();
      if (data) {
        setSettings({
          proxy_enabled: data.proxy_enabled ?? false,
          proxy_type: data.proxy_type ?? 'socks5',
          proxy_host: data.proxy_host ?? '',
          proxy_port: data.proxy_port ?? '',
          proxy_username: data.proxy_username ?? '',
          proxy_password: data.proxy_password ?? '',
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setTestResult(null);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { error } = await supabase
        .from('user_settings')
        .upsert({ user_id: user.id, ...settings, updated_at: new Date().toISOString() });
      if (error) throw error;
      alert('代理設定已儲存，Worker 下次循環將套用。');
    } catch (e) {
      alert('儲存失敗：' + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!settings.proxy_host || !settings.proxy_port) {
      alert('請先填寫主機與埠號');
      return;
    }
    setTesting(true);
    setTestResult(null);
    await new Promise(r => setTimeout(r, 800));
    const portNum = parseInt(settings.proxy_port);
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
      setTestResult({ ok: false, msg: '埠號無效，請輸入 1–65535 之間的數字。' });
    } else {
      setTestResult({
        ok: true,
        msg: `格式正確（${settings.proxy_type.toUpperCase()} ${settings.proxy_host}:${settings.proxy_port}）。實際連線測試將由後端 Worker 執行。`,
      });
    }
    setTesting(false);
  };

  const set = (patch: Partial<ProxySettings>) => setSettings(prev => ({ ...prev, ...patch }));

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <header>
        <h2 className="text-2xl font-bold text-slate-800">代理伺服器</h2>
        <p className="text-slate-500 text-sm mt-1">設定 SOCKS5 / HTTP 代理，讓 Worker 透過代理查詢課程，避免 IP 被封鎖</p>
      </header>

      {/* Info banner */}
      <div className="flex gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-700">
        <Info size={16} className="shrink-0 mt-0.5 text-blue-500" />
        <div>
          代理設定儲存後，後端 Worker 在下次循環時自動套用。
          推薦使用 <strong className="text-blue-800">SOCKS5</strong>，隱私性較 HTTP 代理更好。
          免費可試用 <strong className="text-blue-800">Tor（127.0.0.1:9050）</strong> 或自建 SSH Tunnel。
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
          <h3 className="font-semibold text-slate-800 flex items-center gap-2">
            <Shield size={18} className="text-purple-500" /> 代理設定
          </h3>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-500">啟用代理</span>
            <button
              onClick={() => set({ proxy_enabled: !settings.proxy_enabled })}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ${settings.proxy_enabled ? 'bg-purple-600' : 'bg-slate-200'}`}
            >
              <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ${settings.proxy_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
          </div>
        </div>

        <div className={`p-6 space-y-5 transition-opacity ${settings.proxy_enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
          {/* Type selector */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">代理類型</label>
            <div className="flex gap-3">
              {(['socks5', 'http'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => set({ proxy_type: t })}
                  className={`px-5 py-2 rounded-lg border font-mono text-sm font-medium transition-all ${
                    settings.proxy_type === t
                      ? 'bg-purple-600 border-purple-500 text-white'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {t.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Host + Port */}
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-2">主機位址 (Host)</label>
              <input
                type="text"
                value={settings.proxy_host}
                onChange={e => set({ proxy_host: e.target.value })}
                placeholder="127.0.0.1 或 proxy.example.com"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:ring-2 focus:ring-purple-500 focus:outline-none focus:bg-white transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">埠號 (Port)</label>
              <input
                type="text"
                value={settings.proxy_port}
                onChange={e => set({ proxy_port: e.target.value })}
                placeholder="9050"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:ring-2 focus:ring-purple-500 focus:outline-none focus:bg-white transition-colors"
              />
            </div>
          </div>

          {/* Username + Password */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">帳號（選填）</label>
              <input
                type="text"
                value={settings.proxy_username}
                onChange={e => set({ proxy_username: e.target.value })}
                placeholder="留空表示不需驗證"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:ring-2 focus:ring-purple-500 focus:outline-none focus:bg-white transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">密碼（選填）</label>
              <input
                type="password"
                value={settings.proxy_password}
                onChange={e => set({ proxy_password: e.target.value })}
                placeholder="••••••••"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:ring-2 focus:ring-purple-500 focus:outline-none focus:bg-white transition-colors"
              />
            </div>
          </div>

          {/* Test result */}
          {testResult && (
            <div className={`flex gap-2 p-3 rounded-lg text-sm ${testResult.ok ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
              {testResult.ok ? <CheckCircle2 size={15} className="shrink-0 mt-0.5" /> : <XCircle size={15} className="shrink-0 mt-0.5" />}
              {testResult.msg}
            </div>
          )}

          {/* Presets */}
          <div className="text-xs text-slate-500 space-y-1">
            <p className="font-medium text-slate-600">常用設定範例：</p>
            <p>• Tor Browser 本地代理：<code className="text-slate-700 bg-slate-100 px-1 rounded">SOCKS5 127.0.0.1:9050</code></p>
            <p>• SSH Tunnel：<code className="text-slate-700 bg-slate-100 px-1 rounded">SOCKS5 127.0.0.1:1080</code>（ssh -D 1080 user@server）</p>
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <button
          onClick={handleTest}
          disabled={testing || !settings.proxy_enabled}
          className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-all flex items-center gap-2 disabled:opacity-40 border border-slate-200"
        >
          {testing ? <Loader2 className="animate-spin" size={16} /> : <CheckCircle2 size={16} />}
          格式驗證
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-8 py-2.5 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg shadow-sm transition-all flex items-center gap-2 disabled:opacity-50"
        >
          {saving ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} />}
          儲存設定
        </button>
      </div>
    </div>
  );
};

export default ProxyView;
