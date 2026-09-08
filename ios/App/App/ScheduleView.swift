import SwiftUI

struct ScheduleView: View {
    @EnvironmentObject private var store: AppSessionStore

    @State private var selectedCourseDetail: CourseDetailSelection?

    private var visibleWeekdays: [Weekday] {
        let weekdaysWithCourses = Set(store.scheduleEntries.map(\.weekday))
        return Weekday.allCases.filter { weekday in
            weekday.isRegularSchoolDay || weekdaysWithCourses.contains(weekday)
        }
    }

    private var visiblePeriods: [ClassPeriod] {
        let occupiedPeriodIDs = Set(scheduleCells.keys.map(\.periodID))
        let basePeriods = ClassPeriod.allCases.filter { period in
            period.isDaytime || occupiedPeriodIDs.contains(period.id)
        }
        return basePeriods.isEmpty ? ClassPeriod.daytimePeriods : basePeriods
    }

    private var scheduleCells: [ScheduleGridKey: [ScheduleEntry]] {
        Dictionary(grouping: expandedScheduleCells, by: \.key).mapValues { cells in
            cells.map(\.entry)
        }
    }

    private var expandedScheduleCells: [ExpandedScheduleCell] {
        store.scheduleEntries.flatMap { entry in
            let periodIDs = ClassPeriod.periodIDs(for: entry)
            return periodIDs.map { periodID in
                ExpandedScheduleCell(
                    key: ScheduleGridKey(weekday: entry.weekday, periodID: periodID),
                    entry: entry
                )
            }
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SchedulePageHeader(
                    lastSyncedAt: store.lastSyncedAt,
                    syncState: store.syncState
                )

                if store.scheduleEntries.isEmpty {
                    ContentUnavailableView(
                        "尚未有課表資料",
                        systemImage: "calendar.badge.exclamationmark",
                        description: Text("到設定同步課表後，這裡會顯示每週課程與空堂。")
                    )
                    .frame(maxWidth: .infinity)
                    .padding(.top, 36)
                } else {
                    TimelineView(.periodic(from: .now, by: 60)) { context in
                        WeeklyScheduleGrid(
                            weekdays: visibleWeekdays,
                            periods: visiblePeriods,
                            cells: scheduleCells,
                            highlightedWeekday: Weekday.currentWeekday(from: context.date),
                            currentPeriodID: ClassPeriod.currentPeriodID(at: context.date),
                            onSelectEntries: { entries in
                                selectedCourseDetail = CourseDetailSelection(entries: entries)
                            }
                        )
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 32)
        }
        .refreshable {
            await refreshSchedule()
        }
        .background(Color(.systemGroupedBackground))
        .toolbar(.hidden, for: .navigationBar)
        .sheet(item: $selectedCourseDetail) { detail in
            ScheduleCourseDetailSheet(entries: detail.entries)
                .environmentObject(store)
        }
    }

    private func refreshSchedule() async {
        await store.refreshAppContent(suppressErrors: false)
    }
}

private struct SchedulePageHeader: View {
    let lastSyncedAt: Date?
    let syncState: ScheduleSyncState

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("課表")
                .font(.system(size: 34, weight: .bold, design: .rounded))
                .foregroundStyle(.primary)
                .padding(.top, 4)
            statusLine
        }
    }

    @ViewBuilder
    private var statusLine: some View {
        if case .failed(let message) = syncState {
            Label(message, systemImage: "exclamationmark.triangle.fill")
                .font(.footnote)
                .foregroundStyle(.red)
        } else if let lastSyncedAt {
            Label("上次同步 \(Self.formatted(lastSyncedAt))", systemImage: "clock.arrow.circlepath")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private static func formatted(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_Hant_TW")
        formatter.dateFormat = "M/d HH:mm"
        return formatter.string(from: date)
    }
}

private struct WeeklyScheduleGrid: View {
    let weekdays: [Weekday]
    let periods: [ClassPeriod]
    let cells: [ScheduleGridKey: [ScheduleEntry]]
    let highlightedWeekday: Weekday
    let currentPeriodID: String?
    let onSelectEntries: ([ScheduleEntry]) -> Void

    private let cellSpacing: CGFloat = 4
    private let headerHeight: CGFloat = 28
    private let horizontalPadding: CGFloat = 6
    private let periodColumnWidth: CGFloat = 32
    private let rowHeight: CGFloat = 70

    private var gridHeight: CGFloat {
        headerHeight + CGFloat(periods.count) * rowHeight + CGFloat(periods.count) * cellSpacing + horizontalPadding * 2
    }

    var body: some View {
        GeometryReader { proxy in
            let dayColumnWidth = Self.dayColumnWidth(
                availableWidth: proxy.size.width,
                weekdayCount: weekdays.count,
                periodColumnWidth: periodColumnWidth,
                spacing: cellSpacing,
                horizontalPadding: horizontalPadding
            )

            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: 6) {
                    WeekdayHeaderRow(
                        weekdays: weekdays,
                        highlightedWeekday: highlightedWeekday,
                        periodColumnWidth: periodColumnWidth,
                        dayColumnWidth: dayColumnWidth
                    )

                    ForEach(periods) { period in
                        SchedulePeriodRow(
                            period: period,
                            weekdays: weekdays,
                            highlightedWeekday: highlightedWeekday,
                            cells: cells,
                            periodColumnWidth: periodColumnWidth,
                            dayColumnWidth: dayColumnWidth,
                            rowHeight: rowHeight,
                            currentPeriodID: currentPeriodID,
                            onSelectEntries: onSelectEntries
                        )
                    }
                }
                .padding(horizontalPadding)
            }
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .frame(height: gridHeight)
    }

    private static func dayColumnWidth(
        availableWidth: CGFloat,
        weekdayCount: Int,
        periodColumnWidth: CGFloat,
        spacing: CGFloat,
        horizontalPadding: CGFloat
    ) -> CGFloat {
        guard weekdayCount > 0 else {
            return 0
        }

        let totalSpacing = spacing * CGFloat(weekdayCount)
        let usableWidth = availableWidth - horizontalPadding * 2 - periodColumnWidth - totalSpacing
        return max(38, floor(usableWidth / CGFloat(weekdayCount)))
    }
}

private struct WeekdayHeaderRow: View {
    let weekdays: [Weekday]
    let highlightedWeekday: Weekday
    let periodColumnWidth: CGFloat
    let dayColumnWidth: CGFloat

    var body: some View {
        HStack(spacing: 4) {
            Text("節")
                .font(.caption.weight(.bold))
                .foregroundStyle(.secondary)
                .frame(width: periodColumnWidth, height: 34)

            ForEach(weekdays) { weekday in
                Text(weekday.shortTitle)
                    .font(.subheadline.weight(.bold))
                    .frame(width: dayColumnWidth, height: 34)
                    .background(
                        weekday == highlightedWeekday ? Color.indigo.opacity(0.12) : Color.clear,
                        in: RoundedRectangle(cornerRadius: 8, style: .continuous)
                    )
            }
        }
    }
}

private struct SchedulePeriodRow: View {
    let period: ClassPeriod
    let weekdays: [Weekday]
    let highlightedWeekday: Weekday
    let cells: [ScheduleGridKey: [ScheduleEntry]]
    let periodColumnWidth: CGFloat
    let dayColumnWidth: CGFloat
    let rowHeight: CGFloat
    let currentPeriodID: String?
    let onSelectEntries: ([ScheduleEntry]) -> Void

    private var isCurrentPeriod: Bool {
        period.id == currentPeriodID
    }

    var body: some View {
        HStack(spacing: 4) {
            VStack(spacing: 2) {
                Text(period.id)
                    .font(.subheadline.weight(.bold))
                    .monospacedDigit()
                Text(period.shortTimeRange)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                if isCurrentPeriod {
                    Text("現在")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.indigo)
                }
            }
            .frame(width: periodColumnWidth, height: rowHeight)
            .background(
                isCurrentPeriod ? Color.indigo.opacity(0.12) : Color.clear,
                in: RoundedRectangle(cornerRadius: 8, style: .continuous)
            )

            ForEach(weekdays) { weekday in
                let key = ScheduleGridKey(weekday: weekday, periodID: period.id)
                ScheduleGridCell(
                    entries: cells[key] ?? [],
                    isHighlighted: weekday == highlightedWeekday,
                    isCurrentPeriod: isCurrentPeriod,
                    isCurrentSlot: isCurrentPeriod && weekday == highlightedWeekday,
                    width: dayColumnWidth,
                    height: rowHeight,
                    onSelectEntries: onSelectEntries
                )
            }
        }
    }
}

private struct ScheduleGridCell: View {
    let entries: [ScheduleEntry]
    let isHighlighted: Bool
    let isCurrentPeriod: Bool
    let isCurrentSlot: Bool
    let width: CGFloat
    let height: CGFloat
    let onSelectEntries: ([ScheduleEntry]) -> Void

    var body: some View {
        Group {
            if entries.isEmpty {
                EmptyPeriodCell(
                    isHighlighted: isHighlighted,
                    isCurrentPeriod: isCurrentPeriod,
                    isCurrentSlot: isCurrentSlot
                )
            } else {
                CoursePeriodCell(
                    entries: entries,
                    isHighlighted: isHighlighted,
                    isCurrentPeriod: isCurrentPeriod,
                    isCurrentSlot: isCurrentSlot,
                    onSelectEntries: onSelectEntries
                )
            }
        }
        .frame(width: width, height: height)
    }
}

private struct EmptyPeriodCell: View {
    let isHighlighted: Bool
    let isCurrentPeriod: Bool
    let isCurrentSlot: Bool

    var body: some View {
        RoundedRectangle(cornerRadius: 8, style: .continuous)
            .fill(emptyFill)
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(emptyStroke, lineWidth: isCurrentSlot ? 2 : 1)
            )
    }

    private var emptyFill: Color {
        if isCurrentSlot {
            return Color.green.opacity(0.24)
        }
        if isHighlighted {
            return Color.green.opacity(0.15)
        }
        if isCurrentPeriod {
            return Color.indigo.opacity(0.07)
        }
        return Color(.tertiarySystemGroupedBackground)
    }

    private var emptyStroke: Color {
        if isCurrentSlot {
            return Color.indigo.opacity(0.72)
        }
        if isCurrentPeriod {
            return Color.indigo.opacity(0.28)
        }
        return isHighlighted ? Color.green.opacity(0.3) : Color.clear
    }
}

private struct CoursePeriodCell: View {
    let entries: [ScheduleEntry]
    let isHighlighted: Bool
    let isCurrentPeriod: Bool
    let isCurrentSlot: Bool
    let onSelectEntries: ([ScheduleEntry]) -> Void

    private var primaryEntry: ScheduleEntry {
        entries[0]
    }

    var body: some View {
        Button {
            onSelectEntries(entries)
        } label: {
            VStack(spacing: 0) {
                Text(primaryEntry.title)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.primary)
                    .multilineTextAlignment(.center)
                    .lineLimit(4)
                    .minimumScaleFactor(0.72)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                if entries.count > 1 {
                    Text("+\(entries.count - 1)")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 4)
            .padding(.vertical, 5)
        }
        .buttonStyle(.plain)
        .background(
            primaryEntry.accent.tint.opacity(courseOpacity),
            in: RoundedRectangle(cornerRadius: 8, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(courseStroke, lineWidth: isCurrentSlot ? 2 : 1)
        )
    }

    private var courseOpacity: Double {
        if isCurrentSlot {
            return 0.32
        }
        if isHighlighted {
            return 0.22
        }
        return isCurrentPeriod ? 0.18 : 0.13
    }

    private var courseStroke: Color {
        if isCurrentSlot {
            return Color.indigo.opacity(0.72)
        }
        if isCurrentPeriod {
            return Color.indigo.opacity(0.28)
        }
        return primaryEntry.accent.tint.opacity(isHighlighted ? 0.42 : 0)
    }
}

private struct CourseDetailSelection: Identifiable {
    let id = UUID()
    let entries: [ScheduleEntry]
}

private struct ScheduleCourseDetailSheet: View {
    @EnvironmentObject private var store: AppSessionStore
    let entries: [ScheduleEntry]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    ForEach(entries) { entry in
                        CourseDetailCard(entry: entry)
                        // 課表是進入課堂筆記與成績試算最自然的入口：上課當下就在看課表
                        if let context = store.plannerCourseContext(forTitle: entry.title) {
                            NavigationLink {
                                CourseNoteEditor(semesterID: context.semesterID, course: context.course)
                                    .environmentObject(store)
                            } label: {
                                Label("課堂筆記與成績試算", systemImage: "square.and.pencil")
                                    .font(.subheadline.weight(.semibold))
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(entry.accent.tint)
                        }
                    }
                }
                .padding(20)
            }
            .navigationTitle(entries.count > 1 ? "課程詳情" : entries[0].title)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

private struct CourseDetailCard: View {
    let entry: ScheduleEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(entry.title)
                .font(.title3.weight(.bold))
                .fixedSize(horizontal: false, vertical: true)

            detailRow(title: "星期", value: entry.weekday.fullTitle, systemImage: "calendar")
            detailRow(title: "時間", value: entry.timeRange, systemImage: "clock")

            if !entry.slotTimes.isEmpty {
                detailRow(title: "節次時間", value: entry.slotTimes.joined(separator: "\n"), systemImage: "list.bullet")
            }

            detailRow(title: "教室", value: entry.room.isEmpty ? "未提供" : entry.room, systemImage: "mappin.and.ellipse")
            detailRow(title: "教師", value: entry.instructor.isEmpty ? "未提供" : entry.instructor, systemImage: "person.crop.rectangle")
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            entry.accent.tint.opacity(0.12),
            in: RoundedRectangle(cornerRadius: 12, style: .continuous)
        )
    }

    private func detailRow(title: String, value: String, systemImage: String) -> some View {
        Label {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.primary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        } icon: {
            Image(systemName: systemImage)
                .foregroundStyle(entry.accent.tint)
        }
    }
}

private struct ExpandedScheduleCell {
    let key: ScheduleGridKey
    let entry: ScheduleEntry
}

private struct ScheduleGridKey: Hashable {
    let weekday: Weekday
    let periodID: String
}

private struct ClassPeriod: Identifiable, Hashable {
    let id: String
    let startHour: Int
    let startMinute: Int
    let endHour: Int
    let endMinute: Int

    var isDaytime: Bool {
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"].contains(id)
    }

    var shortTimeRange: String {
        "\(Self.timeText(hour: startHour, minute: startMinute))\n\(Self.timeText(hour: endHour, minute: endMinute))"
    }

    static let allCases: [ClassPeriod] = [
        ClassPeriod(id: "1", startHour: 8, startMinute: 10, endHour: 9, endMinute: 0),
        ClassPeriod(id: "2", startHour: 9, startMinute: 10, endHour: 10, endMinute: 0),
        ClassPeriod(id: "3", startHour: 10, startMinute: 20, endHour: 11, endMinute: 10),
        ClassPeriod(id: "4", startHour: 11, startMinute: 20, endHour: 12, endMinute: 10),
        ClassPeriod(id: "5", startHour: 12, startMinute: 20, endHour: 13, endMinute: 10),
        ClassPeriod(id: "6", startHour: 13, startMinute: 20, endHour: 14, endMinute: 10),
        ClassPeriod(id: "7", startHour: 14, startMinute: 20, endHour: 15, endMinute: 10),
        ClassPeriod(id: "8", startHour: 15, startMinute: 30, endHour: 16, endMinute: 20),
        ClassPeriod(id: "9", startHour: 16, startMinute: 30, endHour: 17, endMinute: 20),
        ClassPeriod(id: "10", startHour: 17, startMinute: 30, endHour: 18, endMinute: 20),
        ClassPeriod(id: "A", startHour: 18, startMinute: 25, endHour: 19, endMinute: 15),
        ClassPeriod(id: "B", startHour: 19, startMinute: 20, endHour: 20, endMinute: 10),
        ClassPeriod(id: "C", startHour: 20, startMinute: 15, endHour: 21, endMinute: 5),
        ClassPeriod(id: "D", startHour: 21, startMinute: 10, endHour: 22, endMinute: 0)
    ]

    static var daytimePeriods: [ClassPeriod] {
        allCases.filter(\.isDaytime)
    }

    static func currentPeriodID(at date: Date, calendar: Calendar = .current) -> String? {
        let components = calendar.dateComponents([.hour, .minute], from: date)
        guard let hour = components.hour, let minute = components.minute else {
            return nil
        }

        let currentMinutes = hour * 60 + minute
        return allCases.first { period in
            let startMinutes = period.startHour * 60 + period.startMinute
            let endMinutes = period.endHour * 60 + period.endMinute
            return startMinutes <= currentMinutes && currentMinutes <= endMinutes
        }?.id
    }

    static func periodIDs(for entry: ScheduleEntry) -> [String] {
        let labels = entry.slotTimes.isEmpty ? [entry.timeRange] : entry.slotTimes
        let matched = labels.compactMap { label -> String? in
            guard let start = parseStartTime(from: label) else {
                return nil
            }
            return allCases.first { period in
                period.startHour == start.hour && period.startMinute == start.minute
            }?.id
        }

        if !matched.isEmpty {
            var seen = Set<String>()
            return matched.filter { seen.insert($0).inserted }
        }

        return periodIDsCovering(timeRange: entry.timeRange)
    }

    private static func periodIDsCovering(timeRange: String) -> [String] {
        guard
            let start = parseStartTime(from: timeRange),
            let end = parseEndTime(from: timeRange)
        else {
            return []
        }

        let startMinutes = start.hour * 60 + start.minute
        let endMinutes = end.hour * 60 + end.minute
        return allCases.compactMap { period in
            let periodStart = period.startHour * 60 + period.startMinute
            let periodEnd = period.endHour * 60 + period.endMinute
            return periodStart >= startMinutes && periodEnd <= endMinutes ? period.id : nil
        }
    }

    private static func parseStartTime(from label: String) -> (hour: Int, minute: Int)? {
        parseTimes(from: label).first
    }

    private static func parseEndTime(from label: String) -> (hour: Int, minute: Int)? {
        parseTimes(from: label).dropFirst().first
    }

    private static func parseTimes(from label: String) -> [(hour: Int, minute: Int)] {
        label.matches(of: /(\d{1,2}):(\d{2})/).compactMap { match in
            guard
                let hour = Int(match.output.1),
                let minute = Int(match.output.2)
            else {
                return nil
            }
            return (hour, minute)
        }
    }

    private static func timeText(hour: Int, minute: Int) -> String {
        "\(hour):\(String(format: "%02d", minute))"
    }
}

private extension Weekday {
    var isRegularSchoolDay: Bool {
        switch self {
        case .monday, .tuesday, .wednesday, .thursday, .friday:
            return true
        case .saturday, .sunday:
            return false
        }
    }
}


/// 課堂筆記與成績試算。手機端只編輯這些「上課當下會記」的欄位；
/// 學分、類別、認列歸屬等規劃性設定留在網頁版，避免手機再長出一套殘缺的編輯器。
/// 課表與學分規劃兩個入口共用同一支，不再各有一套。
struct CourseNoteEditor: View {
    @EnvironmentObject private var store: AppSessionStore
    @Environment(\.dismiss) private var dismiss

    let semesterID: PlannerSemester.ID
    @State var course: PlannerCourse

    var body: some View {
        Form {
            Section("課堂資訊") {
                LabeledContent("課程") { Text(course.name).foregroundStyle(.secondary) }
                if !course.courseNo.isEmpty {
                    LabeledContent("課碼") { Text(course.courseNo).monospaced().foregroundStyle(.secondary) }
                }
                LabeledContent("學分") { Text("\(course.credits, specifier: "%.0f")").foregroundStyle(.secondary) }
                LabeledContent("類別") { Text(course.category.title).foregroundStyle(.secondary) }
                TextField("授課教授", text: $course.instructor)
                TextField("教授 Email", text: $course.email)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                TextField("上課地點", text: $course.location)
                TextField("上課時間", text: $course.time)
                TextField("課程連結", text: $course.link)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
            }

            Section("備註") {
                TextField("第一堂課的重點、評分方式、作業規定…", text: $course.notes, axis: .vertical)
                    .lineLimit(3...10)
            }

            Section {
                ForEach($course.gradingPolicy) { $item in
                    VStack(alignment: .leading, spacing: 8) {
                        TextField("項目名稱（例如 期中考）", text: $item.name)
                        HStack {
                            LabeledContent("權重") {
                                TextField("0", value: $item.weight, format: .number)
                                    .keyboardType(.decimalPad)
                                    .multilineTextAlignment(.trailing)
                            }
                            Text("%").foregroundStyle(.secondary)
                        }
                        LabeledContent("分數") {
                            TextField("未輸入", value: $item.score, format: .number)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.trailing)
                        }
                    }
                    .padding(.vertical, 2)
                }
                .onDelete { offsets in
                    course.gradingPolicy.remove(atOffsets: offsets)
                }

                Button {
                    course.gradingPolicy.append(PlannerGradingItem())
                } label: {
                    Label("新增評分項目", systemImage: "plus.circle")
                }
            } header: {
                Text("成績試算")
            } footer: {
                VStack(alignment: .leading, spacing: 4) {
                    Text("目前總分 \(course.projectedScore, format: .number.precision(.fractionLength(1))) 分（依已填分數的權重換算）")
                    Text(weightFooter)
                        .foregroundStyle(course.totalWeight == 100 ? Color.secondary : Color.orange)
                }
            }
        }
        .navigationTitle("課堂筆記")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("儲存") {
                    store.updateCourse(course, in: semesterID)
                    dismiss()
                }
            }
        }
    }

    private var weightFooter: String {
        let total = course.totalWeight
        if total == 100 { return "總權重 100%" }
        return "總權重 \(total.formatted(.number.precision(.fractionLength(0))))%（未達 100%，試算僅依已填項目換算）"
    }
}
