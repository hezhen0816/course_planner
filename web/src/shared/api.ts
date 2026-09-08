import type {
  CourseSearchResult,
  CourseSemesterInfo,
  GpaApiKeyStatus,
  HistoryImportResponse,
  OfficialSelectionSyncResponse,
  RequirementPdfImportResponse,
  ScheduleSyncResponse,
  SchoolCredentials,
} from './types';

// Only fall back to a local backend while developing; a deployed site with no
// VITE_BACKEND_URL has no backend at all and should say so instead of probing
// localhost from the viewer's machine.
const API_BASE_URL = (import.meta.env.VITE_BACKEND_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/$/, '');

export const BACKEND_UNAVAILABLE_MESSAGE =
  '此站台未連接校務同步後端，無法同步課表或官方選課。請改用手機 App，或在 tailnet 內以本機執行 Web（VITE_BACKEND_URL）。';

export function isBackendConfigured(): boolean {
  return API_BASE_URL.length > 0;
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  if (!isBackendConfigured()) {
    throw new Error(BACKEND_UNAVAILABLE_MESSAGE);
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new Error(`無法連線到校務同步後端（${API_BASE_URL}）。請確認後端已啟動，且此裝置在同一個 tailnet 內。`);
  }
  if (!response.ok) {
    let message = `API 請求失敗 (${response.status})`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        message = String(payload.detail);
      }
    } catch {
      // Keep default message.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function authHeaders(accessToken: string): HeadersInit {
  return {
    Authorization: `Bearer ${accessToken}`,
  };
}

function jsonHeaders(accessToken?: string): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...(accessToken ? authHeaders(accessToken) : {}),
  };
}

export function fetchCourseSemesters(): Promise<CourseSemesterInfo[]> {
  return apiRequest<CourseSemesterInfo[]>('/api/courses/semesters');
}

export function searchCourses(
  semester: string,
  query: string,
  mode: 'name' | 'code',
  accessToken?: string,
  includeCrossSchool = false,
): Promise<CourseSearchResult[]> {
  const params = new URLSearchParams({ semester, q: query, mode });
  if (includeCrossSchool) params.set('include_cross_school', 'true');
  // 帶 token 時後端會用它取出已保存的 GPA 密鑰並附上 GPA；密鑰不經過前端。
  return apiRequest<CourseSearchResult[]>(`/api/courses/search?${params.toString()}`, {
    headers: accessToken ? authHeaders(accessToken) : undefined,
  });
}

export function getGpaApiKeyStatus(accessToken: string): Promise<GpaApiKeyStatus> {
  return apiRequest<GpaApiKeyStatus>('/api/gpa-api-key', { headers: authHeaders(accessToken) });
}

export function saveGpaApiKey(accessToken: string, apiKey: string, enabled: boolean): Promise<GpaApiKeyStatus> {
  return apiRequest<GpaApiKeyStatus>('/api/gpa-api-key', {
    method: 'PUT',
    headers: { ...authHeaders(accessToken), 'Content-Type': 'application/json' },
    body: JSON.stringify({ apiKey, enabled }),
  });
}

export function deleteGpaApiKey(accessToken: string): Promise<GpaApiKeyStatus> {
  return apiRequest<GpaApiKeyStatus>('/api/gpa-api-key', {
    method: 'DELETE',
    headers: authHeaders(accessToken),
  });
}

export function importRequirementsPdf(file: File): Promise<RequirementPdfImportResponse> {
  const formData = new FormData();
  formData.append('file', file);
  return apiRequest<RequirementPdfImportResponse>('/api/planner/import-requirements/pdf', {
    method: 'POST',
    body: formData,
  });
}

export function getSavedSchoolCredentials(accessToken: string): Promise<SchoolCredentials> {
  return apiRequest<SchoolCredentials>('/api/school-credentials', {
    headers: authHeaders(accessToken),
  });
}

export function saveSchoolCredentials(
  accessToken: string,
  username: string,
  password: string,
): Promise<SchoolCredentials> {
  return apiRequest<SchoolCredentials>('/api/school-credentials', {
    method: 'PUT',
    headers: {
      ...authHeaders(accessToken),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  });
}

export function deleteSavedSchoolCredentials(accessToken: string): Promise<SchoolCredentials> {
  return apiRequest<SchoolCredentials>('/api/school-credentials', {
    method: 'DELETE',
    headers: authHeaders(accessToken),
  });
}

export function syncSchoolSchedule(
  username: string,
  password: string,
  accessToken?: string,
): Promise<ScheduleSyncResponse> {
  return apiRequest<ScheduleSyncResponse>('/api/schedule/sync', {
    method: 'POST',
    headers: jsonHeaders(accessToken),
    body: JSON.stringify({
      username,
      ...(password ? { password } : {}),
      profile_key: username,
      persist_to_supabase: false,
      verify_ssl: false,
    }),
  });
}

export function importAcademicHistory(
  username: string,
  password: string,
  accessToken?: string,
): Promise<HistoryImportResponse> {
  return apiRequest<HistoryImportResponse>('/api/history/import', {
    method: 'POST',
    headers: jsonHeaders(accessToken),
    body: JSON.stringify({
      username,
      ...(password ? { password } : {}),
      profile_key: username,
      persist_to_supabase: false,
      verify_ssl: false,
    }),
  });
}

export function syncOfficialInitialSelection(
  username: string,
  password: string,
  accessToken?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/sync', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
    },
    body: JSON.stringify({
      username,
      ...(password ? { password } : {}),
      profile_key: username,
      verify_ssl: false,
    }),
  });
}

export function keepOfficialInitialSelectionAlive(
  username: string,
  accessToken?: string,
): Promise<{ session_valid: boolean; checked_at: string }> {
  return apiRequest<{ session_valid: boolean; checked_at: string }>('/api/official-selection/a02/keep-alive', {
    method: 'POST',
    headers: jsonHeaders(accessToken),
    body: JSON.stringify({
      username,
      profile_key: username,
      verify_ssl: false,
    }),
  });
}

export function joinOfficialInitialSelectionCourse(
  username: string,
  courseNo: string,
  accessToken?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/join', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
    },
    body: JSON.stringify({
      username,
      course_no: courseNo,
      confirmed: true,
      profile_key: username,
      verify_ssl: false,
    }),
  });
}

export function addOfficialInitialSelectionWaitlistCourse(
  username: string,
  courseNo: string,
  accessToken?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/add-to-waitlist', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
    },
    body: JSON.stringify({
      username,
      course_no: courseNo,
      confirmed: true,
      profile_key: username,
      verify_ssl: false,
    }),
  });
}

export function removeOfficialInitialSelectionCourse(
  username: string,
  courseNo: string,
  accessToken?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/remove', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
    },
    body: JSON.stringify({
      username,
      course_no: courseNo,
      confirmed: true,
      profile_key: username,
      verify_ssl: false,
    }),
  });
}

export function reorderOfficialInitialSelectionCourses(
  username: string,
  orderedCourseNos: string[],
  accessToken?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/reorder', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
    },
    body: JSON.stringify({
      username,
      ordered_course_nos: orderedCourseNos,
      confirmed: true,
      profile_key: username,
      verify_ssl: false,
    }),
  });
}
