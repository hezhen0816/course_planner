import SwiftUI

struct PlannerView: View {
    @EnvironmentObject private var store: AppSessionStore
    @State private var expandedSemesters: Set<UUID> = []
    @State private var selectedCourseContext: PlannerCourseContext?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                pageHeader
                plannerHeader
                progressCards
                semestersSection
            }
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 32)
        }
        .background(Color(.systemGroupedBackground))
        .toolbar(.hidden, for: .navigationBar)
        .sheet(item: $selectedCourseContext) { context in
            NavigationStack {
                CourseNoteEditor(semesterID: context.semesterID, course: context.course)
                    .environmentObject(store)
            }
        }
        .onAppear {
            if expandedSemesters.isEmpty, let firstSemester = store.plannerSemesters.first?.id {
                expandedSemesters.insert(firstSemester)
            }
        }
    }

    private var pageHeader: some View {
        Text("學分規劃")
            .font(.system(size: 34, weight: .bold, design: .rounded))
            .foregroundStyle(.primary)
            .padding(.top, 4)
    }

    private var plannerHeader: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("把修課進度整理成清楚的畢業路線")
                .font(.title3.weight(.bold))
            Text("用八學期視角整理課程、門檻與修課重點，隨時調整你的規劃。")
                .font(.footnote)
                .foregroundStyle(.secondary)

            Label("新增課程與畢業門檻請在網頁版調整；手機專注在課表、課堂筆記與成績試算。", systemImage: "info.circle")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
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
                                                // 課碼取自網頁版寫入的 scheduledOffering
                                                if !course.courseNo.isEmpty {
                                                    Label(course.courseNo, systemImage: "number")
                                                        .monospaced()
                                                }
                                                Label("\(course.credits, specifier: "%.0f") 學分", systemImage: "graduationcap")
                                                Label(course.program.title, systemImage: "folder")
                                                if course.dimension != .none {
                                                    Label(course.dimension.title, systemImage: "square.grid.2x2")
                                                }
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
