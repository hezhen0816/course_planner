import SwiftUI
import UserNotifications

struct UserDataUpsertRequest: Encodable {
    let userID: String
    let content: CloudAppDataPayload
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case content
        case updatedAt = "updated_at"
    }
}

@MainActor
final class AppSessionStore: ObservableObject {
    struct CachedScheduleSnapshot: Codable {
        let studentName: String
        let subtitle: String
        let lastSyncedAt: Date?
        let scheduleEntries: [ScheduleEntry]
    }

    struct CachedMoodleAssignmentsSnapshot: Codable {
        let syncedAt: Date?
        let filterLabel: String
        let items: [MoodleAssignmentItem]
    }

    @Published var selectedTab: AppTab = .home
    @Published var schoolAccount: String = "" {
        didSet {
            guard !isRestoringPersistedState else { return }
            queuePlannerSave()
        }
    }
    @Published var schoolPassword: String = "" {
        didSet {
            guard !isRestoringPersistedState else { return }
            queuePlannerSave()
        }
    }
    @Published var reminderMinutes: Int = 10 {
        didSet {
            guard !isRestoringPersistedState else { return }
            queuePlannerSave()
            Task {
                await refreshClassReminders()
            }
        }
    }
    @Published var syncState: ScheduleSyncState = .idle
    @Published var lastSyncedAt: Date?
    @Published var plannerTargets: PlannerTarget = .default
    @Published var plannerSemesters: [PlannerSemester] = []
    @Published var studentName: String = ""
    @Published var subtitle: String = "尚未同步課表"
    @Published var upcomingCourses: [UpcomingCourse]
    @Published var scheduleEntries: [ScheduleEntry]
    @Published var moodleAssignments: [MoodleAssignmentItem]
    @Published var moodleAssignmentsSyncedAt: Date?
    @Published var moodleAssignmentsFilterLabel: String = ""
    @Published var currentUserEmail: String?
    @Published var isAuthenticating = false
    @Published var authErrorMessage: String?
    @Published var authNoticeMessage: String?
    @Published var isBiometricAuthEnabled = false
    @Published var requiresBiometricUnlock = false
    @Published var isBiometricAuthenticating = false
    @Published var biometricAuthErrorMessage: String?
    @Published var historyImportErrorMessage: String?
    @Published var historyImportNoticeMessage: String?
    @Published var reminderErrorMessage: String?
    @Published var reminderNoticeMessage: String?
    @Published var moodleAssignmentsErrorMessage: String?
    @Published var moodleAssignmentsNoticeMessage: String?

    var authSession: SupabaseStoredSession?
    var plannerSaveTask: Task<Void, Never>?
    var isRestoringPersistedState = false

    init() {
        self.upcomingCourses = []
        self.scheduleEntries = []
        self.moodleAssignments = []
        self.moodleAssignmentsSyncedAt = nil
        self.plannerSemesters = Self.blankPlannerSemesters()
        self.studentName = ""
        self.subtitle = "尚未同步課表"
        self.lastSyncedAt = nil
        self.isBiometricAuthEnabled = UserDefaults.standard.bool(forKey: Self.biometricAuthEnabledStorageKey)
        restoreCachedAuthSession()

        if !isAuthConfigured, authSession != nil {
            clearAuthenticatedState()
            authErrorMessage = "尚未完成雲端登入設定"
        } else if let storedSession = authSession, !requiresBiometricUnlock {
            bootstrapAuthenticatedData(forceRefresh: storedSession.expiresAt <= Date().addingTimeInterval(60))
        }
    }

    var isAuthenticated: Bool {
        authSession != nil
    }

    var isAuthConfigured: Bool {
        supabaseURL != nil && supabaseAnonKey != nil
    }

    var shouldUseBiometricUnlock: Bool {
        isAuthenticated && isBiometricAuthEnabled
    }

    var nextUpcomingCourse: UpcomingCourse? {
        todayUpcomingCourses.first
    }

    var orderedUpcomingCourses: [UpcomingCourse] {
        let referenceDate = Date()
        return upcomingCourses.sorted {
            nextOccurrenceDate(for: $0, from: referenceDate) < nextOccurrenceDate(for: $1, from: referenceDate)
        }
    }

    var todayUpcomingCourses: [UpcomingCourse] {
        let now = Date()
        let today = Weekday.currentWeekday(from: now)
        return upcomingCourses
            .filter { $0.weekday == today && !$0.hasEnded(on: now) }
            .sorted { lhs, rhs in
                let lhsStart = lhs.startDate(on: now) ?? now
                let rhsStart = rhs.startDate(on: now) ?? now
                return lhsStart < rhsStart
            }
    }

    var displayName: String {
        let trimmedName = studentName.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedName.isEmpty {
            return trimmedName
        }

        if let currentUserEmail, !currentUserEmail.isEmpty {
            return currentUserEmail
        }

        let trimmedAccount = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedAccount.isEmpty {
            return trimmedAccount
        }

        return "未設定使用者"
    }

    var plannerProgress: PlannerProgress {
        PlannerProgress.calculate(from: plannerSemesters)
    }

    func credits(for semester: PlannerSemester) -> Double {
        semester.courses.reduce(0) { partialResult, course in
            if course.category == .pe {
                return partialResult
            }
            return partialResult + course.credits
        }
    }

    func addCourse(_ course: PlannerCourse, to semesterID: PlannerSemester.ID) {
        guard let index = plannerSemesters.firstIndex(where: { $0.id == semesterID }) else {
            return
        }
        plannerSemesters[index].courses.append(course)
        queuePlannerSave()
    }

    func updateCourse(_ course: PlannerCourse, in semesterID: PlannerSemester.ID) {
        guard let semesterIndex = plannerSemesters.firstIndex(where: { $0.id == semesterID }) else {
            return
        }
        guard let courseIndex = plannerSemesters[semesterIndex].courses.firstIndex(where: { $0.id == course.id }) else {
            return
        }
        plannerSemesters[semesterIndex].courses[courseIndex] = course
        queuePlannerSave()
    }

    func updateTargets(_ targets: PlannerTarget) {
        plannerTargets = targets
        queuePlannerSave()
    }


    static let authSessionStorageKey = "courseplanner.supabase.session"
    static let biometricAuthEnabledStorageKey = "courseplanner.biometricAuth.enabled"
    static let scheduleSnapshotStorageKeyPrefix = "courseplanner.scheduleSnapshot."
    static let moodleAssignmentsStorageKeyPrefix = "courseplanner.moodleAssignments."

    static func iso8601String(from date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: date)
    }

    static func blankPlannerSemesters() -> [PlannerSemester] {
        [
            PlannerSemester(name: "大一上", courses: []),
            PlannerSemester(name: "大一下", courses: []),
            PlannerSemester(name: "大二上", courses: []),
            PlannerSemester(name: "大二下", courses: []),
            PlannerSemester(name: "大三上", courses: []),
            PlannerSemester(name: "大三下", courses: []),
            PlannerSemester(name: "大四上", courses: []),
            PlannerSemester(name: "大四下", courses: [])
        ]
    }

    struct HistoryImportSummary {
        var inserted = 0
        var updated = 0
        var skipped = 0
    }

    static func timeComponents(from timeRange: String) -> DateComponents {
        let startLabel = timeRange
            .components(separatedBy: "-")
            .first?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? "09:00"
        let parts = startLabel.split(separator: ":")
        let hour = Int(parts.first ?? "9") ?? 9
        let minute = Int(parts.dropFirst().first ?? "0") ?? 0
        return DateComponents(hour: hour, minute: minute)
    }

}

extension String {
    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}
