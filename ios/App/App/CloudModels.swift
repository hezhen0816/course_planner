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

struct CloudAppDataPayload: Codable {
    let semesters: [CloudSemester]?
    let targets: CloudTargets?
    let settings: CloudUserSettings?
}

struct CloudSemester: Codable {
    let id: String
    let name: String
    let courses: [CloudCourse]
}

struct CloudCourse: Codable {
    let id: String
    let name: String
    let credits: Double
    let category: String
    let program: String?
    let dimension: String?
    let details: CloudCourseDetails?
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
    let schoolPassword: String?
    let reminderMinutes: Int?

    enum CodingKeys: String, CodingKey {
        case schoolAccount = "school_account"
        case schoolPassword = "school_password"
        case reminderMinutes = "reminder_minutes"
    }
}

struct CloudUserDataRecord: Decodable {
    let content: CloudAppDataPayload
}
