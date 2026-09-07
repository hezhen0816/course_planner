import type { AppData, Course, CourseSearchResult, PendingRequirement } from '../shared/types';
import type { ApiImportPreview, PlanningMode } from '../shared/domain/planner';
import { CourseDetailModal } from '../features/history/CourseDetailModal';
import { OnboardingModal } from './OnboardingModal';
import { OfferingModal } from '../features/planning/OfferingModal';
import { ImportPreviewModal } from '../features/requirements/ImportPreviewModal';
import { SchoolScheduleSyncModal } from '../features/school-sync/SchoolScheduleSyncModal';

type AppModalsProps = {
  activeRequirement: PendingRequirement | null;
  activeSemesterId: string;
  activeSemesterName: string;
  offeringStatus: 'idle' | 'loading' | 'error';
  offeringError: string;
  offeringResults: CourseSearchResult[];
  data: AppData;
  planningMode: PlanningMode;
  importPreview: ApiImportPreview | null;
  isSchoolSyncOpen: boolean;
  schoolSyncMode: 'school-data' | 'official-selection';
  schoolUsername: string;
  schoolPassword: string;
  rememberSchoolCredentials: boolean;
  schoolSyncStatus: 'idle' | 'loading' | 'error' | 'success';
  schoolSyncMessage: string;
  detailCourse: { semesterId: string; semesterName: string; course: Course } | null;
  isOnboardingOpen: boolean;
  onCloseOffering: () => void;
  onScheduleOffering: (offering: CourseSearchResult, force: boolean) => boolean;
  onConfirmImport: () => void;
  onCloseImport: () => void;
  onSchoolUsernameChange: (username: string) => void;
  onSchoolPasswordChange: (password: string) => void;
  onRememberSchoolCredentialsChange: (remember: boolean) => void;
  onCloseSchoolSync: () => void;
  onSyncSchoolData: () => void;
  onCloseCourseDetail: () => void;
  onSaveCourseDetail: (course: Course) => void;
  onCloseOnboarding: () => void;
};

export function AppModals({
  activeRequirement,
  activeSemesterId,
  activeSemesterName,
  offeringStatus,
  offeringError,
  offeringResults,
  data,
  planningMode,
  importPreview,
  isSchoolSyncOpen,
  schoolSyncMode,
  schoolUsername,
  schoolPassword,
  rememberSchoolCredentials,
  schoolSyncStatus,
  schoolSyncMessage,
  detailCourse,
  isOnboardingOpen,
  onCloseOffering,
  onScheduleOffering,
  onConfirmImport,
  onCloseImport,
  onSchoolUsernameChange,
  onSchoolPasswordChange,
  onRememberSchoolCredentialsChange,
  onCloseSchoolSync,
  onSyncSchoolData,
  onCloseCourseDetail,
  onSaveCourseDetail,
  onCloseOnboarding,
}: AppModalsProps) {
  return (
    <>
      {activeRequirement && (
        <OfferingModal
          requirement={activeRequirement}
          semesterName={activeSemesterName}
          status={offeringStatus}
          error={offeringError}
          offerings={offeringResults}
          data={data}
          activeSemesterId={activeSemesterId}
          planningMode={planningMode}
          onClose={onCloseOffering}
          onSchedule={onScheduleOffering}
        />
      )}

      {importPreview && (
        <ImportPreviewModal preview={importPreview} onConfirm={onConfirmImport} onClose={onCloseImport} />
      )}

      {isSchoolSyncOpen && (
        <SchoolScheduleSyncModal
          mode={schoolSyncMode}
          username={schoolUsername}
          password={schoolPassword}
          rememberCredentials={rememberSchoolCredentials}
          status={schoolSyncStatus}
          message={schoolSyncMessage}
          onUsernameChange={onSchoolUsernameChange}
          onPasswordChange={onSchoolPasswordChange}
          onRememberCredentialsChange={onRememberSchoolCredentialsChange}
          onClose={onCloseSchoolSync}
          onImport={onSyncSchoolData}
        />
      )}

      {detailCourse && (
        <CourseDetailModal
          isOpen
          course={detailCourse.course}
          semesterId={detailCourse.semesterId}
          semesterName={detailCourse.semesterName}
          recognitionRequirements={data.pendingRequirements}
          onClose={onCloseCourseDetail}
          onSave={onSaveCourseDetail}
        />
      )}

      {isOnboardingOpen && (
        <OnboardingModal isOpen={isOnboardingOpen} onClose={onCloseOnboarding} />
      )}
    </>
  );
}
