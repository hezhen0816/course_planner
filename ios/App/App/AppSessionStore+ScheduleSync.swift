import Foundation

extension AppSessionStore {
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

        syncState = .syncing

        do {
            let endpoint = try Self.backendURL(path: "/api/schedule/sync")
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

        if !suppressErrors {
            syncState = .syncing
        }

        do {
            let encodedProfileKey = profileKey.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? profileKey
            let endpoint = try Self.backendURL(path: "/api/schedule/\(encodedProfileKey)")
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

    func loadTRRoomStatus(room: String? = nil, target: String = "current", refresh: Bool = false) async throws -> TRRoomStatusResponse {
        guard var components = URLComponents(url: try Self.backendURL(path: "/api/tr-rooms/status"), resolvingAgainstBaseURL: false) else {
            throw URLError(.badURL)
        }

        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "target", value: target)
        ]
        if let room = room?.trimmingCharacters(in: .whitespacesAndNewlines), !room.isEmpty {
            queryItems.append(URLQueryItem(name: "room", value: room))
        }
        if refresh {
            queryItems.append(URLQueryItem(name: "refresh", value: "true"))
        }
        components.queryItems = queryItems.isEmpty ? nil : queryItems

        guard let endpoint = components.url else {
            throw URLError(.badURL)
        }

        let (data, response) = try await URLSession.shared.data(from: endpoint)
        try validateHTTPResponse(response, data: data)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(TRRoomStatusResponse.self, from: data)
    }

    func clearScheduleState() {
        studentName = ""
        subtitle = "尚未同步課表"
        lastSyncedAt = nil
        scheduleEntries = []
        upcomingCourses = []
    }

    func apply(payload: ScheduleSyncResponse) {
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

    static func buildUpcomingCourses(from entries: [ScheduleEntry]) -> [UpcomingCourse] {
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

    func nextOccurrenceDate(for course: UpcomingCourse, from referenceDate: Date) -> Date {
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
}
