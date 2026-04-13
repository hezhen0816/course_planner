import Foundation

extension AppSessionStore {
    func loadPlannerData(preserveExistingStateOnFailure: Bool = true) async {
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

    func queuePlannerSave() {
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

    func savePlannerData() async {
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

    func persistPlannerData() async throws {
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

    func cloudAppDataPayload() -> CloudAppDataPayload {
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

    func applyPlannerPayload(_ payload: CloudAppDataPayload) {
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

    func applyCloudSettings(_ settings: CloudUserSettings?) {
        isRestoringPersistedState = true
        self.schoolAccount = settings?.schoolAccount?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        self.schoolPassword = settings?.schoolPassword?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        self.reminderMinutes = settings?.reminderMinutes ?? 10
        isRestoringPersistedState = false
    }

    func mapAccent(_ rawValue: String) -> PlannerCourseCategory {
        PlannerCourseCategory(rawValue: rawValue) ?? .unclassified
    }

    func cloudCategory(for category: PlannerCourseCategory) -> String {
        switch category {
        case .genEd:
            return "gen_ed"
        default:
            return category.rawValue
        }
    }

    func plannerCategory(from rawValue: String) -> PlannerCourseCategory {
        switch rawValue {
        case "gen_ed":
            return .genEd
        default:
            return PlannerCourseCategory(rawValue: rawValue) ?? .unclassified
        }
    }

    func cloudProgram(for program: PlannerCourseProgram) -> String {
        switch program {
        case .doubleMajor:
            return "double_major"
        default:
            return program.rawValue
        }
    }

    func plannerProgram(from rawValue: String?) -> PlannerCourseProgram {
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

    func cloudDimension(for dimension: PlannerGenEdDimension) -> String? {
        dimension == .none ? "None" : dimension.rawValue
    }

    func plannerDimension(from rawValue: String?) -> PlannerGenEdDimension {
        guard let rawValue, rawValue != "None" else {
            return .none
        }
        return PlannerGenEdDimension(rawValue: rawValue) ?? .none
    }

    func resetCloudBackedState() {
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
}
