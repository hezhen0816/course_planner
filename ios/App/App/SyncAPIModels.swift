import Foundation

struct ScheduleSyncRequest: Encodable {
    let username: String
    let password: String
    let profileKey: String
    let persistToSupabase: Bool
    let verifySSL: Bool

    enum CodingKeys: String, CodingKey {
        case username
        case password
        case profileKey = "profile_key"
        case persistToSupabase = "persist_to_supabase"
        case verifySSL = "verify_ssl"
    }
}

struct HistoryImportRequest: Encodable {
    let username: String
    let password: String
    let profileKey: String
    let persistToSupabase: Bool
    let verifySSL: Bool

    enum CodingKeys: String, CodingKey {
        case username
        case password
        case profileKey = "profile_key"
        case persistToSupabase = "persist_to_supabase"
        case verifySSL = "verify_ssl"
    }
}

struct MoodleAssignmentsRequest: Encodable {
    let username: String
    let password: String
    let profileKey: String
    let persistToSupabase: Bool
    let verifySSL: Bool

    enum CodingKeys: String, CodingKey {
        case username
        case password
        case profileKey = "profile_key"
        case persistToSupabase = "persist_to_supabase"
        case verifySSL = "verify_ssl"
    }
}

struct ScheduleSyncResponse: Decodable {
    let profileKey: String
    let schoolAccount: String
    let studentName: String?
    let sourceURL: String
    let pageTitle: String
    let totalCreditsText: String
    let totalCredits: Double?
    let syncedAt: Date
    let courseCount: Int
    let scheduledSlotCount: Int
    let scheduleEntryCount: Int
    let persistedToSupabase: Bool
    let courses: [RemoteCourse]
    let scheduleEntries: [RemoteScheduleEntry]

    enum CodingKeys: String, CodingKey {
        case profileKey = "profile_key"
        case schoolAccount = "school_account"
        case studentName = "student_name"
        case sourceURL = "source_url"
        case pageTitle = "page_title"
        case totalCreditsText = "total_credits_text"
        case totalCredits = "total_credits"
        case syncedAt = "synced_at"
        case courseCount = "course_count"
        case scheduledSlotCount = "scheduled_slot_count"
        case scheduleEntryCount = "schedule_entry_count"
        case persistedToSupabase = "persisted_to_supabase"
        case courses
        case scheduleEntries = "schedule_entries"
    }
}

struct HistoryImportResponse: Decodable {
    let profileKey: String
    let schoolAccount: String
    let studentName: String?
    let studentNo: String?
    let department: String?
    let status: String?
    let sourceURL: String
    let pageTitle: String
    let importedAt: Date
    let recordCount: Int
    let persistedToSupabase: Bool
    let summaryTexts: [String]
    let records: [HistoryCourseRecord]

    enum CodingKeys: String, CodingKey {
        case profileKey = "profile_key"
        case schoolAccount = "school_account"
        case studentName = "student_name"
        case studentNo = "student_no"
        case department
        case status
        case sourceURL = "source_url"
        case pageTitle = "page_title"
        case importedAt = "imported_at"
        case recordCount = "record_count"
        case persistedToSupabase = "persisted_to_supabase"
        case summaryTexts = "summary_texts"
        case records
    }
}

struct MoodleAssignmentsResponse: Decodable {
    let profileKey: String
    let schoolAccount: String
    let sourceURL: String
    let pageTitle: String
    let timelineFilter: String
    let syncedAt: Date
    let itemCount: Int
    let persistedToSupabase: Bool
    let items: [MoodleAssignmentItem]

    enum CodingKeys: String, CodingKey {
        case profileKey = "profile_key"
        case schoolAccount = "school_account"
        case sourceURL = "source_url"
        case pageTitle = "page_title"
        case timelineFilter = "timeline_filter"
        case syncedAt = "synced_at"
        case itemCount = "item_count"
        case persistedToSupabase = "persisted_to_supabase"
        case items
    }
}

struct TRRoomMeeting: Identifiable, Decodable {
    let room: String
    let node: String
    let courseNo: String
    let courseName: String
    let teacher: String

    var id: String {
        "\(room)|\(node)|\(courseNo)|\(courseName)"
    }

    enum CodingKeys: String, CodingKey {
        case room
        case node
        case courseNo = "course_no"
        case courseName = "course_name"
        case teacher
    }
}

struct TRRoomStatusResponse: Decodable {
    let semester: String
    let queriedAt: Date
    let target: String
    let node: String?
    let nodeLabel: String
    let isClassTime: Bool
    let room: String?
    let roomIsFree: Bool?
    let roomMeetings: [TRRoomMeeting]
    let freeRooms: [String]
    let busyRooms: [String]
    let totalRooms: Int
    let note: String

    enum CodingKeys: String, CodingKey {
        case semester
        case queriedAt = "queried_at"
        case target
        case node
        case nodeLabel = "node_label"
        case isClassTime = "is_class_time"
        case room
        case roomIsFree = "room_is_free"
        case roomMeetings = "room_meetings"
        case freeRooms = "free_rooms"
        case busyRooms = "busy_rooms"
        case totalRooms = "total_rooms"
        case note
    }
}

struct HistoryCourseRecord: Decodable {
    let category: String
    let courseCode: String
    let courseName: String
    let academicTerm: String
    let grade: String
    let earnedCredits: String

    enum CodingKeys: String, CodingKey {
        case category
        case courseCode = "course_code"
        case courseName = "course_name"
        case academicTerm = "academic_term"
        case grade
        case earnedCredits = "earned_credits"
    }
}

struct MoodleAssignmentItem: Identifiable, Codable {
    let dueAt: Date
    let title: String
    let summary: String
    let courseName: String
    let actionLabel: String
    let actionURL: String
    let eventURL: String
    let overdue: Bool

    var id: String {
        "\(courseName)|\(title)|\(dueAt.timeIntervalSince1970)"
    }

    enum CodingKeys: String, CodingKey {
        case dueAt = "due_at"
        case title
        case summary
        case courseName = "course_name"
        case actionLabel = "action_label"
        case actionURL = "action_url"
        case eventURL = "event_url"
        case overdue
    }
}

struct RemoteCourse: Decodable {
    let courseCode: String
    let courseName: String
    let credits: Double?
    let requiredType: String
    let professor: String
    let note: String

    enum CodingKeys: String, CodingKey {
        case courseCode = "course_code"
        case courseName = "course_name"
        case credits
        case requiredType = "required_type"
        case professor
        case note
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        courseCode = try container.decode(String.self, forKey: .courseCode)
        courseName = try container.decode(String.self, forKey: .courseName)
        requiredType = try container.decode(String.self, forKey: .requiredType)
        professor = try container.decode(String.self, forKey: .professor)
        note = try container.decode(String.self, forKey: .note)

        if let number = try? container.decode(Double.self, forKey: .credits) {
            credits = number
        } else if let text = try? container.decode(String.self, forKey: .credits) {
            credits = Double(text)
        } else {
            credits = nil
        }
    }
}

struct RemoteScheduleEntry: Decodable {
    let weekdayKey: Weekday
    let title: String
    let timeRange: String
    let slotTimes: [String]
    let room: String
    let instructor: String
    let accent: String

    enum CodingKeys: String, CodingKey {
        case weekdayKey = "weekday_key"
        case title
        case timeRange = "time_range"
        case slotTimes = "slot_times"
        case room
        case instructor
        case accent
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        weekdayKey = try container.decode(Weekday.self, forKey: .weekdayKey)
        title = try container.decode(String.self, forKey: .title)
        timeRange = try container.decode(String.self, forKey: .timeRange)
        slotTimes = try container.decodeIfPresent([String].self, forKey: .slotTimes) ?? []
        room = try container.decode(String.self, forKey: .room)
        instructor = try container.decode(String.self, forKey: .instructor)
        accent = try container.decode(String.self, forKey: .accent)
    }
}

