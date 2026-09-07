import type {
  CourseSearchResult,
  CourseSemesterInfo,
  HistoryImportResponse,
  OfficialSelectionSyncResponse,
  RequirementPdfImportResponse,
  ScheduleSyncResponse,
  SchoolCredentials,
} from './types';

const API_BASE_URL = (import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '');

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
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
  gpaApiKey?: string,
): Promise<CourseSearchResult[]> {
  const params = new URLSearchParams({ semester, q: query, mode });
  return apiRequest<CourseSearchResult[]>(`/api/courses/search?${params.toString()}`, {
    headers: gpaApiKey ? { 'X-GPA-API-Key': gpaApiKey } : undefined,
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
  gpaApiKey?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/sync', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
      ...(gpaApiKey ? { 'X-GPA-API-Key': gpaApiKey } : {}),
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
  gpaApiKey?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/join', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
      ...(gpaApiKey ? { 'X-GPA-API-Key': gpaApiKey } : {}),
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
  gpaApiKey?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/add-to-waitlist', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
      ...(gpaApiKey ? { 'X-GPA-API-Key': gpaApiKey } : {}),
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
  gpaApiKey?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/remove', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
      ...(gpaApiKey ? { 'X-GPA-API-Key': gpaApiKey } : {}),
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
  gpaApiKey?: string,
): Promise<OfficialSelectionSyncResponse> {
  return apiRequest<OfficialSelectionSyncResponse>('/api/official-selection/a02/reorder', {
    method: 'POST',
    headers: {
      ...jsonHeaders(accessToken),
      ...(gpaApiKey ? { 'X-GPA-API-Key': gpaApiKey } : {}),
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
