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
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          載入代理設定…
        </div>
      </section>
    );
  }

  const inputClass =
    'w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 transition-colors focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500';

  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-blue-600" />
            <h2 className="text-base font-semibold text-slate-900">代理伺服器</h2>
          </div>
          <p className="mt-2 text-sm text-slate-500">
            讓 Worker 透過 SOCKS5 / HTTP 代理查詢課程，避免 IP 被封鎖。儲存後 Worker 在下次循環套用。
          </p>
        </div>
        <div className="flex items-center gap-3 self-start">
          <span className="whitespace-nowrap text-sm text-slate-500">啟用代理</span>
          <button
            type="button"
            aria-pressed={settings.proxy_enabled}
            onClick={() => set({ proxy_enabled: !settings.proxy_enabled })}
            className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ${settings.proxy_enabled ? 'bg-blue-600' : 'bg-slate-200'}`}
          >
            <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ${settings.proxy_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
          </button>
        </div>
      </div>

      <div className={`space-y-5 p-5 transition-opacity ${settings.proxy_enabled ? 'opacity-100' : 'pointer-events-none opacity-40'}`}>
        <div>
          <label className="mb-2 block text-sm font-medium text-slate-700">代理類型</label>
          <div className="flex flex-wrap gap-2">
            {(['socks5', 'http'] as const).map(t => (
              <button
                key={t}
                type="button"
                onClick={() => set({ proxy_type: t })}
                className={`whitespace-nowrap rounded-md border px-4 py-2 font-mono text-sm font-medium transition-colors ${
                  settings.proxy_type === t
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                {t.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium text-slate-700">主機位址（Host）</label>
            <input
              type="text"
              value={settings.proxy_host}
              onChange={e => set({ proxy_host: e.target.value })}
              placeholder="127.0.0.1 或 proxy.example.com"
              className={inputClass}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">埠號（Port）</label>
            <input
              type="text"
              value={settings.proxy_port}
              onChange={e => set({ proxy_port: e.target.value })}
              placeholder="9050"
              className={inputClass}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">帳號（選填）</label>
            <input
              type="text"
              value={settings.proxy_username}
              onChange={e => set({ proxy_username: e.target.value })}
              placeholder="留空表示不需驗證"
              className={inputClass}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">密碼（選填）</label>
            <input
              type="password"
              value={settings.proxy_password}
              onChange={e => set({ proxy_password: e.target.value })}
              placeholder="••••••••"
              className={inputClass}
            />
          </div>
        </div>

        {testResult && (
          <div className={`flex gap-2 rounded-md border p-3 text-sm ${testResult.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'}`}>
            {testResult.ok ? <CheckCircle2 size={15} className="mt-0.5 shrink-0" /> : <XCircle size={15} className="mt-0.5 shrink-0" />}
            {testResult.msg}
          </div>
        )}

        <div className="flex gap-2 rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800">
          <Info size={14} className="mt-0.5 shrink-0 text-blue-600" />
          <div className="space-y-1">
            <p>建議用 <strong>SOCKS5</strong>，隱私性比 HTTP 代理好。</p>
            <p>Tor 本機代理：<code className="rounded bg-white px-1">SOCKS5 127.0.0.1:9050</code></p>
            <p>SSH Tunnel：<code className="rounded bg-white px-1">SOCKS5 127.0.0.1:1080</code>（ssh -D 1080 user@server）</p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-5 py-4">
        <button
          type="button"
          onClick={handleTest}
          disabled={testing || !settings.proxy_enabled}
          className="inline-flex items-center gap-2 whitespace-nowrap rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
          格式驗證
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 whitespace-nowrap rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          儲存代理設定
        </button>
      </div>
    </section>
  );
};

export default ProxyView;
