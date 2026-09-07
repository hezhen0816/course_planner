import { KeyRound, Loader2 } from 'lucide-react';

export type SchoolSyncMode = 'school-data' | 'official-selection';

const SYNC_TABS: { mode: SchoolSyncMode; label: string; description: string }[] = [
  {
    mode: 'school-data',
    label: '課表與成績',
    description: '取得最新選課清單、歷年成績，並自動補查可辨識的歷史節次。',
  },
  {
    mode: 'official-selection',
    label: '官方選課狀態',
    description: '讀取官方已選、待加入、志願序與功課表狀態，不會送出選課。',
  },
];

export function SchoolScheduleSyncModal({
  mode = 'school-data',
  username,
  password,
  rememberCredentials,
  status,
  message,
  onModeChange,
  onUsernameChange,
  onPasswordChange,
  onRememberCredentialsChange,
  onClose,
  onImport,
}: {
  mode?: SchoolSyncMode;
  username: string;
  password: string;
  rememberCredentials: boolean;
  status: 'idle' | 'loading' | 'error' | 'success';
  message: string;
  onModeChange: (mode: SchoolSyncMode) => void;
  onUsernameChange: (username: string) => void;
  onPasswordChange: (password: string) => void;
  onRememberCredentialsChange: (remember: boolean) => void;
  onClose: () => void;
  onImport: () => void;
}) {
  const isLoading = status === 'loading';
  const isOfficialSelection = mode === 'official-selection';
  const activeTab = SYNC_TABS.find((tab) => tab.mode === mode) ?? SYNC_TABS[0];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
      <div className="w-full max-w-md overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="border-b border-slate-200 p-4">
          <div className="flex items-start justify-between gap-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-950">
              <KeyRound className="h-5 w-5 text-blue-600" />
              同步校務資料
            </h2>
            <button onClick={onClose} disabled={isLoading} className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50">✕</button>
          </div>
          {/* One entry point, two jobs: the tab decides what the sync pulls. */}
          <div role="tablist" aria-label="同步項目" className="mt-3 grid grid-cols-2 gap-1 rounded-md bg-slate-100 p-1">
            {SYNC_TABS.map((tab) => {
              const isActive = tab.mode === mode;
              return (
                <button
                  key={tab.mode}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  disabled={isLoading}
                  onClick={() => onModeChange(tab.mode)}
                  className={`rounded px-3 py-1.5 text-sm font-medium transition ${
                    isActive ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                  } disabled:cursor-not-allowed`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-sm text-slate-500">{activeTab.description}</p>
        </div>
        <form
          className="space-y-4 p-4"
          onSubmit={(event) => {
            event.preventDefault();
            onImport();
          }}
        >
          <div>
            <label className="block text-sm font-medium text-slate-700">校務系統帳號</label>
            <input
              value={username}
              onChange={(event) => onUsernameChange(event.target.value)}
              disabled={isLoading}
              autoComplete="username"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">校務系統密碼</label>
            <input
              type="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              disabled={isLoading}
              autoComplete="current-password"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
            />
            <p className="mt-1 text-xs text-slate-500">已保存校務帳密時可留空；勾選保存後，密碼會由後端加密後寫入資料庫。</p>
            <label className="mt-3 flex items-start gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={rememberCredentials}
                onChange={(event) => onRememberCredentialsChange(event.target.checked)}
                disabled={isLoading}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <span>
                <span className="font-medium">加密保存校務帳密</span>
                <span className="mt-0.5 block text-xs text-slate-500">
                  之後同步校務資料或官方選課狀態時會自動帶入；前端不持有加密金鑰。
                </span>
              </span>
            </label>
          </div>
          <div className="rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-800">
            <p className="font-medium">{isOfficialSelection ? '本次同步會讀取：' : '本次同步會更新：'}</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {isOfficialSelection ? (
                <>
                  <li>官方已選與待加入清單</li>
                  <li>已登記志願序</li>
                  <li>官方功課表快照</li>
                </>
              ) : (
                <>
                  <li>目前查詢學期的選課清單</li>
                  <li>歷年成績與已修紀錄</li>
                  <li>可辨識課程的歷史節次</li>
                </>
              )}
            </ul>
            <p className="mt-2 text-xs text-blue-700">不會自動送出選課、不會排程重試。</p>
          </div>
          {message && (
            <p className={`rounded-md px-3 py-2 text-sm ${status === 'error' ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'}`}>
              {message}
            </p>
          )}
          <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              關閉
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
              {isLoading ? '同步中...' : isOfficialSelection ? '同步官方選課狀態' : '開始同步'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
