import Foundation

extension AppSessionStore {
    func persistCachedScheduleSnapshot() {
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

    func restoreCachedScheduleSnapshot(for session: SupabaseStoredSession) {
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

    func persistCachedMoodleAssignmentsSnapshot() {
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

    func restoreCachedMoodleAssignmentsSnapshot(for session: SupabaseStoredSession) {
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
}
