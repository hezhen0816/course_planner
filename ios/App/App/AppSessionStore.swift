import SwiftUI

@MainActor
final class AppSessionStore: ObservableObject {
    @Published var selectedTab: AppTab = .home
    @Published var schoolAccount: String = "B11209001"
    @Published var schoolPassword: String = "courseplanner"
    @Published var reminderMinutes: Int = 10
    @Published var plannerTargets: PlannerTarget = .default
    @Published var plannerSemesters: [PlannerSemester] = []

    let studentName: String = "何哲"
    let subtitle: String = "資料展示模式"
    let upcomingCourses: [UpcomingCourse]
    let todoItems: [TodoItem]
    let scheduleEntries: [ScheduleEntry]

    init() {
        self.upcomingCourses = [
            UpcomingCourse(
                title: "人機互動設計",
                subtitle: "今日第一堂課",
                timeLabel: "09:10 - 12:00",
                room: "TR-512",
                weekday: .monday,
                note: "課前帶上分組 wireframe 草稿"
            ),
            UpcomingCourse(
                title: "資料庫系統",
                subtitle: "期中專案進度確認",
                timeLabel: "13:20 - 16:10",
                room: "RB-105",
                weekday: .tuesday,
                note: "準備 schema 關聯圖與 SQL demo"
            ),
            UpcomingCourse(
                title: "數位產品企劃",
                subtitle: "提案彩排",
                timeLabel: "10:20 - 12:10",
                room: "IB-302",
                weekday: .thursday,
                note: "10 分鐘內完成 pitch"
            )
        ]

        self.todoItems = [
            TodoItem(
                title: "完成期中簡報首頁與資訊架構圖",
                course: "數位產品企劃",
                dueLabel: "今天 18:00 前",
                priority: "高",
                isCompleted: false
            ),
            TodoItem(
                title: "上傳 Lab 2 程式與測試截圖",
                course: "資料庫系統",
                dueLabel: "明天 23:59 前",
                priority: "中",
                isCompleted: false
            ),
            TodoItem(
                title: "閱讀 HCI 第 6 章並整理筆記",
                course: "人機互動設計",
                dueLabel: "本週五前",
                priority: "低",
                isCompleted: true
            )
        ]

        self.scheduleEntries = [
            ScheduleEntry(weekday: .monday, title: "人機互動設計", timeRange: "09:10 - 12:00", room: "TR-512", instructor: "王怡文", accent: .compulsory),
            ScheduleEntry(weekday: .monday, title: "通識：科技與社會", timeRange: "13:20 - 15:10", room: "AU-101", instructor: "陳明志", accent: .genEd),
            ScheduleEntry(weekday: .tuesday, title: "資料庫系統", timeRange: "13:20 - 16:10", room: "RB-105", instructor: "林大鈞", accent: .compulsory),
            ScheduleEntry(weekday: .wednesday, title: "英文簡報與溝通", timeRange: "10:20 - 12:10", room: "IB-201", instructor: "Jessica Wu", accent: .english),
            ScheduleEntry(weekday: .thursday, title: "數位產品企劃", timeRange: "10:20 - 12:10", room: "IB-302", instructor: "黃詠真", accent: .elective),
            ScheduleEntry(weekday: .friday, title: "體育：羽球", timeRange: "15:30 - 17:20", room: "體育館 B1", instructor: "張嘉宏", accent: .pe)
        ]

        self.plannerSemesters = [
            PlannerSemester(name: "大一上", courses: [
                PlannerCourse(name: "微積分(一)", credits: 3, category: .compulsory, program: .home, instructor: "黃建豪", location: "MA-201", time: "一 1,2,3"),
                PlannerCourse(name: "程式設計", credits: 3, category: .compulsory, program: .home, instructor: "李宜庭", location: "IB-105", time: "二 2,3,4"),
                PlannerCourse(name: "大學國文", credits: 2, category: .chinese, program: .home, instructor: "林佳穎", location: "TR-301", time: "三 6,7")
            ]),
            PlannerSemester(name: "大一下", courses: [
                PlannerCourse(name: "微積分(二)", credits: 3, category: .compulsory, program: .home, instructor: "黃建豪", location: "MA-201", time: "一 1,2,3"),
                PlannerCourse(name: "資料結構", credits: 3, category: .compulsory, program: .home, instructor: "陳奕安", location: "IB-210", time: "四 2,3,4"),
                PlannerCourse(name: "英文聽講", credits: 2, category: .english, program: .home, instructor: "Amy Chen", location: "IB-406", time: "五 3,4")
            ]),
            PlannerSemester(name: "大二上", courses: [
                PlannerCourse(name: "機率", credits: 3, category: .compulsory, program: .home, instructor: "楊文祥", location: "MA-105", time: "二 1,2,3"),
                PlannerCourse(name: "資料庫系統", credits: 3, category: .compulsory, program: .home, instructor: "林大鈞", location: "RB-105", time: "二 6,7,8"),
                PlannerCourse(name: "通識：當代文明", credits: 2, category: .genEd, program: .home, dimension: .B, instructor: "王瑞華", location: "AU-205", time: "三 3,4")
            ]),
            PlannerSemester(name: "大二下", courses: [
                PlannerCourse(name: "作業系統", credits: 3, category: .compulsory, program: .home, instructor: "陳柏凱", location: "RB-202", time: "一 6,7,8"),
                PlannerCourse(name: "英文簡報與溝通", credits: 2, category: .english, program: .home, instructor: "Jessica Wu", location: "IB-201", time: "三 2,3"),
                PlannerCourse(name: "體育：游泳", credits: 0, category: .pe, program: .home, instructor: "張嘉宏", location: "游泳館", time: "五 7,8")
            ]),
            PlannerSemester(name: "大三上", courses: [
                PlannerCourse(name: "人機互動設計", credits: 3, category: .elective, program: .home, instructor: "王怡文", location: "TR-512", time: "一 2,3,4"),
                PlannerCourse(name: "通識：美感與人生", credits: 2, category: .genEd, program: .home, dimension: .C, instructor: "張若琳", location: "AU-110", time: "二 8,9"),
                PlannerCourse(name: "社會實踐", credits: 0, category: .social, program: .home, instructor: "服務學習中心", location: "校外服務", time: "彈性安排")
            ]),
            PlannerSemester(name: "大三下", courses: [
                PlannerCourse(name: "數位產品企劃", credits: 3, category: .elective, program: .home, instructor: "黃詠真", location: "IB-302", time: "四 3,4,5"),
                PlannerCourse(name: "通識：群己制度", credits: 2, category: .genEd, program: .home, dimension: .E, instructor: "宋哲民", location: "AU-220", time: "四 8,9")
            ]),
            PlannerSemester(name: "大四上", courses: [
                PlannerCourse(name: "畢業專題(一)", credits: 3, category: .compulsory, program: .home, instructor: "專題指導老師", location: "研究室", time: "另行約定"),
                PlannerCourse(name: "行動應用設計", credits: 3, category: .elective, program: .home, instructor: "邱正杰", location: "IB-506", time: "三 6,7,8")
            ]),
            PlannerSemester(name: "大四下", courses: [
                PlannerCourse(name: "畢業專題(二)", credits: 3, category: .compulsory, program: .home, instructor: "專題指導老師", location: "研究室", time: "另行約定"),
                PlannerCourse(name: "通識：自然生命", credits: 2, category: .genEd, program: .home, dimension: .F, instructor: "蘇品涵", location: "AU-115", time: "二 6,7")
            ])
        ]
    }

    var nextUpcomingCourse: UpcomingCourse? {
        upcomingCourses.first
    }

    var plannerProgress: PlannerProgress {
        PlannerProgress.calculate(from: plannerSemesters)
    }

    func credits(for semester: PlannerSemester) -> Double {
        semester.courses.reduce(0) { partialResult, course in
            if course.category == .pe {
                return partialResult
            }
            return partialResult + course.credits
        }
    }

    func addCourse(_ course: PlannerCourse, to semesterID: PlannerSemester.ID) {
        guard let index = plannerSemesters.firstIndex(where: { $0.id == semesterID }) else {
            return
        }
        plannerSemesters[index].courses.append(course)
    }

    func updateCourse(_ course: PlannerCourse, in semesterID: PlannerSemester.ID) {
        guard let semesterIndex = plannerSemesters.firstIndex(where: { $0.id == semesterID }) else {
            return
        }
        guard let courseIndex = plannerSemesters[semesterIndex].courses.firstIndex(where: { $0.id == course.id }) else {
            return
        }
        plannerSemesters[semesterIndex].courses[courseIndex] = course
    }

    func updateTargets(_ targets: PlannerTarget) {
        plannerTargets = targets
    }
}
