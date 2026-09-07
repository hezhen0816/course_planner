import { useEffect, useMemo, useState } from 'react';
import { fetchCourseSemesters, searchCourses } from '../../shared/api';
import type { CourseSearchResult, CourseSemesterInfo, GpaApiSettings } from '../../shared/types';
import { parseCourseDepartment } from '../../shared/domain/courseDepartments';
import {
  type CapacityFilter,
  type ManualSearchSummary,
  type SearchMode,
  capacityLabel,
  capacityStatus,
  displayClassroom,
  displaySlots,
  formatCredits,
  parseNodeSlots,
} from '../../shared/domain/planner';

function formatGpa(offering: CourseSearchResult): string {
  if (typeof offering.gpa === 'number' && Number.isFinite(offering.gpa)) return offering.gpa.toFixed(2);
  if (offering.gpa_status === 'no_data') return '查無資料';
  if (offering.gpa_status === 'error') return '錯誤';
  return '未啟用';
}

function normalizeCourseName(name: string): string {
  return name
    .replace(/[（）]/g, (match) => (match === '（' ? '(' : ')'))
    .replace(/\s+/g, '')
    .trim();
}

function splitCourseNameQueries(query: string): string[] {
  return query
    .split(/[／/、,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function useCourseSearch(gpaApiSettings?: GpaApiSettings) {
  const [querySemester, setQuerySemester] = useState('1142');
  const [courseSemesters, setCourseSemesters] = useState<CourseSemesterInfo[]>([]);
  const [manualQuery, setManualQuery] = useState('');
  const [manualMode, setManualMode] = useState<SearchMode>('name');
  const [exactCourseNameSearch, setExactCourseNameSearch] = useState(false);
  // Off by default: 台大/師大 cross-school sections are rarely selectable, so
  // they only appear when explicitly requested (matches the school site's list).
  const [includeCrossSchool, setIncludeCrossSchool] = useState(false);
  const [manualResults, setManualResults] = useState<CourseSearchResult[]>([]);
  const [manualStatus, setManualStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [manualError, setManualError] = useState('');
  const [manualSearchSummary, setManualSearchSummary] = useState<ManualSearchSummary | null>(null);
  const [teacherFilter, setTeacherFilter] = useState('');
  const [creditFilter, setCreditFilter] = useState('all');
  const [requireOptionFilter, setRequireOptionFilter] = useState('all');
  const [timeFilter, setTimeFilter] = useState('');
  const [capacityFilter, setCapacityFilter] = useState<CapacityFilter>('all');

  useEffect(() => {
    let isActive = true;
    fetchCourseSemesters()
      .then((semesters) => {
        if (!isActive) return;
        setCourseSemesters(semesters);
        const current = semesters.find((semester) => semester.current) || semesters[0];
        if (current?.semester) setQuerySemester(current.semester);
      })
      .catch(() => {
        if (isActive) setCourseSemesters([]);
      });
    return () => {
      isActive = false;
    };
  }, []);

  const canRunManualSearch = manualQuery.trim().length > 0 && manualStatus !== 'loading';
  const currentCourseSemester = courseSemesters.find((semester) => semester.semester === querySemester);
  const currentCourseSemesterLabel = currentCourseSemester?.english_label
    ? `${querySemester}・${currentCourseSemester.english_label}`
    : querySemester;

  const filteredManualResults = useMemo(() => {
    const teacher = teacherFilter.trim().toLowerCase();
    const time = timeFilter.trim().toUpperCase();
    return manualResults.filter((offering) => {
      if (teacher && !offering.teacher.toLowerCase().includes(teacher)) return false;
      if (creditFilter !== 'all' && String(offering.credits ?? '') !== creditFilter) return false;
      if (requireOptionFilter !== 'all' && offering.require_option !== requireOptionFilter) return false;
      if (time && !offering.node.toUpperCase().includes(time)) return false;
      if (capacityFilter !== 'all' && capacityStatus(offering) !== capacityFilter) return false;
      return true;
    });
  }, [capacityFilter, creditFilter, manualResults, requireOptionFilter, teacherFilter, timeFilter]);

  const resetCourseSearchResults = () => {
    setManualResults([]);
    setManualSearchSummary(null);
  };

  const handleQuerySemesterChange = (semester: string) => {
    setQuerySemester(semester);
    resetCourseSearchResults();
  };

  const handleManualModeChange = (mode: SearchMode) => {
    setManualMode(mode);
    if (mode === 'code') setExactCourseNameSearch(false);
    resetCourseSearchResults();
  };

  const runManualSearch = async (override?: { query?: string; queries?: string[]; mode?: SearchMode }) => {
    const overrideQueries = override?.queries
      ?.map((item) => item.trim())
      .filter(Boolean);
    const rawQuery = (override?.query ?? manualQuery).trim();
    const mode = override?.mode ?? manualMode;
    const queries = overrideQueries && overrideQueries.length > 0
      ? overrideQueries
      : mode === 'name' && exactCourseNameSearch
        ? splitCourseNameQueries(rawQuery)
        : undefined;
    const query = (queries && queries.length > 0 ? queries.join(' / ') : rawQuery).trim();
    if (!query) return;
    setManualStatus('loading');
    setManualError('');
    try {
      const gpaApiKey = gpaApiSettings?.enabled ? gpaApiSettings.apiKey.trim() : '';
      const searchQueries = queries && queries.length > 0 ? queries : [query];
      const resultGroups = await Promise.all(
        searchQueries.map((searchQuery) => searchCourses(querySemester, searchQuery, mode, gpaApiKey || undefined, includeCrossSchool)),
      );
      const seen = new Set<string>();
      const exactNames = mode === 'name' && exactCourseNameSearch
        ? new Set(searchQueries.map(normalizeCourseName))
        : null;
      const results = resultGroups.flat().filter((offering) => {
        if (exactNames && !exactNames.has(normalizeCourseName(offering.course_name))) return false;
        const key = [
          offering.course_no.trim().toUpperCase(),
          offering.course_name.trim(),
          offering.teacher.trim(),
          offering.node.trim(),
        ].join('|');
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      setManualResults(results);
      setManualSearchSummary({
        query,
        mode,
        semester: querySemester,
        resultCount: results.length,
      });
      setManualStatus('idle');
    } catch (error) {
      setManualStatus('error');
      setManualError(error instanceof Error ? error.message : '課程查詢失敗');
    }
  };

  const resetCourseSearchFilters = () => {
    setManualQuery('');
    setExactCourseNameSearch(false);
    setIncludeCrossSchool(false);
    setTeacherFilter('');
    setCreditFilter('all');
    setRequireOptionFilter('all');
    setTimeFilter('');
    setCapacityFilter('all');
    setManualResults([]);
    setManualSearchSummary(null);
    setManualError('');
    setManualStatus('idle');
  };

  const exportCourseResults = () => {
    if (filteredManualResults.length === 0) return;
    const headers = ['課碼', '開課系所', '課名', '教師', '學分', 'GPA', '節次', '教室', '名額', '備註'];
    const escapeCell = (value: string | number | null | undefined) => `"${String(value ?? '').replace(/"/g, '""')}"`;
    const rows = filteredManualResults.map((offering) => [
      offering.course_no,
      parseCourseDepartment(offering.course_no)?.name || '',
      offering.course_name,
      offering.teacher,
      formatCredits(offering.credits),
      formatGpa(offering),
      displaySlots(parseNodeSlots(offering.node)),
      displayClassroom(offering.classroom),
      capacityLabel(offering),
      offering.contents,
    ]);
    const csv = [headers, ...rows].map((row) => row.map(escapeCell).join(',')).join('\n');
    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `course-results-${querySemester}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return {
    courseSemesters,
    querySemester,
    currentCourseSemesterLabel,
    manualMode,
    manualQuery,
    exactCourseNameSearch,
    includeCrossSchool,
    manualStatus,
    manualError,
    manualSearchSummary,
    manualResults,
    filteredManualResults,
    teacherFilter,
    creditFilter,
    requireOptionFilter,
    timeFilter,
    capacityFilter,
    canRunManualSearch,
    setManualQuery,
    setExactCourseNameSearch,
    setIncludeCrossSchool,
    setTeacherFilter,
    setCreditFilter,
    setRequireOptionFilter,
    setTimeFilter,
    setCapacityFilter,
    handleQuerySemesterChange,
    handleManualModeChange,
    runManualSearch,
    resetCourseSearchFilters,
    exportCourseResults,
  };
}
