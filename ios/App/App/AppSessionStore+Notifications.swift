import Foundation
import UserNotifications

extension AppSessionStore {
    func refreshClassReminders() async {
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

    func ensureNotificationAuthorization(center: UNUserNotificationCenter) async throws -> Bool {
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

    func notificationSettings(center: UNUserNotificationCenter) async -> UNNotificationSettings {
        await withCheckedContinuation { continuation in
            center.getNotificationSettings { settings in
                continuation.resume(returning: settings)
            }
        }
    }

    func requestNotificationAuthorization(center: UNUserNotificationCenter) async throws -> Bool {
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

    func addNotificationRequest(_ request: UNNotificationRequest, center: UNUserNotificationCenter) async throws {
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

    func reminderTriggerComponents(for entry: ScheduleEntry, reminderMinutes: Int) -> DateComponents? {
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

    func reminderBody(for entry: ScheduleEntry) -> String {
        [
            entry.title,
            entry.timeRange,
            entry.room.isEmpty ? nil : entry.room,
            entry.instructor.isEmpty ? nil : entry.instructor
        ]
        .compactMap { $0 }
        .joined(separator: " · ")
    }

    func removeAllScheduledClassReminders(center: UNUserNotificationCenter = .current()) async {
        let pendingIDs = await pendingReminderIdentifiers(center: center)
        if !pendingIDs.isEmpty {
            center.removePendingNotificationRequests(withIdentifiers: pendingIDs)
        }

        let deliveredIDs = await deliveredReminderIdentifiers(center: center)
        if !deliveredIDs.isEmpty {
            center.removeDeliveredNotifications(withIdentifiers: deliveredIDs)
        }
    }

    func reminderIdentifier(for entry: ScheduleEntry) -> String {
        let rawValue = "\(entry.weekday.rawValue)-\(entry.timeRange)-\(entry.title)"
        let sanitized = rawValue
            .lowercased()
            .replacingOccurrences(of: " ", with: "-")
            .replacingOccurrences(of: "/", with: "-")
        return "course-reminder-\(sanitized)"
    }

    func pendingReminderIdentifiers(center: UNUserNotificationCenter) async -> [String] {
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

    func deliveredReminderIdentifiers(center: UNUserNotificationCenter) async -> [String] {
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
}
