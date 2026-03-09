import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var store: AppSessionStore

    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_Hant_TW")
        formatter.dateFormat = "M 月 d 日 EEEE"
        return formatter.string(from: Date())
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                headerCard
                upcomingSection
                todoSection
                progressSnapshot
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
            .padding(.bottom, 32)
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("首頁")
        .navigationBarTitleDisplayMode(.large)
    }

    private var headerCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(store.subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.82))
                    Text(store.studentName)
                        .font(.system(size: 30, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                    Text(formattedDate)
                        .font(.callout)
                        .foregroundStyle(.white.opacity(0.9))
                }
                Spacer()
                Image(systemName: "iphone.gen3.radiowaves.left.and.right")
                    .font(.system(size: 26, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.95))
                    .padding(12)
                    .background(.white.opacity(0.16), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            }

            if let nextCourse = store.nextUpcomingCourse {
                VStack(alignment: .leading, spacing: 8) {
                    Text("下一堂課")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.82))
                    Text(nextCourse.title)
                        .font(.title3.weight(.bold))
                        .foregroundStyle(.white)
                    HStack(spacing: 10) {
                        Label(nextCourse.timeLabel, systemImage: "clock.fill")
                        Label(nextCourse.room, systemImage: "mappin.and.ellipse")
                    }
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.white.opacity(0.92))
                    Text(nextCourse.note)
                        .font(.footnote)
                        .foregroundStyle(.white.opacity(0.82))
                }
                .padding(16)
                .background(.white.opacity(0.14), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            }
        }
        .padding(22)
        .background(
            LinearGradient(
                colors: [Color.indigo, Color.blue, Color.cyan.opacity(0.8)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 28, style: .continuous)
        )
    }

    private var upcomingSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader(title: "即將到來的課程", subtitle: "接下來需要準備的課程與提醒")

            ForEach(store.upcomingCourses) { course in
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text(course.weekday.fullTitle)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.indigo)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color.indigo.opacity(0.12), in: Capsule())
                        Spacer()
                        Text(course.timeLabel)
                            .font(.caption.weight(.medium))
                            .foregroundStyle(.secondary)
                    }

                    Text(course.title)
                        .font(.headline)

                    Text(course.subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    HStack(spacing: 12) {
                        Label(course.room, systemImage: "mappin.circle")
                        Label(course.note, systemImage: "checklist")
                    }
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                }
                .padding(18)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            }
        }
    }

    private var todoSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader(title: "待辦作業", subtitle: "只做展示，不連動校務系統資料")

            ForEach(store.todoItems) { item in
                HStack(alignment: .top, spacing: 14) {
                    Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundStyle(item.isCompleted ? Color.green : Color.orange)

                    VStack(alignment: .leading, spacing: 6) {
                        Text(item.title)
                            .font(.headline)
                            .foregroundStyle(item.isCompleted ? .secondary : .primary)
                            .strikethrough(item.isCompleted, color: .secondary)
                        Text(item.course)
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(.secondary)
                        HStack(spacing: 10) {
                            Label(item.dueLabel, systemImage: "calendar.badge.clock")
                            Label("\(item.priority)優先", systemImage: "flag.fill")
                        }
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    }

                    Spacer()
                }
                .padding(18)
                .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            }
        }
    }

    private var progressSnapshot: some View {
        let progress = store.plannerProgress
        let targets = store.plannerTargets

        return VStack(alignment: .leading, spacing: 14) {
            sectionHeader(title: "學分摘要", subtitle: "原始學分規劃功能的精簡快照")

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
