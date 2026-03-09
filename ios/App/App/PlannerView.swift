import SwiftUI

struct PlannerView: View {
    @EnvironmentObject private var store: AppSessionStore
    @State private var expandedSemesters: Set<UUID> = []
    @State private var addSemester: PlannerSemester?
    @State private var selectedCourseContext: PlannerCourseContext?
    @State private var isTargetSheetPresented = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                plannerHeader
                progressCards
                semestersSection
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
            .padding(.bottom, 32)
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("學分規劃")
        .navigationBarTitleDisplayMode(.large)
        .sheet(item: $addSemester) { semester in
            CourseEditorSheet(
                title: "新增課程",
                initialCourse: PlannerCourse(
                    name: "",
                    credits: 3,
                    category: .compulsory,
                    program: .home
                ),
                onSave: { newCourse in
                    store.addCourse(newCourse, to: semester.id)
                }
            )
        }
        .sheet(item: $selectedCourseContext) { context in
            CourseDetailSheet(
                semesterName: context.semesterName,
                initialCourse: context.course,
                onSave: { updatedCourse in
                    store.updateCourse(updatedCourse, in: context.semesterID)
                }
            )
        }
        .sheet(isPresented: $isTargetSheetPresented) {
            TargetSettingsSheet(
                initialTargets: store.plannerTargets,
                onSave: { targets in
                    store.updateTargets(targets)
                }
            )
        }
        .onAppear {
            if expandedSemesters.isEmpty, let firstSemester = store.plannerSemesters.first?.id {
                expandedSemesters.insert(firstSemester)
            }
        }
    }

    private var plannerHeader: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("保留原本學分規劃核心功能")
                .font(.title3.weight(.bold))
            Text("以單欄手機版重新組織進度、八學期與課程細節。")
                .font(.footnote)
                .foregroundStyle(.secondary)

            Button {
                isTargetSheetPresented = true
            } label: {
                Label("設定畢業門檻", systemImage: "slider.horizontal.3")
                    .font(.headline.weight(.semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .buttonStyle(.borderedProminent)
            .tint(.indigo)
        }
        .padding(20)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }

    private var progressCards: some View {
        let progress = store.plannerProgress
        let targets = store.plannerTargets

        return VStack(alignment: .leading, spacing: 14) {
            Text("進度摘要")
                .font(.title3.weight(.bold))

            VStack(alignment: .leading, spacing: 14) {
                PlannerProgressRow(title: "總學分", current: progress.total, target: targets.total, tint: .blue)
                PlannerProgressRow(title: "國文", current: progress.chinese, target: targets.chinese, tint: .orange)
                PlannerProgressRow(title: "英文", current: progress.english, target: targets.english, tint: .indigo)
                PlannerProgressRow(title: "通識", current: progress.genEd, target: targets.genEd, tint: .purple)
                PlannerProgressRow(title: "體育學期數", current: progress.peSemesters, target: targets.peSemesters, tint: .green)
                PlannerProgressRow(title: "本系必修", current: progress.homeCompulsory, target: targets.homeCompulsory, tint: .red)
                PlannerProgressRow(title: "本系選修", current: progress.homeElective, target: targets.homeElective, tint: .cyan)

                VStack(alignment: .leading, spacing: 8) {
                    Text("已修通識向度")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(.secondary)
                    HStack(spacing: 8) {
                        ForEach([PlannerGenEdDimension.A, .B, .C, .D, .E, .F], id: \.id) { dimension in
                            Text(dimension.rawValue)
                                .font(.caption.weight(.bold))
                                .foregroundStyle(progress.genEdDimensions.contains(dimension) ? .white : .secondary)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(
                                    progress.genEdDimensions.contains(dimension) ? Color.indigo : Color(.tertiarySystemFill),
                                    in: RoundedRectangle(cornerRadius: 12, style: .continuous)
                                )
                        }
                    }
                }
            }
            .padding(20)
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        }
    }

    private var semestersSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("八學期規劃")
                .font(.title3.weight(.bold))

            ForEach(store.plannerSemesters) { semester in
                let isExpanded = expandedSemesters.contains(semester.id)

                VStack(alignment: .leading, spacing: 16) {
                    Button {
                        toggleSemester(semester.id)
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(semester.name)
                                    .font(.headline)
                                    .foregroundStyle(.primary)
                                Text("\(Int(store.credits(for: semester))) 學分")
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Image(systemName: isExpanded ? "chevron.up.circle.fill" : "chevron.down.circle.fill")
                                .font(.title3)
                                .foregroundStyle(.indigo)
                        }
                    }
                    .buttonStyle(.plain)

                    if isExpanded {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(semester.courses) { course in
                                Button {
                                    selectedCourseContext = PlannerCourseContext(
                                        semesterID: semester.id,
                                        semesterName: semester.name,
                                        course: course
                                    )
                                } label: {
                                    HStack(alignment: .top, spacing: 12) {
                                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                                            .fill(course.category.tint.opacity(0.16))
                                            .frame(width: 12)
                                            .overlay {
                                                RoundedRectangle(cornerRadius: 10, style: .continuous)
                                                    .stroke(course.category.tint.opacity(0.4), lineWidth: 1)
                                            }

                                        VStack(alignment: .leading, spacing: 8) {
                                            HStack {
                                                Text(course.name)
                                                    .font(.headline)
                                                    .foregroundStyle(.primary)
                                                Spacer()
                                                Text(course.category.title)
                                                    .font(.caption.weight(.semibold))
                                                    .foregroundStyle(course.category.tint)
                                                    .padding(.horizontal, 10)
                                                    .padding(.vertical, 6)
                                                    .background(course.category.tint.opacity(0.12), in: Capsule())
                                            }

                                            HStack(spacing: 12) {
                                                Label("\(course.credits, specifier: "%.0f") 學分", systemImage: "graduationcap")
                                                Label(course.program.title, systemImage: "folder")
                                            }
                                            .font(.footnote)
                                            .foregroundStyle(.secondary)

                                            if !course.time.isEmpty || !course.location.isEmpty {
                                                HStack(spacing: 12) {
                                                    if !course.time.isEmpty {
                                                        Label(course.time, systemImage: "clock")
                                                    }
                                                    if !course.location.isEmpty {
                                                        Label(course.location, systemImage: "mappin.and.ellipse")
                                                    }
                                                }
                                                .font(.footnote)
                                                .foregroundStyle(.secondary)
                                            }
                                        }
                                    }
                                    .padding(16)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .background(Color(.systemBackground), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                                }
                                .buttonStyle(.plain)
                            }

                            Button {
                                addSemester = semester
                            } label: {
                                Label("新增課程", systemImage: "plus")
                                    .font(.headline.weight(.semibold))
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 14)
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }
                .padding(18)
                .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            }
        }
    }

    private func toggleSemester(_ id: UUID) {
        if expandedSemesters.contains(id) {
            expandedSemesters.remove(id)
        } else {
            expandedSemesters.insert(id)
        }
    }
}

private struct PlannerCourseContext: Identifiable {
    let semesterID: UUID
    let semesterName: String
    let course: PlannerCourse

    var id: UUID { course.id }
}

struct PlannerProgressRow: View {
    let title: String
    let current: Double
    let target: Double
    let tint: Color

    var body: some View {
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
}

struct CourseEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var course: PlannerCourse

    let title: String
    let onSave: (PlannerCourse) -> Void

    init(title: String, initialCourse: PlannerCourse, onSave: @escaping (PlannerCourse) -> Void) {
        self.title = title
        self.onSave = onSave
        _course = State(initialValue: initialCourse)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("基本資訊") {
                    TextField("課程名稱", text: $course.name)
                    TextField("授課老師", text: $course.instructor)
                    TextField("上課地點", text: $course.location)
                    TextField("上課時間", text: $course.time)
                    TextField("學分", value: $course.credits, format: .number)
                        .keyboardType(.decimalPad)
                }

                Section("課程分類") {
                    Picker("類別", selection: $course.category) {
                        ForEach(PlannerCourseCategory.allCases) { category in
                            Text(category.title).tag(category)
                        }
                    }

                    Picker("歸屬", selection: $course.program) {
                        ForEach(PlannerCourseProgram.allCases) { program in
                            Text(program.title).tag(program)
                        }
                    }

                    if course.category == .genEd {
                        Picker("通識向度", selection: $course.dimension) {
                            ForEach(PlannerGenEdDimension.allCases) { dimension in
                                Text(dimension.title).tag(dimension)
                            }
                        }
                    }
                }

                Section("備註") {
                    TextEditor(text: $course.notes)
                        .frame(minHeight: 120)
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("取消") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("儲存") {
                        onSave(course)
                        dismiss()
                    }
                    .disabled(course.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
        .presentationDetents([.large])
    }
}

struct CourseDetailSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var course: PlannerCourse

    let semesterName: String
    let onSave: (PlannerCourse) -> Void

    init(semesterName: String, initialCourse: PlannerCourse, onSave: @escaping (PlannerCourse) -> Void) {
        self.semesterName = semesterName
        self.onSave = onSave
        _course = State(initialValue: initialCourse)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(semesterName)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(.secondary)
                        Text(course.name)
                            .font(.title3.weight(.bold))
                        HStack(spacing: 12) {
                            Label("\(course.credits, specifier: "%.0f") 學分", systemImage: "graduationcap")
                            Label(course.category.title, systemImage: "tag")
                        }
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                }

                Section("授課資訊") {
                    TextField("授課老師", text: $course.instructor)
                    TextField("上課地點", text: $course.location)
                    TextField("上課時間", text: $course.time)
                }

                Section("課程屬性") {
                    Picker("類別", selection: $course.category) {
                        ForEach(PlannerCourseCategory.allCases) { category in
                            Text(category.title).tag(category)
                        }
                    }

                    Picker("歸屬", selection: $course.program) {
                        ForEach(PlannerCourseProgram.allCases) { program in
                            Text(program.title).tag(program)
                        }
                    }

                    if course.category == .genEd {
                        Picker("通識向度", selection: $course.dimension) {
                            ForEach(PlannerGenEdDimension.allCases) { dimension in
                                Text(dimension.title).tag(dimension)
                            }
                        }
                    }
                }

                Section("筆記") {
                    TextEditor(text: $course.notes)
                        .frame(minHeight: 150)
                }
            }
            .navigationTitle("課程詳情")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("關閉") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("儲存") {
                        onSave(course)
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

struct TargetSettingsSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var targets: PlannerTarget

    let onSave: (PlannerTarget) -> Void

    init(initialTargets: PlannerTarget, onSave: @escaping (PlannerTarget) -> Void) {
        self.onSave = onSave
        _targets = State(initialValue: initialTargets)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("共同必修") {
                    numberField(title: "總學分", value: $targets.total)
                    numberField(title: "國文", value: $targets.chinese)
                    numberField(title: "英文", value: $targets.english)
                    numberField(title: "通識", value: $targets.genEd)
                    numberField(title: "體育學期數", value: $targets.peSemesters)
                    numberField(title: "社會實踐", value: $targets.social)
                }

                Section("系所門檻") {
                    numberField(title: "本系必修", value: $targets.homeCompulsory)
                    numberField(title: "本系選修", value: $targets.homeElective)
                    numberField(title: "雙主修", value: $targets.doubleMajor)
                    numberField(title: "輔修", value: $targets.minor)
                }
            }
            .navigationTitle("畢業門檻")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("取消") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("儲存") {
                        onSave(targets)
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.large])
    }

    private func numberField(title: String, value: Binding<Double>) -> some View {
        HStack {
            Text(title)
            Spacer()
            TextField(title, value: value, format: .number)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.trailing)
                .foregroundStyle(.secondary)
                .frame(maxWidth: 90)
        }
    }
}
