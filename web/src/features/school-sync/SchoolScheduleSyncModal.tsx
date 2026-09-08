import { KeyRound, Loader2 } from 'lucide-react';
import { useState } from 'react';

/**
 * 三個同步項目，按「多久會變」與「哪個階段才有意義」拆開：
 * - courses：選課清單與功課表（ChooseList/D01/D01），加退選期天天在動
 * - history：歷年成績（StuScoreQuery/DisplayAll），一學期才變一次，不必跟課表一起重抓
 * - preregistration：初選 A02 的已登記志願與志願序，只有初選期有值
 * 原本叫「官方選課狀態」不精確——加退選也是官方狀態；差別在階段與用途。
 */
export type SchoolSyncMode = 'courses' | 'history' | 'preregistration';

const SYNC_TABS: { mode: SchoolSyncMode; label: string; description: string }[] = [
  {
    mode: 'courses',
    label: '目前選課',
    description: '取得學校選課清單與功課表；加退選期這份就是最新課表。',
  },
  {
    mode: 'history',
    label: '歷年成績',
    description: '取得歷年成績與已修紀錄，並補查可辨識的歷史節次。一學期更新一次就夠。',
  },
  {
    mode: 'preregistration',
    label: '初選志願登記',
    description: '讀取初選已登記志願、待加入清單與志願序，不會送出選課。',
  },
];

export function SchoolScheduleSyncModal({
  mode = 'courses',
  username,
  password,
  rememberCredentials,
  hasSavedCredentials,
  phaseLabel,
  isPreregistrationPhase,
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
  hasSavedCredentials: boolean;
  /** 目前選課階段名稱，用來說明為什麼某個項目會是空的 */
  phaseLabel: string;
  isPreregistrationPhase: boolean;
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
  const isPreregistration = mode === 'preregistration';
  const activeTab = SYNC_TABS.find((tab) => tab.mode === mode) ?? SYNC_TABS[0];
  // 已保存密碼時收起輸入框：不必每次都打，按「改密碼」才展開。
  // 用「使用者是否要求更換」推導，不用 effect 同步 state。
  const [wantsNewPassword, setWantsNewPassword] = useState(false);
  const showPasswordField = !hasSavedCredentials || wantsNewPassword;
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
          <div role="tablist" aria-label="同步項目" className="mt-3 grid grid-cols-3 gap-1 rounded-md bg-slate-100 p-1">
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
            {hasSavedCredentials && !showPasswordField ? (
              <div className="flex items-center justify-between rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                <span>使用已保存的密碼（{username || '校務帳號'}）</span>
                <button
                  type="button"
                  onClick={() => setWantsNewPassword(true)}
                  disabled={isLoading}
                  className="whitespace-nowrap rounded px-2 py-1 text-xs font-medium text-emerald-700 underline hover:bg-emerald-100 disabled:cursor-not-allowed"
                >
                  改密碼
                </button>
              </div>
            ) : (
              <>
                <label className="block text-sm font-medium text-slate-700">校務系統密碼</label>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => onPasswordChange(event.target.value)}
                  disabled={isLoading}
                  autoComplete="current-password"
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
                />
                <p className="mt-1 text-xs text-slate-500">
                  {hasSavedCredentials
                    ? '留空即沿用已保存的密碼；輸入新密碼並勾選保存會覆蓋舊的。'
                    : '勾選保存後，密碼會由後端加密後寫入資料庫，之後同步就不必再輸入。'}
                </p>
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
                      之後任何一項同步都會自動帶入；前端不持有加密金鑰。
                    </span>
                  </span>
                </label>
              </>
            )}
          </div>
          {isPreregistration && !isPreregistrationPhase && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              目前是「{phaseLabel}」，初選頁本來就會回 0 門，這不是同步失敗。要更新已選上的課請改用「目前選課」。
            </div>
          )}
          <div className="rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-800">
            <p className="font-medium">{isPreregistration ? '本次同步會讀取：' : '本次同步會更新：'}</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {mode === 'courses' && (
                <>
                  <li>學校選課清單（目前選上的課）</li>
                  <li>官方功課表節次</li>
                </>
              )}
              {mode === 'history' && (
                <>
                  <li>歷年成績與已修紀錄</li>
                  <li>可辨識課程的歷史節次</li>
                  <li>待重修清單</li>
                </>
              )}
              {isPreregistration && (
                <>
                  <li>初選已登記志願與待加入清單</li>
                  <li>已登記志願序</li>
                  <li>初選功課表快照</li>
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
              {isLoading ? '同步中...' : `同步${activeTab.label}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
