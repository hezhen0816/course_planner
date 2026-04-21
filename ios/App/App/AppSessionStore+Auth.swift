import Foundation
import LocalAuthentication

extension AppSessionStore {
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


    func restoreCachedAuthSession() {
        guard
            let sessionData = UserDefaults.standard.data(forKey: Self.authSessionStorageKey),
            let storedSession = try? JSONDecoder().decode(SupabaseStoredSession.self, from: sessionData)
        else {
            return
        }

        authSession = storedSession
        currentUserEmail = storedSession.email
        if isBiometricAuthEnabled {
            requiresBiometricUnlock = true
        }
        restoreCachedScheduleSnapshot(for: storedSession)
        restoreCachedMoodleAssignmentsSnapshot(for: storedSession)
    }

    func establishAuthenticatedSession(from payload: SupabaseAuthSessionResponse, fallbackEmail: String) async throws {
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
        requiresBiometricUnlock = false
        biometricAuthErrorMessage = nil
        authErrorMessage = nil
        subtitle = "尚未同步課表"
        persistAuthSession(storedSession)
        restoreCachedScheduleSnapshot(for: storedSession)
        restoreCachedMoodleAssignmentsSnapshot(for: storedSession)
        bootstrapAuthenticatedData(forceRefresh: false)
    }

    func bootstrapAuthenticatedData(forceRefresh: Bool) {
        Task { @MainActor in
            do {
                _ = try await validSession(forceRefresh: forceRefresh)
                await loadPlannerData(preserveExistingStateOnFailure: true)
                if !schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    await loadLatestScheduleSnapshot(suppressErrors: true)
                    await loadLatestMoodleAssignments(suppressErrors: true)
                }
            } catch {
                if Self.isCancellation(error) {
                    return
                }
                clearAuthenticatedState()
                authErrorMessage = "登入已失效，請重新登入"
            }
        }
    }

    func validSession(forceRefresh: Bool = false) async throws -> SupabaseStoredSession {
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

    func refreshSession(using currentSession: SupabaseStoredSession) async throws -> SupabaseStoredSession {
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

    func persistAuthSession(_ session: SupabaseStoredSession) {
        if let encoded = try? JSONEncoder().encode(session) {
            UserDefaults.standard.set(encoded, forKey: Self.authSessionStorageKey)
        }
    }

    func clearAuthenticatedState() {
        plannerSaveTask?.cancel()
        plannerSaveTask = nil
        authSession = nil
        currentUserEmail = nil
        isBiometricAuthEnabled = false
        requiresBiometricUnlock = false
        isBiometricAuthenticating = false
        biometricAuthErrorMessage = nil
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
        UserDefaults.standard.removeObject(forKey: Self.biometricAuthEnabledStorageKey)
    }

    var localizedBiometricName: String {
        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            return "Face ID"
        }

        switch context.biometryType {
        case .faceID:
            return "Face ID"
        case .touchID:
            return "Touch ID"
        case .opticID:
            return "Optic ID"
        default:
            return "Face ID"
        }
    }

    func setBiometricAuthEnabled(_ isEnabled: Bool) async {
        biometricAuthErrorMessage = nil

        guard isEnabled else {
            isBiometricAuthEnabled = false
            requiresBiometricUnlock = false
            UserDefaults.standard.set(false, forKey: Self.biometricAuthEnabledStorageKey)
            return
        }

        guard isAuthenticated else {
            biometricAuthErrorMessage = "請先登入帳號，再啟用 \(localizedBiometricName)"
            return
        }

        guard biometricAuthenticationIsAvailable() else {
            biometricAuthErrorMessage = "這台裝置尚未設定可用的 \(localizedBiometricName)"
            return
        }

        let didAuthenticate = await evaluateBiometricAuthentication(
            reason: "啟用後，開啟修課羅盤時可使用 \(localizedBiometricName) 解鎖。"
        )
        guard didAuthenticate else {
            return
        }

        isBiometricAuthEnabled = true
        requiresBiometricUnlock = false
        UserDefaults.standard.set(true, forKey: Self.biometricAuthEnabledStorageKey)
        authNoticeMessage = "已啟用 \(localizedBiometricName) 登入"
    }

    func lockForBiometricUnlockIfNeeded() {
        guard shouldUseBiometricUnlock else {
            return
        }
        requiresBiometricUnlock = true
        biometricAuthErrorMessage = nil
    }

    func unlockWithBiometrics() async {
        guard shouldUseBiometricUnlock else {
            requiresBiometricUnlock = false
            return
        }

        biometricAuthErrorMessage = nil
        let didAuthenticate = await evaluateBiometricAuthentication(
            reason: "使用 \(localizedBiometricName) 解鎖修課羅盤。"
        )

        if didAuthenticate {
            requiresBiometricUnlock = false
            biometricAuthErrorMessage = nil
            bootstrapAuthenticatedData(forceRefresh: false)
        }
    }

    private func biometricAuthenticationIsAvailable() -> Bool {
        let context = LAContext()
        var error: NSError?
        return context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
    }

    private func evaluateBiometricAuthentication(reason: String) async -> Bool {
        let context = LAContext()
        context.localizedCancelTitle = "取消"

        var policyError: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &policyError) else {
            biometricAuthErrorMessage = "這台裝置尚未設定可用的 \(localizedBiometricName)"
            return false
        }

        isBiometricAuthenticating = true
        defer {
            isBiometricAuthenticating = false
        }

        do {
            return try await context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason)
        } catch {
            biometricAuthErrorMessage = biometricErrorMessage(from: error)
            return false
        }
    }

    private func biometricErrorMessage(from error: Error) -> String {
        guard let laError = error as? LAError else {
            return error.localizedDescription
        }

        switch laError.code {
        case .authenticationFailed:
            return "\(localizedBiometricName) 驗證失敗，請再試一次"
        case .biometryLockout:
            return "\(localizedBiometricName) 已暫時鎖定，請先用系統密碼解鎖後再試"
        case .biometryNotAvailable:
            return "這台裝置不支援 \(localizedBiometricName)"
        case .biometryNotEnrolled:
            return "請先到系統設定完成 \(localizedBiometricName) 設定"
        case .userCancel, .systemCancel, .appCancel:
            return "已取消 \(localizedBiometricName) 驗證"
        default:
            return laError.localizedDescription
        }
    }
}
