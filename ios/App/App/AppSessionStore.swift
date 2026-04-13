import SwiftUI
import UserNotifications

private struct UserDataUpsertRequest: Encodable {
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
    private struct CachedScheduleSnapshot: Codable {
        let studentName: String
        let subtitle: String
        let lastSyncedAt: Date?
        let scheduleEntries: [ScheduleEntry]
    }

    private struct CachedMoodleAssignmentsSnapshot: Codable {
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
    @Published var historyImportErrorMessage: String?
    @Published var historyImportNoticeMessage: String?
    @Published var reminderErrorMessage: String?
    @Published var reminderNoticeMessage: String?
    @Published var moodleAssignmentsErrorMessage: String?
    @Published var moodleAssignmentsNoticeMessage: String?

    private var authSession: SupabaseStoredSession?
    private var plannerSaveTask: Task<Void, Never>?
    private var isRestoringPersistedState = false

    init() {
        self.upcomingCourses = []
        self.scheduleEntries = []
        self.moodleAssignments = []
        self.moodleAssignmentsSyncedAt = nil
        self.plannerSemesters = Self.blankPlannerSemesters()
        self.studentName = ""
        self.subtitle = "尚未同步課表"
        self.lastSyncedAt = nil
        restoreCachedAuthSession()

        if !isAuthConfigured, authSession != nil {
            clearAuthenticatedState()
            authErrorMessage = "尚未完成雲端登入設定"
        } else if let storedSession = authSession {
            bootstrapAuthenticatedData(forceRefresh: storedSession.expiresAt <= Date().addingTimeInterval(60))
        }
    }

    var isAuthenticated: Bool {
        authSession != nil
    }

    var isAuthConfigured: Bool {
        supabaseURL != nil && supabaseAnonKey != nil
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

    func signIn(email: String, password: String) async {
        guard isAuthConfigured else {
            authErrorMessage = "尚未完成雲端登入設定"
            return
        }

        let normalizedEmail = email.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedEmail.isEmpty, !password.isEmpty else {
            authErrorMessage = "請輸入 Email 與密碼"
            return
        }

        isAuthenticating = true
        authErrorMessage = nil
        authNoticeMessage = nil

        do {
            let endpoint = try makeURL(path: "/auth/v1/token?grant_type=password")
            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            applyAPIHeaders(to: &request)
            request.httpBody = try JSONSerialization.data(withJSONObject: [
                "email": normalizedEmail,
                "password": password
            ])

            let payload: SupabaseAuthSessionResponse = try await performJSONRequest(request)
            try await establishAuthenticatedSession(from: payload, fallbackEmail: normalizedEmail)
        } catch {
            authErrorMessage = error.localizedDescription
        }

        isAuthenticating = false
    }

    func signUp(email: String, password: String) async {
        guard isAuthConfigured else {
            authErrorMessage = "尚未完成雲端登入設定"
            return
        }

        let normalizedEmail = email.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedEmail.isEmpty, !password.isEmpty else {
            authErrorMessage = "請輸入 Email 與密碼"
            return
        }

        isAuthenticating = true
        authErrorMessage = nil
        authNoticeMessage = nil

        do {
            let endpoint = try makeURL(path: "/auth/v1/signup")
            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            applyAPIHeaders(to: &request)
            request.httpBody = try JSONSerialization.data(withJSONObject: [
                "email": normalizedEmail,
                "password": password
            ])

            let payload: SupabaseAuthSessionResponse = try await performJSONRequest(request)
            if payload.accessToken != nil {
                try await establishAuthenticatedSession(from: payload, fallbackEmail: normalizedEmail)
                authNoticeMessage = "註冊成功，已直接登入"
            } else {
                authNoticeMessage = "註冊成功，請先完成信箱驗證後再登入"
            }
        } catch {
            authErrorMessage = error.localizedDescription
        }

        isAuthenticating = false
    }

    func signOut() async {
        plannerSaveTask?.cancel()

        if authSession != nil {
            do {
                let session = try await validSession(forceRefresh: false)
                let endpoint = try makeURL(path: "/auth/v1/logout")
                var request = URLRequest(url: endpoint)
                request.httpMethod = "POST"
                applyAPIHeaders(to: &request)
                request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
                _ = try await URLSession.shared.data(for: request)
            } catch {
                // Ignore remote logout failures and clear the local session anyway.
            }
        }

        clearAuthenticatedState()
    }

    func refreshAppContent(suppressErrors: Bool = true) async {
        guard isAuthenticated else {
            return
        }

        do {
            _ = try await validSession(forceRefresh: false)
            await loadPlannerData(preserveExistingStateOnFailure: true)

            if !schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                await loadLatestScheduleSnapshot(suppressErrors: suppressErrors)
                await loadLatestMoodleAssignments(suppressErrors: suppressErrors)
            }
        } catch {
            clearAuthenticatedState()
            authErrorMessage = "登入已失效，請重新登入"
        }
    }

    func refreshHomeContent() async {
        guard isAuthenticated else {
            return
        }

        await refreshAppContent(suppressErrors: false)

        let username = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        let password = schoolPassword.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !username.isEmpty, !password.isEmpty else {
            return
        }

        await syncMoodleAssignments()
    }

    func syncSchedule() async {
        let username = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        let password = schoolPassword.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !username.isEmpty, !password.isEmpty else {
            syncState = .failed("請先輸入學校帳號與密碼")
            return
        }

        let endpoint = URL(string: "\(Self.backendServiceBaseURL)/api/schedule/sync")!

        syncState = .syncing

        do {
            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(
                ScheduleSyncRequest(
                    username: username,
                    password: password,
                    profileKey: username,
                    persistToSupabase: true,
                    verifySSL: false
                )
            )

            let (data, response) = try await URLSession.shared.data(for: request)
            try validateHTTPResponse(response, data: data)

            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let payload = try decoder.decode(ScheduleSyncResponse.self, from: data)
            apply(payload: payload)
            syncState = .synced
        } catch {
            syncState = .failed(error.localizedDescription)
        }
    }

    func loadLatestScheduleSnapshot(suppressErrors: Bool = false) async {
        let profileKey = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !profileKey.isEmpty else {
            if !suppressErrors {
                syncState = .failed("缺少學號，無法更新課表")
            }
            return
        }

        let endpoint = URL(string: "\(Self.backendServiceBaseURL)/api/schedule/\(profileKey.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? profileKey)")!

        if !suppressErrors {
            syncState = .syncing
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: endpoint)
            try validateHTTPResponse(response, data: data)

            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let payload = try decoder.decode(ScheduleSyncResponse.self, from: data)
            apply(payload: payload)
            syncState = .synced
        } catch {
            if let nsError = error as NSError?, nsError.code == 404 {
                clearScheduleState()
            }
            if !suppressErrors {
                syncState = .failed(error.localizedDescription)
            }
        }
    }

    func importAcademicHistory() async {
        let username = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        let password = schoolPassword.trimmingCharacters(in: .whitespacesAndNewlines)
        historyImportErrorMessage = nil
        historyImportNoticeMessage = nil

        guard !username.isEmpty, !password.isEmpty else {
            historyImportErrorMessage = "請先輸入學校帳號與密碼"
            return
        }

        let endpoint = URL(string: "\(Self.backendServiceBaseURL)/api/history/import")!

        do {
            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(
                HistoryImportRequest(
                    username: username,
                    password: password,
                    profileKey: username,
                    persistToSupabase: true,
                    verifySSL: false
                )
            )

            let (data, response) = try await URLSession.shared.data(for: request)
            try validateHTTPResponse(response, data: data)

            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let payload = try decoder.decode(HistoryImportResponse.self, from: data)

            if let payloadStudentName = payload.studentName?.trimmingCharacters(in: .whitespacesAndNewlines), !payloadStudentName.isEmpty {
                studentName = payloadStudentName.replacingOccurrences(of: "姓名：", with: "")
            }

            let summary = mergeImportedHistory(
                payload.records,
                studentNumber: payload.studentNo ?? username
            )
            try await persistPlannerData()

            historyImportNoticeMessage = [
                "已匯入 \(payload.recordCount) 筆歷史修課紀錄",
                "新增 \(summary.inserted) 筆",
                "更新 \(summary.updated) 筆",
                "略過 \(summary.skipped) 筆",
            ].joined(separator: "・")
        } catch {
            historyImportErrorMessage = error.localizedDescription
        }
    }

    func syncMoodleAssignments() async {
        let username = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        let password = schoolPassword.trimmingCharacters(in: .whitespacesAndNewlines)
        moodleAssignmentsErrorMessage = nil
        moodleAssignmentsNoticeMessage = nil

        guard !username.isEmpty, !password.isEmpty else {
            moodleAssignmentsErrorMessage = "請先輸入學校帳號與密碼"
            return
        }

        let endpoint = URL(string: "\(Self.backendServiceBaseURL)/api/moodle/assignments/sync")!

        do {
            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(
                MoodleAssignmentsRequest(
                    username: username,
                    password: password,
                    profileKey: username,
                    persistToSupabase: true,
                    verifySSL: false
                )
            )

            let (data, response) = try await URLSession.shared.data(for: request)
            try validateHTTPResponse(response, data: data)

            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let payload = try decoder.decode(MoodleAssignmentsResponse.self, from: data)
            apply(payload: payload)
        } catch {
            moodleAssignmentsErrorMessage = friendlyMoodleAssignmentsErrorMessage(for: error)
        }
    }

    func loadLatestMoodleAssignments(suppressErrors: Bool = false) async {
        let profileKey = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !profileKey.isEmpty else {
            return
        }

        let endpoint = URL(string: "\(Self.backendServiceBaseURL)/api/moodle/assignments/\(profileKey.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? profileKey)")!

        do {
            let (data, response) = try await URLSession.shared.data(from: endpoint)
            try validateHTTPResponse(response, data: data)

            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let payload = try decoder.decode(MoodleAssignmentsResponse.self, from: data)
            apply(payload: payload)
        } catch {
            if let nsError = error as NSError?, nsError.code == 404 {
                clearMoodleAssignmentsState()
                moodleAssignmentsErrorMessage = nil
                return
            }
            if !suppressErrors {
                moodleAssignmentsErrorMessage = friendlyMoodleAssignmentsErrorMessage(for: error)
            }
        }
    }

    private func restoreCachedAuthSession() {
        guard
            let sessionData = UserDefaults.standard.data(forKey: Self.authSessionStorageKey),
            let storedSession = try? JSONDecoder().decode(SupabaseStoredSession.self, from: sessionData)
        else {
            return
        }

        authSession = storedSession
        currentUserEmail = storedSession.email
        restoreCachedScheduleSnapshot(for: storedSession)
        restoreCachedMoodleAssignmentsSnapshot(for: storedSession)
    }

    private func establishAuthenticatedSession(from payload: SupabaseAuthSessionResponse, fallbackEmail: String) async throws {
        guard
            let accessToken = payload.accessToken,
            let refreshToken = payload.refreshToken,
            let user = payload.user
        else {
            throw NSError(domain: "CoursePlannerAuth", code: 1, userInfo: [
                NSLocalizedDescriptionKey: "雲端登入沒有回傳可用的 session"
            ])
        }

        let expiresAt: Date
        if let epoch = payload.expiresAt {
            expiresAt = Date(timeIntervalSince1970: epoch)
        } else if let expiresIn = payload.expiresIn {
            expiresAt = Date().addingTimeInterval(TimeInterval(expiresIn))
        } else {
            expiresAt = Date().addingTimeInterval(3600)
        }

        let storedSession = SupabaseStoredSession(
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresAt: expiresAt,
            userID: user.id,
            email: user.email ?? fallbackEmail
        )

        authSession = storedSession
        currentUserEmail = storedSession.email
        authErrorMessage = nil
        subtitle = "尚未同步課表"
        persistAuthSession(storedSession)
        restoreCachedScheduleSnapshot(for: storedSession)
        restoreCachedMoodleAssignmentsSnapshot(for: storedSession)
        bootstrapAuthenticatedData(forceRefresh: false)
    }

    private func bootstrapAuthenticatedData(forceRefresh: Bool) {
        Task { @MainActor in
            do {
                _ = try await validSession(forceRefresh: forceRefresh)
                await loadPlannerData(preserveExistingStateOnFailure: true)
                if !schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    await loadLatestScheduleSnapshot(suppressErrors: true)
                    await loadLatestMoodleAssignments(suppressErrors: true)
                }
            } catch {
                clearAuthenticatedState()
                authErrorMessage = "登入已失效，請重新登入"
            }
        }
    }

    private func loadPlannerData(preserveExistingStateOnFailure: Bool = true) async {
        guard isAuthenticated else {
            return
        }

        do {
            let session = try await validSession()
            let queryUserID = session.userID.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? session.userID
            let endpoint = try makeURL(path: "/rest/v1/user_data?select=content&user_id=eq.\(queryUserID)")
            var request = URLRequest(url: endpoint)
            request.httpMethod = "GET"
            applyAPIHeaders(to: &request)
            request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

            let (data, response) = try await URLSession.shared.data(for: request)
            try validateHTTPResponse(response, data: data)

            let decoder = JSONDecoder()
            let records = try decoder.decode([CloudUserDataRecord].self, from: data)
            if let record = records.first {
                applyPlannerPayload(record.content)
                authNoticeMessage = "已載入你的規劃資料"
            } else {
                resetCloudBackedState()
                authNoticeMessage = "已登入，可以開始建立你的規劃"
            }
        } catch {
            if !preserveExistingStateOnFailure {
                resetCloudBackedState()
            }
            authErrorMessage = "讀取雲端資料失敗：\(error.localizedDescription)"
        }
    }

    private func queuePlannerSave() {
        guard isAuthenticated else {
            return
        }

        plannerSaveTask?.cancel()
        plannerSaveTask = Task {
            try? await Task.sleep(for: .seconds(2))
            guard !Task.isCancelled else {
                return
            }
            await savePlannerData()
        }
    }

    private func savePlannerData() async {
        guard isAuthenticated else {
            return
        }

        do {
            try await persistPlannerData()
            authNoticeMessage = "規劃資料已保存到雲端"
        } catch {
            authErrorMessage = "保存雲端資料失敗：\(error.localizedDescription)"
        }
    }

    private func persistPlannerData() async throws {
        let session = try await validSession()
        let endpoint = try makeURL(path: "/rest/v1/user_data?on_conflict=user_id")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("resolution=merge-duplicates,return=minimal", forHTTPHeaderField: "Prefer")
        applyAPIHeaders(to: &request)
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

        let payload = cloudAppDataPayload()
        let body = [
            UserDataUpsertRequest(
                userID: session.userID,
                content: payload,
                updatedAt: Self.iso8601String(from: Date())
            )
        ]
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.withoutEscapingSlashes]
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        try validateHTTPResponse(response, data: data)
    }

    private func validSession(forceRefresh: Bool = false) async throws -> SupabaseStoredSession {
        guard let currentSession = authSession else {
            throw NSError(domain: "CoursePlannerAuth", code: 2, userInfo: [
                NSLocalizedDescriptionKey: "尚未登入"
            ])
        }

        if forceRefresh || currentSession.expiresAt <= Date().addingTimeInterval(60) {
            return try await refreshSession(using: currentSession)
        }

        return currentSession
    }

    private func refreshSession(using currentSession: SupabaseStoredSession) async throws -> SupabaseStoredSession {
        let endpoint = try makeURL(path: "/auth/v1/token?grant_type=refresh_token")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyAPIHeaders(to: &request)
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "refresh_token": currentSession.refreshToken
        ])

        let payload: SupabaseAuthSessionResponse = try await performJSONRequest(request)
        guard
            let accessToken = payload.accessToken,
            let refreshToken = payload.refreshToken
        else {
            throw NSError(domain: "CoursePlannerAuth", code: 3, userInfo: [
                NSLocalizedDescriptionKey: "無法刷新登入 session"
            ])
        }

        let expiresAt: Date
        if let epoch = payload.expiresAt {
            expiresAt = Date(timeIntervalSince1970: epoch)
        } else if let expiresIn = payload.expiresIn {
            expiresAt = Date().addingTimeInterval(TimeInterval(expiresIn))
        } else {
            expiresAt = Date().addingTimeInterval(3600)
        }

        let refreshedSession = SupabaseStoredSession(
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresAt: expiresAt,
            userID: payload.user?.id ?? currentSession.userID,
            email: payload.user?.email ?? currentSession.email
        )

        authSession = refreshedSession
        currentUserEmail = refreshedSession.email
        persistAuthSession(refreshedSession)
        return refreshedSession
    }

    private func cloudAppDataPayload() -> CloudAppDataPayload {
        CloudAppDataPayload(
            semesters: plannerSemesters.map { semester in
                CloudSemester(
                    id: semester.id.uuidString,
                    name: semester.name,
                    courses: semester.courses.map { course in
                        CloudCourse(
                            id: course.id.uuidString,
                            name: course.name,
                            credits: course.credits,
                            category: cloudCategory(for: course.category),
                            program: cloudProgram(for: course.program),
                            dimension: cloudDimension(for: course.dimension),
                            details: CloudCourseDetails(
                                professor: course.instructor.isEmpty ? nil : course.instructor,
                                email: nil,
                                location: course.location.isEmpty ? nil : course.location,
                                time: course.time.isEmpty ? nil : course.time,
                                link: nil,
                                gradingPolicy: [],
                                notes: course.notes.isEmpty ? nil : course.notes
                            )
                        )
                    }
                )
            },
            targets: CloudTargets(
                total: plannerTargets.total,
                chinese: plannerTargets.chinese,
                english: plannerTargets.english,
                genEd: plannerTargets.genEd,
                peSemesters: plannerTargets.peSemesters,
                social: plannerTargets.social,
                homeCompulsory: plannerTargets.homeCompulsory,
                homeElective: plannerTargets.homeElective,
                doubleMajor: plannerTargets.doubleMajor,
                minor: plannerTargets.minor
            ),
            settings: CloudUserSettings(
                schoolAccount: schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty,
                schoolPassword: schoolPassword.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty,
                reminderMinutes: reminderMinutes
            )
        )
    }

    private func applyPlannerPayload(_ payload: CloudAppDataPayload) {
        applyCloudSettings(payload.settings)

        let targets = payload.targets
        plannerTargets = PlannerTarget(
            total: targets?.total ?? PlannerTarget.default.total,
            chinese: targets?.chinese ?? PlannerTarget.default.chinese,
            english: targets?.english ?? PlannerTarget.default.english,
            genEd: targets?.genEd ?? PlannerTarget.default.genEd,
            peSemesters: targets?.peSemesters ?? PlannerTarget.default.peSemesters,
            social: targets?.social ?? PlannerTarget.default.social,
            homeCompulsory: targets?.homeCompulsory ?? PlannerTarget.default.homeCompulsory,
            homeElective: targets?.homeElective ?? PlannerTarget.default.homeElective,
            doubleMajor: targets?.doubleMajor ?? PlannerTarget.default.doubleMajor,
            minor: targets?.minor ?? PlannerTarget.default.minor
        )

        let semesters = (payload.semesters ?? []).map { semester in
            PlannerSemester(
                id: UUID(uuidString: semester.id) ?? UUID(),
                name: semester.name,
                courses: semester.courses.map { course in
                    PlannerCourse(
                        id: UUID(uuidString: course.id) ?? UUID(),
                        name: course.name,
                        credits: course.credits,
                        category: plannerCategory(from: course.category),
                        program: plannerProgram(from: course.program),
                        dimension: plannerDimension(from: course.dimension),
                        instructor: course.details?.professor ?? "",
                        location: course.details?.location ?? "",
                        time: course.details?.time ?? "",
                        notes: course.details?.notes ?? ""
                    )
                }
            )
        }

        plannerSemesters = semesters.isEmpty ? Self.blankPlannerSemesters() : semesters
    }

    private func mergeImportedHistory(_ records: [HistoryCourseRecord], studentNumber: String?) -> HistoryImportSummary {
        var summary = HistoryImportSummary()

        for record in records.sorted(by: historyRecordSort) {
            let targetIndex = ensureSemesterIndex(for: record.academicTerm, studentNumber: studentNumber)
            let importedCourse = plannerCourse(from: record)
            let importedName = importedCourse.name.trimmingCharacters(in: .whitespacesAndNewlines)

            if let existingIndex = plannerSemesters[targetIndex].courses.firstIndex(where: {
                historyImportedCourseCode(from: $0.notes) == record.courseCode
            }) {
                let existingCourse = plannerSemesters[targetIndex].courses[existingIndex]
                plannerSemesters[targetIndex].courses[existingIndex] = mergedImportedHistoryCourse(
                    existing: existingCourse,
                    imported: importedCourse
                )
                summary.updated += 1
                continue
            }

            if plannerSemesters[targetIndex].courses.contains(where: {
                $0.name.trimmingCharacters(in: .whitespacesAndNewlines) == importedName
            }) {
                summary.skipped += 1
                continue
            }

            plannerSemesters[targetIndex].courses.append(importedCourse)
            summary.inserted += 1
        }

        return summary
    }

    private func mergedImportedHistoryCourse(existing: PlannerCourse, imported: PlannerCourse) -> PlannerCourse {
        var merged = existing
        merged.name = imported.name
        merged.credits = imported.credits
        merged.notes = mergedHistoryNotes(existingNotes: existing.notes, importedNotes: imported.notes)
        return merged
    }

    private func ensureSemesterIndex(for academicTerm: String, studentNumber: String?) -> Int {
        if let computedIndex = plannerSemesterIndex(for: academicTerm, studentNumber: studentNumber) {
            while plannerSemesters.count <= computedIndex {
                let nextIndex = plannerSemesters.count
                plannerSemesters.append(
                    PlannerSemester(
                        name: semesterName(forSequentialIndex: nextIndex),
                        courses: []
                    )
                )
            }
            return computedIndex
        }

        let fallbackName = fallbackSemesterName(for: academicTerm)
        if let existingIndex = plannerSemesters.firstIndex(where: { $0.name == fallbackName }) {
            return existingIndex
        }

        plannerSemesters.append(PlannerSemester(name: fallbackName, courses: []))
        return plannerSemesters.count - 1
    }

    private func plannerSemesterIndex(for academicTerm: String, studentNumber: String?) -> Int? {
        guard academicTerm.count >= 4 else {
            return nil
        }

        let termYearText = String(academicTerm.prefix(3))
        let termSemesterText = String(academicTerm.suffix(1))
        guard
            let termYear = Int(termYearText),
            let termSemester = Int(termSemesterText),
            (1 ... 2).contains(termSemester),
            let admissionYear = admissionYear(from: studentNumber ?? schoolAccount)
        else {
            return nil
        }

        let yearOffset = termYear - admissionYear
        guard yearOffset >= 0 else {
            return nil
        }

        return yearOffset * 2 + (termSemester - 1)
    }

    private func admissionYear(from studentNumber: String) -> Int? {
        let trimmed = studentNumber.trimmingCharacters(in: .whitespacesAndNewlines)
        let match = trimmed.range(of: #"\d{3}"#, options: .regularExpression)
        guard let match else {
            return nil
        }
        return Int(trimmed[match])
    }

    private func semesterName(forSequentialIndex index: Int) -> String {
        let academicYear = index / 2
        let semesterLabel = index.isMultiple(of: 2) ? "上" : "下"
        let yearLabel: String

        switch academicYear {
        case 0:
            yearLabel = "大一"
        case 1:
            yearLabel = "大二"
        case 2:
            yearLabel = "大三"
        case 3:
            yearLabel = "大四"
        default:
            yearLabel = "第\(academicYear + 1)學年"
        }

        return "\(yearLabel)\(semesterLabel)"
    }

    private func fallbackSemesterName(for academicTerm: String) -> String {
        guard academicTerm.count >= 4 else {
            return academicTerm
        }

        let year = String(academicTerm.prefix(3))
        let semester = academicTerm.hasSuffix("1") ? "上" : "下"
        return "\(year)學年\(semester)"
    }

    private func plannerCourse(from record: HistoryCourseRecord) -> PlannerCourse {
        let cleanedName = sanitizedHistoryCourseName(record.courseName)
        let category = plannerCategory(
            forHistoryCourseName: cleanedName,
            courseCode: record.courseCode,
            sourceCategory: record.category
        )

        return PlannerCourse(
            name: cleanedName,
            credits: parsedCredits(record.earnedCredits),
            category: category,
            program: .home,
            notes: historyNotes(for: record)
        )
    }

    private func sanitizedHistoryCourseName(_ rawName: String) -> String {
        rawName
            .replacingOccurrences(of: "★", with: "")
            .replacingOccurrences(of: "◆", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func parsedCredits(_ rawValue: String) -> Double {
        Double(rawValue.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
    }

    private func plannerCategory(forHistoryCourseName name: String, courseCode: String, sourceCategory: String) -> PlannerCourseCategory {
        let categoryText = sourceCategory
        let normalizedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        let code = courseCode.uppercased()

        if normalizedName.contains("體育") || code.hasPrefix("PE") {
            return .pe
        }
        if
            normalizedName.contains("國文")
            || normalizedName.contains("中文")
            || normalizedName.contains("文學")
            || normalizedName.contains("表達")
        {
            return .chinese
        }
        if normalizedName.contains("英文") || normalizedName.contains("英語") || code.hasPrefix("CC101") || code.hasPrefix("CC105") {
            return .english
        }
        if normalizedName.contains("通識") || code.hasPrefix("GE") || categoryText.contains("通識") {
            return .genEd
        }
        if categoryText.contains("社會") {
            return .social
        }
        if categoryText.contains("必修") {
            return .compulsory
        }
        if categoryText.contains("選修") {
            return .elective
        }
        return .other
    }

    private func historyNotes(for record: HistoryCourseRecord) -> String {
        [
            "歷史修課匯入",
            "課碼: \(record.courseCode)",
            "學年期: \(record.academicTerm)",
            "成績: \(record.grade)",
            "來源分類: \(record.category)"
        ].joined(separator: "\n")
    }

    private func mergedHistoryNotes(existingNotes: String, importedNotes: String) -> String {
        let preservedNotes = strippedHistoryMetadata(from: existingNotes)
        guard !preservedNotes.isEmpty else {
            return importedNotes
        }
        return importedNotes + "\n\n" + preservedNotes
    }

    private func strippedHistoryMetadata(from notes: String) -> String {
        let metadataPrefixes = [
            "歷史修課匯入",
            "課碼: ",
            "學年期: ",
            "成績: ",
            "來源分類: "
        ]

        let filteredLines = notes
            .components(separatedBy: .newlines)
            .filter { line in
                let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmed.isEmpty else {
                    return false
                }
                return !metadataPrefixes.contains(where: { trimmed.hasPrefix($0) })
            }

        return filteredLines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func historyImportedCourseCode(from notes: String) -> String? {
        let lines = notes.split(separator: "\n")
        for line in lines {
            if line.hasPrefix("課碼: ") {
                return line.replacingOccurrences(of: "課碼: ", with: "")
            }
        }
        return nil
    }

    private func historySourceCategory(from notes: String) -> String? {
        let lines = notes.split(separator: "\n")
        for line in lines {
            if line.hasPrefix("來源分類: ") {
                return line.replacingOccurrences(of: "來源分類: ", with: "")
            }
        }
        return nil
    }

    private func historyRecordSort(lhs: HistoryCourseRecord, rhs: HistoryCourseRecord) -> Bool {
        if lhs.academicTerm == rhs.academicTerm {
            return lhs.courseCode < rhs.courseCode
        }
        return lhs.academicTerm < rhs.academicTerm
    }

    private func applyCloudSettings(_ settings: CloudUserSettings?) {
        isRestoringPersistedState = true
        self.schoolAccount = settings?.schoolAccount?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        self.schoolPassword = settings?.schoolPassword?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        self.reminderMinutes = settings?.reminderMinutes ?? 10
        isRestoringPersistedState = false
    }

    private func clearScheduleState() {
        studentName = ""
        subtitle = "尚未同步課表"
        lastSyncedAt = nil
        scheduleEntries = []
        upcomingCourses = []
    }

    private func clearMoodleAssignmentsState() {
        moodleAssignments = []
        moodleAssignmentsSyncedAt = nil
        moodleAssignmentsFilterLabel = ""
    }

    private func friendlyMoodleAssignmentsErrorMessage(for error: Error) -> String {
        let message = error.localizedDescription.trimmingCharacters(in: .whitespacesAndNewlines)
        if message.contains("connect/authorize") || message.contains("登入後無法進入目標頁面") {
            return "Moodle 登入後沒有完成驗證流程，請稍後再試。"
        }
        if message.contains("Limit must be between 1 and 50") {
            return "Moodle 待繳事項同步參數超出範圍，請重新同步。"
        }
        return message
    }

    private func apply(payload: ScheduleSyncResponse) {
        if let payloadStudentName = payload.studentName?.trimmingCharacters(in: .whitespacesAndNewlines), !payloadStudentName.isEmpty {
            studentName = payloadStudentName
        }
        subtitle = payload.persistedToSupabase ? "課表已更新" : "課表已更新，等待雲端保存"
        lastSyncedAt = payload.syncedAt
        scheduleEntries = payload.scheduleEntries.map { entry in
            ScheduleEntry(
                weekday: entry.weekdayKey,
                title: entry.title,
                timeRange: entry.timeRange,
                slotTimes: entry.slotTimes,
                room: entry.room,
                instructor: entry.instructor,
                accent: mapAccent(entry.accent)
            )
        }
        upcomingCourses = Self.buildUpcomingCourses(from: scheduleEntries)
        persistCachedScheduleSnapshot()
        Task {
            await refreshClassReminders()
        }
    }

    private func apply(payload: MoodleAssignmentsResponse) {
        moodleAssignments = payload.items.sorted { $0.dueAt < $1.dueAt }
        moodleAssignmentsSyncedAt = payload.syncedAt
        moodleAssignmentsFilterLabel = payload.timelineFilter
        moodleAssignmentsErrorMessage = nil
        moodleAssignmentsNoticeMessage = payload.itemCount > 0
            ? "已更新 \(payload.itemCount) 筆待繳事項"
            : "目前沒有待繳事項"
        persistCachedMoodleAssignmentsSnapshot()
    }

    private static func buildUpcomingCourses(from entries: [ScheduleEntry]) -> [UpcomingCourse] {
        entries.map { entry in
            UpcomingCourse(
                title: entry.title,
                subtitle: entry.instructor.isEmpty ? "課表已更新" : entry.instructor,
                timeLabel: entry.timeRange,
                slotTimes: entry.slotTimes,
                room: entry.room.isEmpty ? "未提供地點" : entry.room,
                weekday: entry.weekday,
                note: entry.room.isEmpty ? "此課程未提供教室資訊" : "課表資料已更新"
            )
        }
    }

    private func mapAccent(_ rawValue: String) -> PlannerCourseCategory {
        PlannerCourseCategory(rawValue: rawValue) ?? .unclassified
    }

    private func cloudCategory(for category: PlannerCourseCategory) -> String {
        switch category {
        case .genEd:
            return "gen_ed"
        default:
            return category.rawValue
        }
    }

    private func plannerCategory(from rawValue: String) -> PlannerCourseCategory {
        switch rawValue {
        case "gen_ed":
            return .genEd
        default:
            return PlannerCourseCategory(rawValue: rawValue) ?? .unclassified
        }
    }

    private func cloudProgram(for program: PlannerCourseProgram) -> String {
        switch program {
        case .doubleMajor:
            return "double_major"
        default:
            return program.rawValue
        }
    }

    private func plannerProgram(from rawValue: String?) -> PlannerCourseProgram {
        switch rawValue {
        case "double_major":
            return .doubleMajor
        case "minor":
            return .minor
        case "other":
            return .other
        default:
            return .home
        }
    }

    private func cloudDimension(for dimension: PlannerGenEdDimension) -> String? {
        dimension == .none ? "None" : dimension.rawValue
    }

    private func plannerDimension(from rawValue: String?) -> PlannerGenEdDimension {
        guard let rawValue, rawValue != "None" else {
            return .none
        }
        return PlannerGenEdDimension(rawValue: rawValue) ?? .none
    }

    private func persistAuthSession(_ session: SupabaseStoredSession) {
        if let encoded = try? JSONEncoder().encode(session) {
            UserDefaults.standard.set(encoded, forKey: Self.authSessionStorageKey)
        }
    }

    private func clearAuthenticatedState() {
        plannerSaveTask?.cancel()
        plannerSaveTask = nil
        authSession = nil
        currentUserEmail = nil
        authErrorMessage = nil
        authNoticeMessage = nil
        historyImportErrorMessage = nil
        historyImportNoticeMessage = nil
        reminderErrorMessage = nil
        reminderNoticeMessage = nil
        moodleAssignmentsErrorMessage = nil
        moodleAssignmentsNoticeMessage = nil
        Task {
            await removeAllScheduledClassReminders()
        }
        resetCloudBackedState()
        selectedTab = .home
        UserDefaults.standard.removeObject(forKey: Self.authSessionStorageKey)
    }

    private func resetCloudBackedState() {
        isRestoringPersistedState = true
        schoolAccount = ""
        schoolPassword = ""
        reminderMinutes = 10
        plannerTargets = .default
        plannerSemesters = Self.blankPlannerSemesters()
        syncState = .idle
        clearScheduleState()
        clearMoodleAssignmentsState()
        isRestoringPersistedState = false
    }

    private func persistCachedScheduleSnapshot() {
        guard let session = authSession else {
            return
        }

        let snapshot = CachedScheduleSnapshot(
            studentName: studentName,
            subtitle: subtitle,
            lastSyncedAt: lastSyncedAt,
            scheduleEntries: scheduleEntries
        )

        if let encoded = try? JSONEncoder().encode(snapshot) {
            UserDefaults.standard.set(encoded, forKey: Self.scheduleSnapshotStorageKeyPrefix + session.userID)
        }
    }

    private func restoreCachedScheduleSnapshot(for session: SupabaseStoredSession) {
        guard
            let data = UserDefaults.standard.data(forKey: Self.scheduleSnapshotStorageKeyPrefix + session.userID),
            let snapshot = try? JSONDecoder().decode(CachedScheduleSnapshot.self, from: data)
        else {
            return
        }

        studentName = snapshot.studentName
        subtitle = snapshot.subtitle
        lastSyncedAt = snapshot.lastSyncedAt
        scheduleEntries = snapshot.scheduleEntries
        upcomingCourses = Self.buildUpcomingCourses(from: snapshot.scheduleEntries)
    }

    private func persistCachedMoodleAssignmentsSnapshot() {
        guard let session = authSession else {
            return
        }

        let snapshot = CachedMoodleAssignmentsSnapshot(
            syncedAt: moodleAssignmentsSyncedAt,
            filterLabel: moodleAssignmentsFilterLabel,
            items: moodleAssignments
        )

        if let encoded = try? JSONEncoder().encode(snapshot) {
            UserDefaults.standard.set(encoded, forKey: Self.moodleAssignmentsStorageKeyPrefix + session.userID)
        }
    }

    private func restoreCachedMoodleAssignmentsSnapshot(for session: SupabaseStoredSession) {
        guard
            let data = UserDefaults.standard.data(forKey: Self.moodleAssignmentsStorageKeyPrefix + session.userID),
            let snapshot = try? JSONDecoder().decode(CachedMoodleAssignmentsSnapshot.self, from: data)
        else {
            return
        }

        moodleAssignments = snapshot.items.sorted { $0.dueAt < $1.dueAt }
        moodleAssignmentsSyncedAt = snapshot.syncedAt
        moodleAssignmentsFilterLabel = snapshot.filterLabel
    }

    private func refreshClassReminders() async {
        reminderErrorMessage = nil

        guard reminderMinutes > 0 else {
            await removeAllScheduledClassReminders()
            reminderNoticeMessage = "課前提醒已關閉"
            return
        }

        guard !scheduleEntries.isEmpty else {
            await removeAllScheduledClassReminders()
            reminderNoticeMessage = "目前沒有可建立提醒的課程"
            return
        }

        do {
            let center = UNUserNotificationCenter.current()
            let isAuthorized = try await ensureNotificationAuthorization(center: center)
            guard isAuthorized else {
                await removeAllScheduledClassReminders(center: center)
                reminderErrorMessage = "尚未允許通知，請到 iPhone 的設定開啟通知權限"
                return
            }

            await removeAllScheduledClassReminders(center: center)

            var scheduledCount = 0
            for entry in scheduleEntries {
                guard let triggerComponents = reminderTriggerComponents(for: entry, reminderMinutes: reminderMinutes) else {
                    continue
                }

                let content = UNMutableNotificationContent()
                content.title = "\(reminderMinutes) 分鐘後上課"
                content.body = reminderBody(for: entry)
                content.sound = .default

                let request = UNNotificationRequest(
                    identifier: reminderIdentifier(for: entry),
                    content: content,
                    trigger: UNCalendarNotificationTrigger(dateMatching: triggerComponents, repeats: true)
                )

                try await addNotificationRequest(request, center: center)
                scheduledCount += 1
            }

            reminderNoticeMessage = scheduledCount > 0
                ? "已建立 \(scheduledCount) 筆每週課前提醒"
                : "目前沒有可建立提醒的課程"
        } catch {
            reminderErrorMessage = "建立課前提醒失敗：\(error.localizedDescription)"
        }
    }

    private func ensureNotificationAuthorization(center: UNUserNotificationCenter) async throws -> Bool {
        let settings = await notificationSettings(center: center)
        switch settings.authorizationStatus {
        case .authorized, .provisional, .ephemeral:
            return true
        case .notDetermined:
            return try await requestNotificationAuthorization(center: center)
        case .denied:
            return false
        @unknown default:
            return false
        }
    }

    private func notificationSettings(center: UNUserNotificationCenter) async -> UNNotificationSettings {
        await withCheckedContinuation { continuation in
            center.getNotificationSettings { settings in
                continuation.resume(returning: settings)
            }
        }
    }

    private func requestNotificationAuthorization(center: UNUserNotificationCenter) async throws -> Bool {
        try await withCheckedThrowingContinuation { continuation in
            center.requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: granted)
                }
            }
        }
    }

    private func addNotificationRequest(_ request: UNNotificationRequest, center: UNUserNotificationCenter) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            center.add(request) { error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: ())
                }
            }
        }
    }

    private func reminderTriggerComponents(for entry: ScheduleEntry, reminderMinutes: Int) -> DateComponents? {
        let startComponents = Self.timeComponents(from: entry.timeRange)
        let calendar = Calendar(identifier: .gregorian)
        var matchingComponents = DateComponents()
        matchingComponents.weekday = entry.weekday.calendarWeekday
        matchingComponents.hour = startComponents.hour
        matchingComponents.minute = startComponents.minute

        guard
            let nextStartDate = calendar.nextDate(
                after: Date(),
                matching: matchingComponents,
                matchingPolicy: .nextTimePreservingSmallerComponents,
                direction: .forward
            ),
            let reminderDate = calendar.date(byAdding: .minute, value: -reminderMinutes, to: nextStartDate)
        else {
            return nil
        }

        var components = DateComponents()
        components.weekday = calendar.component(.weekday, from: reminderDate)
        components.hour = calendar.component(.hour, from: reminderDate)
        components.minute = calendar.component(.minute, from: reminderDate)
        return components
    }

    private func reminderBody(for entry: ScheduleEntry) -> String {
        [
            entry.title,
            entry.timeRange,
            entry.room.isEmpty ? nil : entry.room,
            entry.instructor.isEmpty ? nil : entry.instructor
        ]
        .compactMap { $0 }
        .joined(separator: " · ")
    }

    private func removeAllScheduledClassReminders(center: UNUserNotificationCenter = .current()) async {
        let pendingIDs = await pendingReminderIdentifiers(center: center)
        if !pendingIDs.isEmpty {
            center.removePendingNotificationRequests(withIdentifiers: pendingIDs)
        }

        let deliveredIDs = await deliveredReminderIdentifiers(center: center)
        if !deliveredIDs.isEmpty {
            center.removeDeliveredNotifications(withIdentifiers: deliveredIDs)
        }
    }

    private func reminderIdentifier(for entry: ScheduleEntry) -> String {
        let rawValue = "\(entry.weekday.rawValue)-\(entry.timeRange)-\(entry.title)"
        let sanitized = rawValue
            .lowercased()
            .replacingOccurrences(of: " ", with: "-")
            .replacingOccurrences(of: "/", with: "-")
        return "course-reminder-\(sanitized)"
    }

    private func pendingReminderIdentifiers(center: UNUserNotificationCenter) async -> [String] {
        await withCheckedContinuation { continuation in
            center.getPendingNotificationRequests { requests in
                continuation.resume(
                    returning: requests
                        .map(\.identifier)
                        .filter { $0.hasPrefix("course-reminder-") }
                )
            }
        }
    }

    private func deliveredReminderIdentifiers(center: UNUserNotificationCenter) async -> [String] {
        await withCheckedContinuation { continuation in
            center.getDeliveredNotifications { notifications in
                continuation.resume(
                    returning: notifications
                        .map(\.request.identifier)
                        .filter { $0.hasPrefix("course-reminder-") }
                )
            }
        }
    }

    private func makeURL(path: String) throws -> URL {
        guard
            let supabaseURL,
            let url = URL(string: path, relativeTo: supabaseURL)
        else {
            throw NSError(domain: "CoursePlannerAuth", code: 4, userInfo: [
                NSLocalizedDescriptionKey: "雲端服務網址設定錯誤"
            ])
        }
        return url
    }

    private func applyAPIHeaders(to request: inout URLRequest) {
        guard let supabaseAnonKey else {
            return
        }

        request.setValue(supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
    }

    private func performJSONRequest<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request)
        try validateHTTPResponse(response, data: data)

        let decoder = JSONDecoder()
        return try decoder.decode(T.self, from: data)
    }

    private func validateHTTPResponse(_ response: URLResponse, data: Data) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        guard (200 ..< 300).contains(httpResponse.statusCode) else {
            if
                let authError = try? JSONDecoder().decode(SupabaseAuthErrorResponse.self, from: data),
                let message = authError.errorDescription ?? authError.message
            {
                throw NSError(domain: "CoursePlannerAuth", code: httpResponse.statusCode, userInfo: [
                    NSLocalizedDescriptionKey: message
                ])
            }

            if
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                let detail = json["detail"] as? String
            {
                throw NSError(domain: "CoursePlannerAuth", code: httpResponse.statusCode, userInfo: [
                    NSLocalizedDescriptionKey: detail
                ])
            }

            throw NSError(domain: "CoursePlannerAuth", code: httpResponse.statusCode, userInfo: [
                NSLocalizedDescriptionKey: "請求失敗，HTTP \(httpResponse.statusCode)"
            ])
        }
    }

    private func nextOccurrenceDate(for course: UpcomingCourse, from referenceDate: Date) -> Date {
        let calendar = Calendar(identifier: .gregorian)
        var components = DateComponents()
        components.weekday = course.weekday.calendarWeekday
        components.hour = course.startTime.hour
        components.minute = course.startTime.minute

        return calendar.nextDate(
            after: referenceDate.addingTimeInterval(-1),
            matching: components,
            matchingPolicy: .nextTimePreservingSmallerComponents,
            direction: .forward
        ) ?? referenceDate
    }

    private var supabaseURL: URL? {
        guard let rawValue = Bundle.main.object(forInfoDictionaryKey: "SupabaseURL") as? String else {
            return nil
        }
        return URL(string: rawValue)
    }

    private var supabaseAnonKey: String? {
        Bundle.main.object(forInfoDictionaryKey: "SupabaseAnonKey") as? String
    }

    private static let authSessionStorageKey = "courseplanner.supabase.session"
    private static let scheduleSnapshotStorageKeyPrefix = "courseplanner.scheduleSnapshot."
    private static let moodleAssignmentsStorageKeyPrefix = "courseplanner.moodleAssignments."
    private static let backendServiceBaseURL = "https://course-planner-backend-production.up.railway.app"

    private static func iso8601String(from date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: date)
    }

    private static func blankPlannerSemesters() -> [PlannerSemester] {
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

    private struct HistoryImportSummary {
        var inserted = 0
        var updated = 0
        var skipped = 0
    }

    private static func timeComponents(from timeRange: String) -> DateComponents {
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

private extension String {
    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}
