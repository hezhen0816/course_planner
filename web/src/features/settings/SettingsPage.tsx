import { useEffect, useState } from 'react';
import { KeyRound, RefreshCw, Settings, ShieldCheck } from 'lucide-react';
import type { AppData, GpaApiSettings, ProgramDepartmentSettings } from '../../shared/types';
import { listCourseDepartments } from '../../shared/domain/courseDepartments';

const EMPTY_GPA_API_SETTINGS: GpaApiSettings = {
  enabled: false,
  apiKey: '',
};
const EMPTY_PROGRAM_DEPARTMENT_SETTINGS: ProgramDepartmentSettings = {};
const COURSE_DEPARTMENTS = listCourseDepartments();

type SettingsPageProps = {
  initialSettings: AppData['targets'];
  schoolUsername: string;
  selectionTargetLabel: string;
  hasSavedSchoolCredentials: boolean;
  syncStatus: 'idle' | 'loading' | 'error' | 'success';
  syncMessage: string;
  officialSelectionStatus: 'idle' | 'loading' | 'error' | 'success';
  officialSelectionMessage: string;
  initialGpaApiSettings?: GpaApiSettings;
  initialProgramDepartmentSettings?: ProgramDepartmentSettings;
  onSaveTargets: (targets: AppData['targets']) => void;
  onSaveGpaApiSettings: (settings: GpaApiSettings) => void;
  onSaveProgramDepartmentSettings: (settings: ProgramDepartmentSettings) => void;
  onOpenSchoolSync: () => void;
  onOpenOfficialSelectionSync: () => void;
  onClearSavedSchoolCredentials: () => void;
};

export function SettingsPage({
  initialSettings,
  schoolUsername,
  selectionTargetLabel,
  hasSavedSchoolCredentials,
  syncStatus,
  syncMessage,
  officialSelectionStatus,
  officialSelectionMessage,
  initialGpaApiSettings,
  initialProgramDepartmentSettings,
  onSaveTargets,
  onSaveGpaApiSettings,
  onSaveProgramDepartmentSettings,
  onOpenSchoolSync,
  onOpenOfficialSelectionSync,
  onClearSavedSchoolCredentials,
}: SettingsPageProps) {
  const [settingsForm, setSettingsForm] = useState(initialSettings);
  const [gpaApiForm, setGpaApiForm] = useState<GpaApiSettings>({
    ...EMPTY_GPA_API_SETTINGS,
    ...initialGpaApiSettings,
  });
  const [programDepartmentForm, setProgramDepartmentForm] = useState<ProgramDepartmentSettings>({
    ...EMPTY_PROGRAM_DEPARTMENT_SETTINGS,
    ...initialProgramDepartmentSettings,
  });
  const [programDepartmentSaved, setProgramDepartmentSaved] = useState(false);

  useEffect(() => {
    setSettingsForm(initialSettings);
  }, [initialSettings]);

  useEffect(() => {
    setGpaApiForm({
      ...EMPTY_GPA_API_SETTINGS,
      ...initialGpaApiSettings,
    });
  }, [initialGpaApiSettings]);

  useEffect(() => {
    setProgramDepartmentForm({
      ...EMPTY_PROGRAM_DEPARTMENT_SETTINGS,
      ...initialProgramDepartmentSettings,
    });
  }, [initialProgramDepartmentSettings]);

  useEffect(() => {
    if (!programDepartmentSaved) return;
    const timer = window.setTimeout(() => setProgramDepartmentSaved(false), 2000);
    return () => window.clearTimeout(timer);
  }, [programDepartmentSaved]);

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">設定</p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-950">資料同步與畢業門檻</h1>
            <p className="mt-1 text-sm text-slate-500">校務資料同步、畢業門檻數字與帳號層級設定集中放在這裡，不混進選課流程。</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              onClick={onOpenSchoolSync}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <RefreshCw className="h-4 w-4" />
              同步校務資料
            </button>
            <button
              onClick={onOpenOfficialSelectionSync}
              disabled={officialSelectionStatus === 'loading'}
              className="inline-flex items-center justify-center gap-2 rounded-md border border-blue-300 bg-white px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${officialSelectionStatus === 'loading' ? 'animate-spin' : ''}`} />
              同步官方選課狀態
            </button>
          </div>
        </div>
        {syncMessage && (
          <p className={`mt-4 rounded-md px-3 py-2 text-sm ${
            syncStatus === 'error' ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'
          }`}>
            {syncMessage}
          </p>
        )}
        {officialSelectionMessage && (
          <p className={`mt-3 rounded-md px-3 py-2 text-sm ${
            officialSelectionStatus === 'error' ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
          }`}>
            官方選課狀態：{officialSelectionMessage}
          </p>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <Settings className="h-4 w-4 text-blue-600" />
          <h2 className="text-base font-semibold text-slate-900">雙主修與輔系系所</h2>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSaveProgramDepartmentSettings({
              homeDepartmentCode: programDepartmentForm.homeDepartmentCode || undefined,
              doubleMajorDepartmentCode: programDepartmentForm.doubleMajorDepartmentCode || undefined,
              minorDepartmentCode: programDepartmentForm.minorDepartmentCode || undefined,
            });
            setProgramDepartmentSaved(true);
          }}
          className="space-y-4 p-5"
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <DepartmentField
              label="本系系所"
              value={programDepartmentForm.homeDepartmentCode || ''}
              onChange={(value) => setProgramDepartmentForm({
                ...programDepartmentForm,
                homeDepartmentCode: value || undefined,
              })}
            />
            <DepartmentField
              label="雙主修系所"
              value={programDepartmentForm.doubleMajorDepartmentCode || ''}
              onChange={(value) => setProgramDepartmentForm({
                ...programDepartmentForm,
                doubleMajorDepartmentCode: value || undefined,
              })}
            />
            <DepartmentField
              label="輔系系所"
              value={programDepartmentForm.minorDepartmentCode || ''}
              onChange={(value) => setProgramDepartmentForm({
                ...programDepartmentForm,
                minorDepartmentCode: value || undefined,
              })}
            />
          </div>
          <p className="text-sm text-slate-500">
            選課工作台會依課碼前兩碼比對這裡設定的系所，改變課程顏色標示。
          </p>
          <div className="flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className={`text-sm font-medium ${programDepartmentSaved ? 'text-emerald-700' : 'text-slate-400'}`}>
              {programDepartmentSaved ? '系所設定已更新，將自動同步到資料庫。' : '儲存後會套用到選課工作台顏色。'}
            </p>
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              儲存系所設定
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-blue-600" />
              <h2 className="text-base font-semibold text-slate-900">校務帳號與選課目標</h2>
            </div>
            <p className="mt-2 text-sm text-slate-500">
              校務帳號用來同步官方選課清單與歷年成績，並可由學號推定目前選課對應的大幾學期。
            </p>
          </div>
          <button
            onClick={onOpenSchoolSync}
            className="inline-flex items-center justify-center gap-2 rounded-md border border-blue-300 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50"
          >
            <RefreshCw className="h-4 w-4" />
            設定 / 同步校務帳號
          </button>
        </div>
        <div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2">
          <InfoRow label="目前學號" value={schoolUsername.trim() || '尚未設定'} />
          <InfoRow label="推定選課目標" value={selectionTargetLabel} />
          <div className="flex flex-col gap-3 rounded-md border border-blue-200 bg-blue-50 px-3 py-3 text-sm text-blue-800 md:col-span-2 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="font-medium">
                {hasSavedSchoolCredentials ? '校務帳密已加密保存於資料庫。' : '尚未保存校務密碼。'}
              </p>
              <p className="mt-1 text-xs text-blue-700">
                {hasSavedSchoolCredentials
                  ? '官方 session 過期時，可直接重新同步官方選課狀態，不必再輸入密碼。'
                  : '請在同步視窗勾選保存並成功同步一次，之後官方 session 過期才可直接重新同步。'}
              </p>
            </div>
            <button
              type="button"
              onClick={onClearSavedSchoolCredentials}
              disabled={!hasSavedSchoolCredentials}
              className="inline-flex justify-center rounded-md border border-blue-300 bg-white px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            >
              清除保存密碼
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-blue-600" />
              <h2 className="text-base font-semibold text-slate-900">GPA API 密鑰</h2>
            </div>
            <p className="mt-2 text-sm text-slate-500">
              預留 GPA API 串接設定；目前只保存設定，不會自動向第三方 GPA API 發送請求。
            </p>
          </div>
          <span className={`w-fit rounded-full px-2 py-1 text-xs font-medium ${
            gpaApiForm.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'
          }`}>
            {gpaApiForm.enabled ? '已啟用' : '未啟用'}
          </span>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSaveGpaApiSettings({
              enabled: gpaApiForm.enabled,
              apiKey: gpaApiForm.apiKey.trim(),
              updatedAt: new Date().toISOString(),
            });
          }}
          className="space-y-4 p-5"
        >
          <label className="flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
            <input
              type="checkbox"
              checked={gpaApiForm.enabled}
              onChange={(event) => setGpaApiForm({ ...gpaApiForm, enabled: event.target.checked })}
              className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <span>
              <span className="block text-sm font-medium text-slate-800">啟用 GPA API 串接</span>
              <span className="mt-1 block text-xs text-slate-500">啟用後，未來 GPA 匯入流程會讀取這組 API 設定。</span>
            </span>
          </label>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <TextField
              label="API 密鑰"
              value={gpaApiForm.apiKey}
              onChange={(value) => setGpaApiForm({ ...gpaApiForm, apiKey: value })}
              placeholder="貼上 GPA API token"
              type="password"
              wide
            />
          </div>

          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            GPA API 密鑰屬於敏感資料；正式串接前建議改由後端加密保存，避免把密鑰暴露在前端或一般資料欄位。
          </div>

          <div className="flex justify-end border-t border-slate-100 pt-4">
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              儲存 GPA API 設定
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <Settings className="h-4 w-4 text-blue-600" />
          <h2 className="text-base font-semibold text-slate-900">設定畢業門檻</h2>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSaveTargets(settingsForm);
          }}
          className="space-y-5 p-5"
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <NumberField
              label="畢業總學分"
              value={settingsForm.total}
              onChange={(value) => setSettingsForm({ ...settingsForm, total: value })}
              wide
            />
            <NumberField
              label="必修國文"
              value={settingsForm.chinese}
              onChange={(value) => setSettingsForm({ ...settingsForm, chinese: value })}
            />
            <NumberField
              label="共同必修英文"
              value={settingsForm.english}
              onChange={(value) => setSettingsForm({ ...settingsForm, english: value })}
            />
            <NumberField
              label="通識學分"
              value={settingsForm.gen_ed}
              onChange={(value) => setSettingsForm({ ...settingsForm, gen_ed: value })}
            />
            <NumberField
              label="社會實踐"
              value={settingsForm.social}
              onChange={(value) => setSettingsForm({ ...settingsForm, social: value })}
            />
            <NumberField
              label="體育（學期數）"
              value={settingsForm.pe_semesters}
              onChange={(value) => setSettingsForm({ ...settingsForm, pe_semesters: value })}
              wide
            />
          </div>

          <div className="border-t border-slate-100 pt-5">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">系所課程門檻</h3>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <NumberField
                label="本系必修"
                value={settingsForm.home_compulsory}
                onChange={(value) => setSettingsForm({ ...settingsForm, home_compulsory: value })}
              />
              <NumberField
                label="本系選修"
                value={settingsForm.home_elective}
                onChange={(value) => setSettingsForm({ ...settingsForm, home_elective: value })}
              />
              <NumberField
                label="雙主修"
                value={settingsForm.double_major}
                onChange={(value) => setSettingsForm({ ...settingsForm, double_major: value })}
              />
              <NumberField
                label="輔修"
                value={settingsForm.minor}
                onChange={(value) => setSettingsForm({ ...settingsForm, minor: value })}
              />
            </div>
          </div>

          <div className="flex justify-end border-t border-slate-100 pt-5">
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              儲存設定
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  wide = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: 'text' | 'password';
  wide?: boolean;
}) {
  return (
    <label className={wide ? 'md:col-span-2' : undefined}>
      <span className="block text-sm font-medium text-slate-700">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
      />
    </label>
  );
}

function DepartmentField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span className="block text-sm font-medium text-slate-700">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
      >
        <option value="">未設定</option>
        {COURSE_DEPARTMENTS.map((department) => (
          <option key={department.code} value={department.code}>
            {department.code}・{department.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
  wide = false,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  wide?: boolean;
}) {
  return (
    <label className={wide ? 'md:col-span-2' : undefined}>
      <span className="block text-sm font-medium text-slate-700">{label}</span>
      <input
        type="number"
        min="0"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
      />
    </label>
  );
}
