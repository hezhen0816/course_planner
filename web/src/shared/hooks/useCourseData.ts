import { useEffect, useMemo, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '../supabase';
import type { AcademicHistoryRecord, AppData, Course, PendingRequirement, RequirementSet, SelectionPlan } from '../types';
import { INITIAL_SEMESTERS, DEFAULT_TARGETS } from '../constants';

function normalizeCourse(course: Course): Course {
  return {
    ...course,
    program: course.program ?? 'home',
    scheduledOffering: course.scheduledOffering
      ? {
          ...course.scheduledOffering,
          slots: course.scheduledOffering.slots || parseNodeSlots(course.scheduledOffering.node),
        }
      : undefined,
  };
}

function normalizeRequirementSet(set: RequirementSet): RequirementSet {
  return {
    ...set,
    source: set.source ?? 'manual',
    notes: set.notes || [],
  };
}

function normalizeRequirement(requirement: PendingRequirement): PendingRequirement {
  return {
    ...requirement,
    kind: requirement.kind ?? 'course',
    courseNames: requirement.courseNames || [],
    options: requirement.options || [],
    note: requirement.note || '',
  };
}

function normalizeHistoryRecord(record: AcademicHistoryRecord): AcademicHistoryRecord {
  return {
    ...record,
    category: record.category || '',
    courseCode: record.courseCode || '',
    courseName: record.courseName || '',
    academicTerm: record.academicTerm || '',
    grade: record.grade || '',
    credits: Number.isFinite(record.credits) ? record.credits : 0,
    status: record.status || 'passed',
    dimension: record.dimension || undefined,
  };
}

function normalizeSelectionPlan(plan: SelectionPlan | undefined): SelectionPlan | undefined {
  if (!plan) return undefined;
  const officialSelectionCache = plan.officialSelectionCache
    ? { ...plan.officialSelectionCache, session_valid: false }
    : undefined;
  return {
    targetAcademicTerm: plan.targetAcademicTerm || '',
    targetLabel: plan.targetLabel || '',
    courses: (plan.courses || []).map(normalizeCourse),
    officialSelectionCache,
    updatedAt: plan.updatedAt || undefined,
  };
}

type StoredAppData = Partial<AppData> & Record<string, unknown>;

function normalizeAppData(rawData: StoredAppData): AppData {
  return {
    ...rawData,
    schemaVersion: 2,
    semesters: (rawData.semesters || INITIAL_SEMESTERS).map((semester) => ({
      ...semester,
      courses: (semester.courses || []).map(normalizeCourse),
    })),
    targets: {
      ...DEFAULT_TARGETS,
      ...(rawData.targets || {}),
    },
    selectionPlan: normalizeSelectionPlan(rawData.selectionPlan),
    requirementSets: (rawData.requirementSets || []).map(normalizeRequirementSet),
    pendingRequirements: (rawData.pendingRequirements || []).map(normalizeRequirement),
    historyRecords: (rawData.historyRecords || []).map(normalizeHistoryRecord),
  };
}

function createEmptyAppData(): AppData {
  return normalizeAppData({
    schemaVersion: 2,
    semesters: INITIAL_SEMESTERS,
    targets: { ...DEFAULT_TARGETS },
    settings: {},
    selectionPlan: undefined,
    requirementSets: [],
    pendingRequirements: [],
    historyRecords: [],
  });
}

function parseNodeSlots(node: string): string[] {
  return (node || '')
    .split(/[,、\s]+/)
    .map((slot) => slot.trim().toUpperCase())
    .filter(Boolean);
}

type UserDataRecord = {
  content: StoredAppData;
};

export function useCourseData(session: Session | null) {
  const [data, setData] = useState<AppData>(() => createEmptyAppData());
  const [syncStatus, setSyncStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [loadedUserID, setLoadedUserID] = useState<string | null>(null);
  const userID = session?.user.id ?? null;

  const isLoading = useMemo(() => {
    if (!supabase || !userID) {
      return false;
    }
    return loadedUserID != userID;
  }, [loadedUserID, userID]);

  useEffect(() => {
    if (!userID || !supabase) {
      return;
    }

    const client = supabase;
    let isActive = true;

    const loadUserData = async () => {
      const result = await client
        .from('user_data')
        .select('content')
        .eq('user_id', userID)
        .maybeSingle();

      if (!isActive) {
        return;
      }

      if (result.error) {
        console.error('Error loading data:', result.error);
      }

      const userData = result.data as UserDataRecord | null;
      if (userData?.content) {
        setData(normalizeAppData(userData.content));
      } else {
        setData(createEmptyAppData());
      }
      setLoadedUserID(userID);
      setSyncStatus('idle');
    };

    void loadUserData();

    return () => {
      isActive = false;
    };
  }, [userID]);

  useEffect(() => {
    if (!userID || !supabase || loadedUserID !== userID) {
      return;
    }

    const client = supabase;
    let isActive = true;
    let resetStatusTimer: ReturnType<typeof window.setTimeout> | undefined;
    const saveTimer = window.setTimeout(async () => {
      setSyncStatus('saving');

      const normalizedData = normalizeAppData(data);
      const { error } = await client
        .from('user_data')
        .upsert(
          [{
            user_id: userID,
            content: normalizedData,
            content_version: 2,
            last_writer: 'web',
            updated_at: new Date().toISOString(),
          }],
          { onConflict: 'user_id' }
        );

      if (!isActive) {
        return;
      }

      if (error) {
        console.error('Error saving data:', error);
        setSyncStatus('error');
        return;
      }

      setSyncStatus('saved');
      resetStatusTimer = window.setTimeout(() => {
        if (isActive) {
          setSyncStatus('idle');
        }
      }, 2000);
    }, 2000);

    return () => {
      isActive = false;
      window.clearTimeout(saveTimer);
      if (resetStatusTimer) {
        window.clearTimeout(resetStatusTimer);
      }
    };
  }, [data, loadedUserID, userID]);

  return { data, setData, syncStatus, isLoading };
}
