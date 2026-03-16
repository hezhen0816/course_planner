import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var store: AppSessionStore
    
    private func formattedDate(for date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_Hant_TW")
        formatter.dateFormat = "M 月 d 日 EEEE"
        return formatter.string(from: date)
    }

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    pageHeader
                    headerCard(now: context.date)
                    upcomingSection(now: context.date)
                    todoSection
                    progressSnapshot
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 32)
            }
            .refreshable {
                await store.refreshHomeContent()
            }
        }
        .background(Color(.systemGroupedBackground))
        .toolbar(.hidden, for: .navigationBar)
    }

    private var pageHeader: some View {
        Text("首頁")
            .font(.system(size: 34, weight: .bold, design: .rounded))
            .foregroundStyle(.primary)
            .padding(.top, 4)
    }

    private func headerCard(now: Date) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            if let nextCourse = store.nextUpcomingCourse {
                VStack(alignment: .leading, spacing: 14) {
                    Text(formattedDate(for: now))
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.9))

                    Text("下一堂課")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.78))

                    Text(nextCourse.title)
                        .font(.title2.weight(.bold))
                        .foregroundStyle(.white)
                        .fixedSize(horizontal: false, vertical: true)

                    HStack(spacing: 10) {
                        heroMetaPill(systemImage: "clock.fill", text: nextCourse.timeLabel)
                        heroMetaPill(systemImage: "mappin.and.ellipse", text: nextCourse.room)
                    }

                    if let countdownText = countdownText(for: nextCourse, now: now) {
                        Text(countdownText)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white.opacity(0.92))
                    }
                }
            } else {
                VStack(alignment: .leading, spacing: 10) {
                    Text(formattedDate(for: now))
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.9))
                    Text("今天沒有剩餘課程，可以保留時間安排複習或作業。")
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.84))
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(22)
        .background(
            LinearGradient(
                colors: [Color.indigo, Color.blue, Color.cyan.opacity(0.8)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 30, style: .continuous)
        )
    }

    private func upcomingSection(now: Date) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader(title: "今日課程", subtitle: "只顯示今天尚未結束的課程與提醒")

            if store.todayUpcomingCourses.isEmpty {
                ContentUnavailableView(
                    "今天沒有剩餘課程",
                    systemImage: "sun.max",
                    description: Text("今天已經結束的課不會再顯示，也不會顯示其他日期的課程。")
                )
                .frame(maxWidth: .infinity)
                .padding(.top, 12)
            } else {
                ForEach(store.todayUpcomingCourses) { course in
                    HStack(alignment: .top, spacing: 14) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(startTimeText(for: course))
                                .font(.title3.weight(.bold))
                                .monospacedDigit()
                            Text(endTimeText(for: course))
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(.secondary)
                                .monospacedDigit()
                            Text(course.weekday.fullTitle)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .frame(width: 76, alignment: .leading)

                        VStack(alignment: .leading, spacing: 12) {
                            HStack(alignment: .top, spacing: 12) {
                                Text(course.title)
                                    .font(.headline)
                                    .foregroundStyle(.primary)
                                    .fixedSize(horizontal: false, vertical: true)
                                Spacer()
                                Circle()
                                    .fill(courseAccentColor(for: course, now: now))
                                    .frame(width: 10, height: 10)
                                    .padding(.top, 6)
                            }

                            Text(course.subtitle)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)

                            if let countdownText = countdownText(for: course, now: now) {
                                Text(countdownText)
                                    .font(.footnote.weight(.semibold))
                                    .foregroundStyle(courseAccentColor(for: course, now: now))
                            }

                            HStack(spacing: 14) {
                                metadataItem(systemImage: "mappin.and.ellipse", text: course.room)
                                metadataItem(systemImage: "checklist", text: course.note)
                            }
                        }
                        .padding(18)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    }
                }
            }
        }
    }

    private var todoSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader(title: "待繳事項", subtitle: todoSubtitle)

            if store.moodleAssignments.isEmpty {
                ContentUnavailableView(
                    "目前沒有待繳事項",
                    systemImage: "checkmark.seal",
                    description: Text("同步 Moodle 後，這裡會顯示近期需要繳交的作業。")
                )
                .frame(maxWidth: .infinity)
                .padding(.top, 12)
            } else {
                ForEach(store.moodleAssignments.prefix(4)) { item in
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(alignment: .top, spacing: 12) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(todoDateText(for: item.dueAt))
                                    .font(.headline.weight(.bold))
                                    .monospacedDigit()
                                Text(todoWeekdayText(for: item.dueAt))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .frame(width: 78, alignment: .leading)

                            VStack(alignment: .leading, spacing: 10) {
                                HStack(alignment: .top, spacing: 8) {
                                    Text(item.title)
                                        .font(.headline)
                                        .fixedSize(horizontal: false, vertical: true)
                                    Spacer()
                                    Text(item.overdue ? "已逾期" : nonEmptyText(item.actionLabel) ?? "待處理")
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(item.overdue ? .red : .indigo)
                                        .padding(.horizontal, 10)
                                        .padding(.vertical, 6)
                                        .background(
                                            (item.overdue ? Color.red : Color.indigo).opacity(0.1),
                                            in: Capsule()
                                        )
                                }

                                Text(item.courseName)
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                                    .fixedSize(horizontal: false, vertical: true)

                                if !item.summary.isEmpty {
                                    Text(item.summary)
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(18)
                    .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                }
            }
        }
    }

    private var todoSubtitle: String {
        if let syncedAt = store.moodleAssignmentsSyncedAt {
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "zh_Hant_TW")
            formatter.dateFormat = "M/d HH:mm"
            let filterLabel = nonEmptyText(store.moodleAssignmentsFilterLabel) ?? "往後30天"
            return "\(filterLabel)・上次更新 \(formatter.string(from: syncedAt))"
        }
        return "同步 Moodle 後，會顯示往後30天需要繳交的作業"
    }

    private var progressSnapshot: some View {
        let progress = store.plannerProgress
        let targets = store.plannerTargets

        return VStack(alignment: .leading, spacing: 14) {
            sectionHeader(title: "學分摘要", subtitle: "快速查看目前進度與剩餘目標")

            VStack(alignment: .leading, spacing: 14) {
                summaryRow(title: "總學分", current: progress.total, target: targets.total, tint: .blue)
                summaryRow(title: "通識", current: progress.genEd, target: targets.genEd, tint: .purple)
                summaryRow(title: "共同英文", current: progress.english, target: targets.english, tint: .indigo)
                summaryRow(title: "本系必修", current: progress.homeCompulsory, target: targets.homeCompulsory, tint: .red)

                HStack(spacing: 8) {
                    ForEach([PlannerGenEdDimension.A, .B, .C, .D, .E, .F], id: \.id) { dimension in
                        Text(dimension.rawValue)
                            .font(.caption.weight(.bold))
                            .foregroundStyle(progress.genEdDimensions.contains(dimension) ? Color.white : Color.secondary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .fill(progress.genEdDimensions.contains(dimension) ? dimensionColor(for: dimension) : Color(.tertiarySystemFill))
                            )
                    }
                }
            }
            .padding(18)
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        }
    }

    private func sectionHeader(title: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.title3.weight(.bold))
            Text(subtitle)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private func heroMetaPill(systemImage: String, text: String) -> some View {
        Label(text, systemImage: systemImage)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(.white.opacity(0.14), in: Capsule())
    }

    private func metadataItem(systemImage: String, text: String) -> some View {
        Label(text, systemImage: systemImage)
            .font(.footnote)
            .foregroundStyle(.secondary)
            .lineLimit(1)
    }

    private func courseAccentColor(for course: UpcomingCourse, now: Date) -> Color {
        if case .inClass = course.countdownState(on: now) {
            return .orange
        }
        return .indigo
    }

    private func startTimeText(for course: UpcomingCourse) -> String {
        formattedTime(timeComponent(for: course, at: 0, fallbackHour: 9))
    }

    private func endTimeText(for course: UpcomingCourse) -> String {
        formattedTime(timeComponent(for: course, at: 1, fallbackHour: 10))
    }

    private func timeComponent(for course: UpcomingCourse, at index: Int, fallbackHour: Int) -> DateComponents {
        let label = course.timeLabel
            .components(separatedBy: "-")
            .dropFirst(index)
            .first?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? "\(fallbackHour):00"
        let parts = label.split(separator: ":")
        let hour = Int(parts.first ?? Substring("\(fallbackHour)")) ?? fallbackHour
        let minute = Int(parts.dropFirst().first ?? "0") ?? 0
        return DateComponents(hour: hour, minute: minute)
    }

    private func formattedTime(_ components: DateComponents) -> String {
        let hour = components.hour ?? 0
        let minute = components.minute ?? 0
        return String(format: "%02d:%02d", hour, minute)
    }

    private func minutes(from components: DateComponents) -> Int {
        (components.hour ?? 0) * 60 + (components.minute ?? 0)
    }

    private func countdownText(for course: UpcomingCourse, now: Date = Date(), calendar: Calendar = .current) -> String? {
        if let state = course.countdownState(on: now, calendar: calendar) {
            switch state {
            case .beforeClass(let startDate):
                let minutes = max(1, Int(startDate.timeIntervalSince(now) / 60))
                return "距離上課還有 \(minutes) 分鐘"
            case .inClass(let endDate):
                let minutes = max(1, Int(endDate.timeIntervalSince(now) / 60))
                return "正在上課中，距離下課還有 \(minutes) 分鐘"
            case .betweenSessions(let nextStartDate):
                let minutes = max(1, Int(nextStartDate.timeIntervalSince(now) / 60))
                return "下課中，距離下節上課還有 \(minutes) 分鐘"
            }
        }

        return nil
    }

    private func summaryRow(title: String, current: Double, target: Double, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Text("\(Int(current))/\(Int(target))")
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(.secondary)
            }
            ProgressView(value: min(current, target), total: max(target, 1))
                .tint(tint)
        }
    }

    private func todoDateText(for date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_Hant_TW")
        formatter.dateFormat = "M/d HH:mm"
        return formatter.string(from: date)
    }

    private func todoWeekdayText(for date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_Hant_TW")
        formatter.dateFormat = "EEEE"
        return formatter.string(from: date)
    }

    private func nonEmptyText(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func dimensionColor(for dimension: PlannerGenEdDimension) -> Color {
        switch dimension {
        case .A:
            return .pink
        case .B:
            return .blue
        case .C:
            return .purple
        case .D:
            return .orange
        case .E:
            return .green
        case .F:
            return .teal
        case .none:
            return .gray
        }
    }
}
