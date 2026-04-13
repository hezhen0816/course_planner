import SwiftUI

enum AppTab: String, CaseIterable, Hashable {
    case home
    case schedule
    case rooms
    case planner
    case settings

    var title: String {
        switch self {
        case .home:
            return "首頁"
        case .schedule:
            return "課表"
        case .rooms:
            return "空教室"
        case .planner:
            return "學分規劃"
        case .settings:
            return "設定"
        }
    }

    var systemImage: String {
        switch self {
        case .home:
            return "house.fill"
        case .schedule:
            return "calendar"
        case .rooms:
            return "door.left.hand.open"
        case .planner:
            return "chart.bar.doc.horizontal"
        case .settings:
            return "gearshape.fill"
        }
    }
}

enum Weekday: String, CaseIterable, Identifiable, Codable {
    case monday
    case tuesday
    case wednesday
    case thursday
    case friday
    case saturday
    case sunday

    var id: String { rawValue }

    var shortTitle: String {
        switch self {
        case .monday:
            return "一"
        case .tuesday:
            return "二"
        case .wednesday:
            return "三"
        case .thursday:
            return "四"
        case .friday:
            return "五"
        case .saturday:
            return "六"
        case .sunday:
            return "日"
        }
    }

    var fullTitle: String {
        "星期\(shortTitle)"
    }

    var calendarWeekday: Int {
        switch self {
        case .monday:
            return 2
        case .tuesday:
            return 3
        case .wednesday:
            return 4
        case .thursday:
            return 5
        case .friday:
            return 6
        case .saturday:
            return 7
        case .sunday:
            return 1
        }
    }

    static func currentWeekday(from date: Date = Date()) -> Weekday {
        let weekday = Calendar.current.component(.weekday, from: date)
        switch weekday {
        case 2:
            return .monday
        case 3:
            return .tuesday
        case 4:
            return .wednesday
        case 5:
            return .thursday
        case 6:
            return .friday
        case 7:
            return .saturday
        case 1:
            return .sunday
        default:
            return .monday
        }
    }
}


enum AuthFormMode {
    case login
    case signup

    var title: String {
        switch self {
        case .login:
            return "登入"
        case .signup:
            return "建立帳號"
        }
    }

    var toggleTitle: String {
        switch self {
        case .login:
            return "沒有帳號？點此建立"
        case .signup:
            return "已有帳號？點此登入"
        }
    }
}
