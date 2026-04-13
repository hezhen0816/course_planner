import SwiftUI

enum PlannerCourseCategory: String, CaseIterable, Identifiable, Codable {
    case compulsory
    case elective
    case chinese
    case english
    case genEd
    case pe
    case social
    case other
    case unclassified

    var id: String { rawValue }

    var title: String {
        switch self {
        case .compulsory:
            return "必修"
        case .elective:
            return "選修"
        case .chinese:
            return "國文"
        case .english:
            return "英文"
        case .genEd:
            return "通識"
        case .pe:
            return "體育"
        case .social:
            return "社會實踐"
        case .other:
            return "其他"
        case .unclassified:
            return "未歸類"
        }
    }

    var tint: Color {
        switch self {
        case .compulsory:
            return .red
        case .elective:
            return .blue
        case .chinese:
            return .orange
        case .english:
            return .indigo
        case .genEd:
            return .purple
        case .pe:
            return .green
        case .social:
            return .yellow
        case .other:
            return .teal
        case .unclassified:
            return .gray
        }
    }
}

enum PlannerCourseProgram: String, CaseIterable, Identifiable {
    case home
    case doubleMajor
    case minor
    case other

    var id: String { rawValue }

    var title: String {
        switch self {
        case .home:
            return "本系"
        case .doubleMajor:
            return "雙主修"
        case .minor:
            return "輔修"
        case .other:
            return "其他"
        }
    }
}

enum PlannerGenEdDimension: String, CaseIterable, Identifiable {
    case A
    case B
    case C
    case D
    case E
    case F
    case none

    var id: String { rawValue }

    var title: String {
        switch self {
        case .A:
            return "A 人文素養"
        case .B:
            return "B 當代文明"
        case .C:
            return "C 美感與人生"
        case .D:
            return "D 社會歷史"
        case .E:
            return "E 群己制度"
        case .F:
            return "F 自然生命"
        case .none:
            return "未設定"
        }
    }
}


struct PlannerCourse: Identifiable, Equatable {
    var id = UUID()
    var name: String
    var credits: Double
    var category: PlannerCourseCategory
    var program: PlannerCourseProgram
    var dimension: PlannerGenEdDimension = .none
    var instructor: String = ""
    var location: String = ""
    var time: String = ""
    var notes: String = ""
}

struct PlannerSemester: Identifiable, Equatable {
    let id: UUID
    var name: String
    var courses: [PlannerCourse]

    init(id: UUID = UUID(), name: String, courses: [PlannerCourse]) {
        self.id = id
        self.name = name
        self.courses = courses
    }
}

struct PlannerTarget: Equatable {
    var total: Double
    var chinese: Double
    var english: Double
    var genEd: Double
    var peSemesters: Double
    var social: Double
    var homeCompulsory: Double
    var homeElective: Double
    var doubleMajor: Double
    var minor: Double

    static let `default` = PlannerTarget(
        total: 133,
        chinese: 3,
        english: 12,
        genEd: 16,
        peSemesters: 6,
        social: 1,
        homeCompulsory: 72,
        homeElective: 24,
        doubleMajor: 0,
        minor: 0
    )
}

struct PlannerProgress {
    var total: Double = 0
    var chinese: Double = 0
    var english: Double = 0
    var genEd: Double = 0
    var peSemesters: Double = 0
    var social: Double = 0
    var homeCompulsory: Double = 0
    var homeElective: Double = 0
    var doubleMajor: Double = 0
    var minor: Double = 0
    var genEdDimensions: Set<PlannerGenEdDimension> = []

    static func calculate(from semesters: [PlannerSemester]) -> PlannerProgress {
        var progress = PlannerProgress()

        for semester in semesters {
            var hasPE = false

            for course in semester.courses {
                let credits = course.credits

                if course.category == .pe {
                    hasPE = true
                    continue
                }

                if course.category == .social {
                    progress.social += 1
                    continue
                }

                progress.total += credits

                switch course.category {
                case .chinese:
                    progress.chinese += credits
                case .english:
                    progress.english += credits
                case .genEd:
                    progress.genEd += credits
                    if course.dimension != .none {
                        progress.genEdDimensions.insert(course.dimension)
                    }
                case .compulsory where course.program == .home:
                    progress.homeCompulsory += credits
                case .elective where course.program == .home:
                    progress.homeElective += credits
                default:
                    break
                }

                switch course.program {
                case .doubleMajor:
                    progress.doubleMajor += credits
                case .minor:
                    progress.minor += credits
                default:
                    break
                }
            }

            if hasPE {
                progress.peSemesters += 1
            }
        }

        return progress
    }
}
