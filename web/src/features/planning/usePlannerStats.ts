import { useMemo } from 'react';
import type { AppData, PlannerStats } from '../../shared/types';
import {
  categoryFromHistoryRecord,
  isFailedImportedHistoryCourse,
  normalizeName,
} from '../../shared/domain/planner';

export function usePlannerStats(data: AppData): PlannerStats {
  return useMemo<PlannerStats>(() => {
    const current: PlannerStats = {
      total: 0,
      chinese: 0,
      english: 0,
      gen_ed: 0,
      pe_semesters: 0,
      social: 0,
      homeCompulsory: 0,
      homeElective: 0,
      doubleMajor: 0,
      minor: 0,
      genEdDimensions: new Set<string>(),
    };

    const countedHistoryNames = new Set<string>();
    (data.historyRecords || []).forEach((record) => {
      if (record.status === 'failed') return;
      countedHistoryNames.add(normalizeName(record.courseName));
      const category = categoryFromHistoryRecord(record);
      const credits = Number.isFinite(record.credits) ? record.credits : 0;
      if (category === 'pe') {
        current.pe_semesters += 1;
        return;
      }
      if (category === 'social') {
        current.social += 1;
        return;
      }
      current.total += credits;
      if (category === 'chinese') current.chinese += credits;
      if (category === 'english') current.english += credits;
      if (category === 'gen_ed') {
        current.gen_ed += credits;
        if (record.dimension && record.dimension !== 'None') current.genEdDimensions.add(record.dimension);
      }
      if (category === 'compulsory') current.homeCompulsory += credits;
      if (category === 'elective') current.homeElective += credits;
    });

    const semesterLikeSources = [
      ...data.semesters,
      ...(data.selectionPlan?.courses.length
        ? [{ id: '__selection_plan__', name: data.selectionPlan.targetLabel || '未來規劃', courses: data.selectionPlan.courses }]
        : []),
    ];

    semesterLikeSources.forEach((semester) => {
      let hasPE = false;
      semester.courses.forEach((course) => {
        if (isFailedImportedHistoryCourse(course)) return;
        if (countedHistoryNames.has(normalizeName(course.name))) return;
        const credits = Number.isFinite(course.credits) ? course.credits : 0;
        const program = course.program ?? 'home';
        if (course.category === 'pe') {
          hasPE = true;
          return;
        }
        if (course.category === 'social') {
          current.social += 1;
          return;
        }
        current.total += credits;
        if (course.category === 'chinese') current.chinese += credits;
        if (course.category === 'english') current.english += credits;
        if (course.category === 'gen_ed') {
          current.gen_ed += credits;
          if (course.dimension && course.dimension !== 'None') current.genEdDimensions.add(course.dimension);
        }
        if (program === 'double_major') current.doubleMajor += credits;
        if (program === 'minor') current.minor += credits;
        if (program === 'home' && course.category === 'compulsory') current.homeCompulsory += credits;
        if (program === 'home' && course.category === 'elective') current.homeElective += credits;
      });
      if (hasPE) current.pe_semesters += 1;
    });

    return current;
  }, [data]);
}
