import Foundation

enum ScheduleSyncState: Equatable {
    case idle
    case syncing
    case synced
    case failed(String)

    var label: String {
        switch self {
        case .idle:
            return "尚未同步"
        case .syncing:
            return "同步中"
        case .synced:
            return "已同步"
        case .failed(let message):
            return message
        }
    }
}

struct UpcomingCourse: Identifiable {
    let id = UUID()
    let title: String
    let subtitle: String
    let timeLabel: String
    let slotTimes: [String]
    let room: String
    let weekday: Weekday
    let note: String

    var startTime: DateComponents {
        sessionTimeRanges.first?.start ?? parsedTimeRange(timeLabel, fallbackStartHour: 9, fallbackEndHour: 10).start
    }

    var endTime: DateComponents {
        sessionTimeRanges.last?.end ?? parsedTimeRange(timeLabel, fallbackStartHour: 9, fallbackEndHour: 10).end
    }

    func startDate(on referenceDate: Date, calendar: Calendar = .current) -> Date? {
        calendar.date(
            bySettingHour: startTime.hour ?? 9,
            minute: startTime.minute ?? 0,
            second: 0,
            of: referenceDate
        )
    }

    func endDate(on referenceDate: Date, calendar: Calendar = .current) -> Date? {
        calendar.date(
            bySettingHour: endTime.hour ?? 10,
            minute: endTime.minute ?? 0,
            second: 0,
            of: referenceDate
        )
    }

    func hasEnded(on referenceDate: Date, calendar: Calendar = .current) -> Bool {
        guard let endDate = endDate(on: referenceDate, calendar: calendar) else {
            return false
        }
        return endDate <= referenceDate
    }

    var sessionTimeRanges: [(start: DateComponents, end: DateComponents)] {
        let rawRanges = slotTimes.isEmpty ? [timeLabel] : slotTimes
        return rawRanges.map {
            parsedTimeRange($0, fallbackStartHour: 9, fallbackEndHour: 10)
        }
    }

    func countdownState(on referenceDate: Date, calendar: Calendar = .current) -> CountdownState? {
        var sessions: [(start: Date, end: Date)] = []
        for range in sessionTimeRanges {
            guard
                let start = calendar.date(
                    bySettingHour: range.start.hour ?? 9,
                    minute: range.start.minute ?? 0,
                    second: 0,
                    of: referenceDate
                ),
                let end = calendar.date(
                    bySettingHour: range.end.hour ?? 10,
                    minute: range.end.minute ?? 0,
                    second: 0,
                    of: referenceDate
                )
            else {
                continue
            }
            sessions.append((start: start, end: end))
        }

        guard let firstSession = sessions.first, let lastSession = sessions.last else {
            return nil
        }

        if referenceDate < firstSession.start {
            return .beforeClass(firstSession.start)
        }

        for (index, session) in sessions.enumerated() {
            if referenceDate < session.start {
                return .betweenSessions(session.start)
            }

            if referenceDate < session.end {
                if index < sessions.count - 1, let nextSession = sessions[safe: index + 1], referenceDate < nextSession.start {
                    return .inClass(session.end)
                }
                return .inClass(session.end)
            }

            if let nextSession = sessions[safe: index + 1], referenceDate < nextSession.start {
                return .betweenSessions(nextSession.start)
            }
        }

        if referenceDate < lastSession.end {
            return .inClass(lastSession.end)
        }

        return nil
    }

    private func parsedTimeRange(_ label: String, fallbackStartHour: Int, fallbackEndHour: Int) -> (start: DateComponents, end: DateComponents) {
        let matches = label.matches(of: /(\d{1,2}):(\d{2})/)
        if matches.count >= 2 {
            let start = matches[0]
            let end = matches[1]
            return (
                DateComponents(
                    hour: Int(start.output.1) ?? fallbackStartHour,
                    minute: Int(start.output.2) ?? 0
                ),
                DateComponents(
                    hour: Int(end.output.1) ?? fallbackEndHour,
                    minute: Int(end.output.2) ?? 0
                )
            )
        }

        let pieces = label
            .replacingOccurrences(of: "～", with: "-")
            .replacingOccurrences(of: "~", with: "-")
            .components(separatedBy: "-")
        let startLabel = pieces.first?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "\(fallbackStartHour):00"
        let endLabel = pieces.dropFirst().first?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "\(fallbackEndHour):00"
        return (
            parseSingleTime(startLabel, fallbackHour: fallbackStartHour),
            parseSingleTime(endLabel, fallbackHour: fallbackEndHour)
        )
    }

    private func parseSingleTime(_ label: String, fallbackHour: Int) -> DateComponents {
        if let match = label.firstMatch(of: /(\d{1,2}):(\d{2})/) {
            return DateComponents(
                hour: Int(match.output.1) ?? fallbackHour,
                minute: Int(match.output.2) ?? 0
            )
        }

        let parts = label.split(separator: ":")
        let hour = Int(parts.first ?? Substring("\(fallbackHour)")) ?? fallbackHour
        let minute = Int(parts.dropFirst().first ?? "0") ?? 0
        return DateComponents(hour: hour, minute: minute)
    }
}

enum CountdownState {
    case beforeClass(Date)
    case inClass(Date)
    case betweenSessions(Date)
}

struct ScheduleEntry: Identifiable, Codable {
    let id = UUID()
    let weekday: Weekday
    let title: String
    let timeRange: String
    let slotTimes: [String]
    let room: String
    let instructor: String
    let accent: PlannerCourseCategory

    enum CodingKeys: String, CodingKey {
        case weekday
        case title
        case timeRange
        case slotTimes
        case room
        case instructor
        case accent
    }

    init(
        weekday: Weekday,
        title: String,
        timeRange: String,
        slotTimes: [String] = [],
        room: String,
        instructor: String,
        accent: PlannerCourseCategory
    ) {
        self.weekday = weekday
        self.title = title
        self.timeRange = timeRange
        self.slotTimes = slotTimes
        self.room = room
        self.instructor = instructor
        self.accent = accent
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        weekday = try container.decode(Weekday.self, forKey: .weekday)
        title = try container.decode(String.self, forKey: .title)
        timeRange = try container.decode(String.self, forKey: .timeRange)
        slotTimes = try container.decodeIfPresent([String].self, forKey: .slotTimes) ?? []
        room = try container.decode(String.self, forKey: .room)
        instructor = try container.decode(String.self, forKey: .instructor)
        accent = try container.decode(PlannerCourseCategory.self, forKey: .accent)
    }
}

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
