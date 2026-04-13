import Foundation

extension AppSessionStore {
    func syncMoodleAssignments() async {
        let username = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        let password = schoolPassword.trimmingCharacters(in: .whitespacesAndNewlines)
        moodleAssignmentsErrorMessage = nil
        moodleAssignmentsNoticeMessage = nil

        guard !username.isEmpty, !password.isEmpty else {
            moodleAssignmentsErrorMessage = "請先輸入學校帳號與密碼"
            return
        }

        do {
            let endpoint = try Self.backendURL(path: "/api/moodle/assignments/sync")
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

        do {
            let encodedProfileKey = profileKey.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? profileKey
            let endpoint = try Self.backendURL(path: "/api/moodle/assignments/\(encodedProfileKey)")
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

    func clearMoodleAssignmentsState() {
        moodleAssignments = []
        moodleAssignmentsSyncedAt = nil
        moodleAssignmentsFilterLabel = ""
    }

    func friendlyMoodleAssignmentsErrorMessage(for error: Error) -> String {
        let message = error.localizedDescription.trimmingCharacters(in: .whitespacesAndNewlines)
        if message.contains("connect/authorize") || message.contains("登入後無法進入目標頁面") {
            return "Moodle 登入後沒有完成驗證流程，請稍後再試。"
        }
        if message.contains("Limit must be between 1 and 50") {
            return "Moodle 待繳事項同步參數超出範圍，請重新同步。"
        }
        return message
    }

    func apply(payload: MoodleAssignmentsResponse) {
        moodleAssignments = payload.items.sorted { $0.dueAt < $1.dueAt }
        moodleAssignmentsSyncedAt = payload.syncedAt
        moodleAssignmentsFilterLabel = payload.timelineFilter
        moodleAssignmentsErrorMessage = nil
        moodleAssignmentsNoticeMessage = payload.itemCount > 0
            ? "已更新 \(payload.itemCount) 筆待繳事項"
            : "目前沒有待繳事項"
        persistCachedMoodleAssignmentsSnapshot()
    }
}
