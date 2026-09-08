import Foundation

struct SupabaseAuthUser: Codable {
    let id: String
    let email: String?
}

struct SupabaseAuthSessionResponse: Decodable {
    let accessToken: String?
    let refreshToken: String?
    let expiresAt: TimeInterval?
    let expiresIn: Int?
    let tokenType: String?
    let user: SupabaseAuthUser?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresAt = "expires_at"
        case expiresIn = "expires_in"
        case tokenType = "token_type"
        case user
    }
}

struct SupabaseStoredSession: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresAt: Date
    let userID: String
    let email: String?
}

struct SupabaseAuthErrorResponse: Decodable {
    let errorDescription: String?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case errorDescription = "error_description"
        case message
    }
}

/// 任意 JSON 值。用來原樣保存 iOS 不理解的欄位（例如網頁版的 scheduledOffering、
/// 認列來源、成績等），避免 iOS 存檔時把它們清掉。
enum JSONValue: Codable, Equatable {
    case null
    case bool(Bool)
    case number(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "無法解析的 JSON 值")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null: try container.encodeNil()
        case .bool(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .string(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        }
    }
}

/// 動態鍵，讓上面的 extras 能收下任意欄位名稱。
struct JSONCodingKey: CodingKey {
    var stringValue: String
    var intValue: Int?
    init?(stringValue: String) { self.stringValue = stringValue }
    init?(intValue: Int) { self.intValue = intValue; self.stringValue = String(intValue) }
    init(_ key: String) { self.stringValue = key }
}

/// 解碼時把 `known` 以外的鍵原樣收進字典。
func decodeExtras(from decoder: Decoder, known: Set<String>) throws -> [String: JSONValue] {
    let container = try decoder.container(keyedBy: JSONCodingKey.self)
    var extras: [String: JSONValue] = [:]
    for key in container.allKeys where !known.contains(key.stringValue) {
        extras[key.stringValue] = try container.decode(JSONValue.self, forKey: key)
    }
    return extras
}

/// 編碼時把保存下來的鍵原樣送回。
func encodeExtras(_ extras: [String: JSONValue], to encoder: Encoder) throws {
    guard !extras.isEmpty else { return }
    var container = encoder.container(keyedBy: JSONCodingKey.self)
    for (key, value) in extras {
        try container.encode(value, forKey: JSONCodingKey(key))
    }
}

struct CloudAppDataPayload: Codable {
    let semesters: [CloudSemester]?
    let targets: CloudTargets?
    let settings: CloudUserSettings?
}

struct CloudSemester: Codable {
    let id: String
    let name: String
    let courses: [CloudCourse]
    var extras: [String: JSONValue] = [:]

    private enum CodingKeys: String, CodingKey { case id, name, courses }

    init(id: String, name: String, courses: [CloudCourse], extras: [String: JSONValue] = [:]) {
        self.id = id
        self.name = name
        self.courses = courses
        self.extras = extras
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        courses = try container.decodeIfPresent([CloudCourse].self, forKey: .courses) ?? []
        extras = try decodeExtras(from: decoder, known: ["id", "name", "courses"])
    }

    func encode(to encoder: Encoder) throws {
        try encodeExtras(extras, to: encoder)
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(courses, forKey: .courses)
    }
}

struct CloudCourse: Codable {
    let id: String
    let name: String
    let credits: Double
    let category: String
    let program: String?
    let dimension: String?
    let details: CloudCourseDetails?
    /// 網頁版專有欄位（scheduledOffering、grade、認列來源、virtualSelection…）原樣保存。
    /// iOS 不顯示也不修改，但存回雲端時一定要原封不動送回，否則網頁版會整組不見。
    var extras: [String: JSONValue] = [:]

    private enum CodingKeys: String, CodingKey { case id, name, credits, category, program, dimension, details }
    private static let knownKeys: Set<String> = ["id", "name", "credits", "category", "program", "dimension", "details"]

    init(
        id: String,
        name: String,
        credits: Double,
        category: String,
        program: String?,
        dimension: String?,
        details: CloudCourseDetails?,
        extras: [String: JSONValue] = [:]
    ) {
        self.id = id
        self.name = name
        self.credits = credits
        self.category = category
        self.program = program
        self.dimension = dimension
        self.details = details
        self.extras = extras
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        credits = try container.decodeIfPresent(Double.self, forKey: .credits) ?? 0
        category = try container.decodeIfPresent(String.self, forKey: .category) ?? "other"
        program = try container.decodeIfPresent(String.self, forKey: .program)
        dimension = try container.decodeIfPresent(String.self, forKey: .dimension)
        details = try container.decodeIfPresent(CloudCourseDetails.self, forKey: .details)
        extras = try decodeExtras(from: decoder, known: Self.knownKeys)
    }

    func encode(to encoder: Encoder) throws {
        try encodeExtras(extras, to: encoder)
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(credits, forKey: .credits)
        try container.encode(category, forKey: .category)
        try container.encodeIfPresent(program, forKey: .program)
        try container.encodeIfPresent(dimension, forKey: .dimension)
        try container.encodeIfPresent(details, forKey: .details)
    }
}

struct CloudCourseDetails: Codable {
    let professor: String?
    let email: String?
    let location: String?
    let time: String?
    let link: String?
    let gradingPolicy: [CloudGradingItem]
    let notes: String?
}

struct CloudGradingItem: Codable {
    let id: String
    let name: String
    let weight: Double
    let score: Double?
}

struct CloudTargets: Codable {
    let total: Double
    let chinese: Double
    let english: Double
    let genEd: Double
    let peSemesters: Double
    let social: Double
    let homeCompulsory: Double
    let homeElective: Double
    let doubleMajor: Double
    let minor: Double

    enum CodingKeys: String, CodingKey {
        case total
        case chinese
        case english
        case genEd = "gen_ed"
        case peSemesters = "pe_semesters"
        case social
        case homeCompulsory = "home_compulsory"
        case homeElective = "home_elective"
        case doubleMajor = "double_major"
        case minor
    }
}

struct CloudUserSettings: Codable {
    let schoolAccount: String?
    let reminderMinutes: Int?
    /// 網頁版專有設定（例如 programDepartments 雙主修／輔系系所）原樣保存後送回。
    var extras: [String: JSONValue] = [:]

    enum CodingKeys: String, CodingKey {
        case schoolAccount = "school_account"
        case reminderMinutes = "reminder_minutes"
    }

    init(schoolAccount: String?, reminderMinutes: Int?, extras: [String: JSONValue] = [:]) {
        self.schoolAccount = schoolAccount
        self.reminderMinutes = reminderMinutes
        self.extras = extras
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schoolAccount = try container.decodeIfPresent(String.self, forKey: .schoolAccount)
        reminderMinutes = try container.decodeIfPresent(Int.self, forKey: .reminderMinutes)
        extras = try decodeExtras(from: decoder, known: ["school_account", "reminder_minutes"])
    }

    func encode(to encoder: Encoder) throws {
        try encodeExtras(extras, to: encoder)
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(schoolAccount, forKey: .schoolAccount)
        try container.encodeIfPresent(reminderMinutes, forKey: .reminderMinutes)
    }
}

struct CloudUserDataRecord: Decodable {
    let content: CloudAppDataPayload
}
