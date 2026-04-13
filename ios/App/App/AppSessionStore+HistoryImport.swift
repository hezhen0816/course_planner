import Foundation

extension AppSessionStore {
    func importAcademicHistory() async {
        let username = schoolAccount.trimmingCharacters(in: .whitespacesAndNewlines)
        let password = schoolPassword.trimmingCharacters(in: .whitespacesAndNewlines)
        historyImportErrorMessage = nil
        historyImportNoticeMessage = nil

        guard !username.isEmpty, !password.isEmpty else {
            historyImportErrorMessage = "請先輸入學校帳號與密碼"
            return
        }

        do {
            let endpoint = try Self.backendURL(path: "/api/history/import")
            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(
                HistoryImportRequest(
                    username: username,
                    password: password,
                    profileKey: username,
                    persistToSupabase: true,
                    verifySSL: false
                )
            )

            let (data, response) = try await URLSession.shared.data(for: request)
            try validateHTTPResponse(response, data: data)

            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let payload = try decoder.decode(HistoryImportResponse.self, from: data)

            if let payloadStudentName = payload.studentName?.trimmingCharacters(in: .whitespacesAndNewlines), !payloadStudentName.isEmpty {
                studentName = payloadStudentName.replacingOccurrences(of: "姓名：", with: "")
            }

            let summary = mergeImportedHistory(
                payload.records,
                studentNumber: payload.studentNo ?? username
            )
            try await persistPlannerData()

            historyImportNoticeMessage = [
                "已匯入 \(payload.recordCount) 筆歷史修課紀錄",
                "新增 \(summary.inserted) 筆",
                "更新 \(summary.updated) 筆",
                "略過 \(summary.skipped) 筆",
            ].joined(separator: "・")
        } catch {
            historyImportErrorMessage = error.localizedDescription
        }
    }

    func mergeImportedHistory(_ records: [HistoryCourseRecord], studentNumber: String?) -> HistoryImportSummary {
        var summary = HistoryImportSummary()

        for record in records.sorted(by: historyRecordSort) {
            let targetIndex = ensureSemesterIndex(for: record.academicTerm, studentNumber: studentNumber)
            let importedCourse = plannerCourse(from: record)
            let importedName = importedCourse.name.trimmingCharacters(in: .whitespacesAndNewlines)

            if let existingIndex = plannerSemesters[targetIndex].courses.firstIndex(where: {
                historyImportedCourseCode(from: $0.notes) == record.courseCode
            }) {
                let existingCourse = plannerSemesters[targetIndex].courses[existingIndex]
                plannerSemesters[targetIndex].courses[existingIndex] = mergedImportedHistoryCourse(
                    existing: existingCourse,
                    imported: importedCourse
                )
                summary.updated += 1
                continue
            }

            if plannerSemesters[targetIndex].courses.contains(where: {
                $0.name.trimmingCharacters(in: .whitespacesAndNewlines) == importedName
            }) {
                summary.skipped += 1
                continue
            }

            plannerSemesters[targetIndex].courses.append(importedCourse)
            summary.inserted += 1
        }

        return summary
    }

    func mergedImportedHistoryCourse(existing: PlannerCourse, imported: PlannerCourse) -> PlannerCourse {
        var merged = existing
        merged.name = imported.name
        merged.credits = imported.credits
        merged.notes = mergedHistoryNotes(existingNotes: existing.notes, importedNotes: imported.notes)
        return merged
    }

    func ensureSemesterIndex(for academicTerm: String, studentNumber: String?) -> Int {
        if let computedIndex = plannerSemesterIndex(for: academicTerm, studentNumber: studentNumber) {
            while plannerSemesters.count <= computedIndex {
                let nextIndex = plannerSemesters.count
                plannerSemesters.append(
                    PlannerSemester(
                        name: semesterName(forSequentialIndex: nextIndex),
                        courses: []
                    )
                )
            }
            return computedIndex
        }

        let fallbackName = fallbackSemesterName(for: academicTerm)
        if let existingIndex = plannerSemesters.firstIndex(where: { $0.name == fallbackName }) {
            return existingIndex
        }

        plannerSemesters.append(PlannerSemester(name: fallbackName, courses: []))
        return plannerSemesters.count - 1
    }

    func plannerSemesterIndex(for academicTerm: String, studentNumber: String?) -> Int? {
        guard academicTerm.count >= 4 else {
            return nil
        }

        let termYearText = String(academicTerm.prefix(3))
        let termSemesterText = String(academicTerm.suffix(1))
        guard
            let termYear = Int(termYearText),
            let termSemester = Int(termSemesterText),
            (1 ... 2).contains(termSemester),
            let admissionYear = admissionYear(from: studentNumber ?? schoolAccount)
        else {
            return nil
        }

        let yearOffset = termYear - admissionYear
        guard yearOffset >= 0 else {
            return nil
        }

        return yearOffset * 2 + (termSemester - 1)
    }

    func admissionYear(from studentNumber: String) -> Int? {
        let trimmed = studentNumber.trimmingCharacters(in: .whitespacesAndNewlines)
        let match = trimmed.range(of: #"\d{3}"#, options: .regularExpression)
        guard let match else {
            return nil
        }
        return Int(trimmed[match])
    }

    func semesterName(forSequentialIndex index: Int) -> String {
        let academicYear = index / 2
        let semesterLabel = index.isMultiple(of: 2) ? "上" : "下"
        let yearLabel: String

        switch academicYear {
        case 0:
            yearLabel = "大一"
        case 1:
            yearLabel = "大二"
        case 2:
            yearLabel = "大三"
        case 3:
            yearLabel = "大四"
        default:
            yearLabel = "第\(academicYear + 1)學年"
        }

        return "\(yearLabel)\(semesterLabel)"
    }

    func fallbackSemesterName(for academicTerm: String) -> String {
        guard academicTerm.count >= 4 else {
            return academicTerm
        }

        let year = String(academicTerm.prefix(3))
        let semester = academicTerm.hasSuffix("1") ? "上" : "下"
        return "\(year)學年\(semester)"
    }

    func plannerCourse(from record: HistoryCourseRecord) -> PlannerCourse {
        let cleanedName = sanitizedHistoryCourseName(record.courseName)
        let category = plannerCategory(
            forHistoryCourseName: cleanedName,
            courseCode: record.courseCode,
            sourceCategory: record.category
        )

        return PlannerCourse(
            name: cleanedName,
            credits: parsedCredits(record.earnedCredits),
            category: category,
            program: .home,
            notes: historyNotes(for: record)
        )
    }

    func sanitizedHistoryCourseName(_ rawName: String) -> String {
        rawName
            .replacingOccurrences(of: "★", with: "")
            .replacingOccurrences(of: "◆", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    func parsedCredits(_ rawValue: String) -> Double {
        Double(rawValue.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
    }

    func plannerCategory(forHistoryCourseName name: String, courseCode: String, sourceCategory: String) -> PlannerCourseCategory {
        let categoryText = sourceCategory
        let normalizedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        let code = courseCode.uppercased()

        if normalizedName.contains("體育") || code.hasPrefix("PE") {
            return .pe
        }
        if
            normalizedName.contains("國文")
            || normalizedName.contains("中文")
            || normalizedName.contains("文學")
            || normalizedName.contains("表達")
        {
            return .chinese
        }
        if normalizedName.contains("英文") || normalizedName.contains("英語") || code.hasPrefix("CC101") || code.hasPrefix("CC105") {
            return .english
        }
        if normalizedName.contains("通識") || code.hasPrefix("GE") || categoryText.contains("通識") {
            return .genEd
        }
        if categoryText.contains("社會") {
            return .social
        }
        if categoryText.contains("必修") {
            return .compulsory
        }
        if categoryText.contains("選修") {
            return .elective
        }
        return .other
    }

    func historyNotes(for record: HistoryCourseRecord) -> String {
        [
            "歷史修課匯入",
            "課碼: \(record.courseCode)",
            "學年期: \(record.academicTerm)",
            "成績: \(record.grade)",
            "來源分類: \(record.category)"
        ].joined(separator: "\n")
    }

    func mergedHistoryNotes(existingNotes: String, importedNotes: String) -> String {
        let preservedNotes = strippedHistoryMetadata(from: existingNotes)
        guard !preservedNotes.isEmpty else {
            return importedNotes
        }
        return importedNotes + "\n\n" + preservedNotes
    }

    func strippedHistoryMetadata(from notes: String) -> String {
        let metadataPrefixes = [
            "歷史修課匯入",
            "課碼: ",
            "學年期: ",
            "成績: ",
            "來源分類: "
        ]

        let filteredLines = notes
            .components(separatedBy: .newlines)
            .filter { line in
                let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmed.isEmpty else {
                    return false
                }
                return !metadataPrefixes.contains(where: { trimmed.hasPrefix($0) })
            }

        return filteredLines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    func historyImportedCourseCode(from notes: String) -> String? {
        let lines = notes.split(separator: "\n")
        for line in lines {
            if line.hasPrefix("課碼: ") {
                return line.replacingOccurrences(of: "課碼: ", with: "")
            }
        }
        return nil
    }

    func historySourceCategory(from notes: String) -> String? {
        let lines = notes.split(separator: "\n")
        for line in lines {
            if line.hasPrefix("來源分類: ") {
                return line.replacingOccurrences(of: "來源分類: ", with: "")
            }
        }
        return nil
    }

    func historyRecordSort(lhs: HistoryCourseRecord, rhs: HistoryCourseRecord) -> Bool {
        if lhs.academicTerm == rhs.academicTerm {
            return lhs.courseCode < rhs.courseCode
        }
        return lhs.academicTerm < rhs.academicTerm
    }
}
