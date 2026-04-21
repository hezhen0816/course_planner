import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppSessionStore
    @State private var infoMessage: InfoMessage?
    @State private var isTargetSheetPresented = false
    @State private var isSyncing = false
    @State private var isImportingHistory = false
    @State private var isSyncingMoodleAssignments = false

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("設定")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(.primary)
                Spacer()
            }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            .padding(.bottom, 8)

            Form {
                Section("帳號") {
                    HStack(spacing: 12) {
                        Image(systemName: "person.crop.circle.badge.checkmark")
                            .font(.title3)
                            .foregroundStyle(.indigo)
                            .frame(width: 34)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("目前使用帳號")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(.secondary)
                            Text(store.currentUserEmail ?? "未登入")
                                .font(.body.weight(.semibold))
                        }
                    }

                    if let authNoticeMessage = store.authNoticeMessage {
                        Text(authNoticeMessage)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("安全性") {
                    Toggle(isOn: biometricToggleBinding) {
                        HStack(spacing: 12) {
                            Image(systemName: "faceid")
                                .font(.headline)
                                .foregroundStyle(.indigo)
                                .frame(width: 36, height: 36)
                                .background(Color.indigo.opacity(0.1), in: RoundedRectangle(cornerRadius: 12, style: .continuous))

                            VStack(alignment: .leading, spacing: 4) {
                                Text("\(store.localizedBiometricName) 登入")
                                    .font(.body.weight(.semibold))
                                Text("重新開啟 App 或回到前景時先完成本機解鎖")
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    .disabled(store.isBiometricAuthenticating)

                    if store.isBiometricAuthEnabled {
                        Button {
                            store.lockForBiometricUnlockIfNeeded()
                        } label: {
                            Label("立即鎖定 App", systemImage: "lock.fill")
                        }
                    }

                    if let biometricAuthErrorMessage = store.biometricAuthErrorMessage {
                        Text(biometricAuthErrorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    } else {
                        Text("此功能只保護這支裝置上的 App 解鎖；登出後會清除本機 Face ID 設定。")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("校務系統") {
                    TextField("學號 / 校務帳號", text: $store.schoolAccount)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled(true)
                    SecureField("密碼", text: $store.schoolPassword)

                    Text("更新課表或修課紀錄時，會透過修課羅盤的同步服務登入校務系統，再把資料整理回這個 App。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("資料同步") {
                    Button {
                        isSyncing = true
                        Task {
                            await store.syncSchedule()
                            isSyncing = false
                        }
                    } label: {
                        settingsRow(
                            title: isSyncing ? "同步中..." : "同步課表",
                            subtitle: "更新雲端課表，並同步到這支 iPhone",
                            symbol: "arrow.triangle.2.circlepath"
                        )
                    }
                    .disabled(isSyncing)

                    Button {
                        isSyncingMoodleAssignments = true
                        Task {
                            await store.syncMoodleAssignments()
                            isSyncingMoodleAssignments = false
                        }
                    } label: {
                        settingsRow(
                            title: isSyncingMoodleAssignments ? "同步中..." : "同步待繳事項",
                            subtitle: "更新 Moodle 待繳作業，並同步到這支 iPhone",
                            symbol: "checklist.checked"
                        )
                    }
                    .buttonStyle(.plain)
                    .disabled(isSyncingMoodleAssignments)

                    Button {
                        isImportingHistory = true
                        Task {
                            await store.importAcademicHistory()
                            isImportingHistory = false
                        }
                    } label: {
                        settingsRow(
                            title: isImportingHistory ? "匯入中..." : "匯入歷史修課紀錄",
                            subtitle: "整理歷年修課資料，並更新到學分規劃",
                            symbol: "square.and.arrow.down.on.square"
                        )
                    }
                    .buttonStyle(.plain)
                    .disabled(isImportingHistory)

                    if case .failed(let message) = store.syncState {
                        Text(message)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    } else {
                        Text(syncStatusDescription)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    if let historyImportErrorMessage = store.historyImportErrorMessage {
                        Text(historyImportErrorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    } else if let historyImportNoticeMessage = store.historyImportNoticeMessage {
                        Text(historyImportNoticeMessage)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    if let moodleAssignmentsErrorMessage = store.moodleAssignmentsErrorMessage {
                        Text(moodleAssignmentsErrorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    } else if let moodleAssignmentsNoticeMessage = store.moodleAssignmentsNoticeMessage {
                        Text(moodleAssignmentsNoticeMessage)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("提醒") {
                    Picker("課前提醒", selection: $store.reminderMinutes) {
                        ForEach([0, 5, 10, 15, 30, 60], id: \.self) { minutes in
                            Text(minutes == 0 ? "關閉" : "\(minutes) 分鐘前").tag(minutes)
                        }
                    }

                    if let reminderErrorMessage = store.reminderErrorMessage {
                        Text(reminderErrorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    } else if let reminderNoticeMessage = store.reminderNoticeMessage {
                        Text(reminderNoticeMessage)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else {
                        Text("會使用 iPhone 系統通知建立每週課前提醒，第一次啟用時會要求通知權限。")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("學分規劃") {
                    Button {
                        isTargetSheetPresented = true
                    } label: {
                        settingsRow(title: "設定畢業門檻", subtitle: "調整你的學分目標與畢業條件", symbol: "slider.horizontal.3")
                    }

                    let progress = store.plannerProgress
                    VStack(alignment: .leading, spacing: 10) {
                        Text("目前進度摘要")
                            .font(.subheadline.weight(.semibold))
                        PlannerProgressRow(title: "總學分", current: progress.total, target: store.plannerTargets.total, tint: .blue)
                        PlannerProgressRow(title: "通識", current: progress.genEd, target: store.plannerTargets.genEd, tint: .purple)
                        PlannerProgressRow(title: "本系必修", current: progress.homeCompulsory, target: store.plannerTargets.homeCompulsory, tint: .red)
                    }
                    .padding(.vertical, 6)
                }

                Section("關於 App") {
                    Button {
                        infoMessage = InfoMessage(title: "修課羅盤", message: "修課羅盤整合課表、歷史修課紀錄與學分規劃，讓你能在同一個 App 追蹤自己的修課進度。")
                    } label: {
                        settingsRow(title: "查看 App 介紹", subtitle: "了解這個 App 的主要功能與定位", symbol: "book.closed")
                    }
                }

                Section {
                    Button(role: .destructive) {
                        Task {
                            await store.signOut()
                        }
                    } label: {
                        HStack {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                            Text("登出帳號")
                        }
                    }
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(
            LinearGradient(
                colors: [Color(.systemGroupedBackground), Color.indigo.opacity(0.04)],
                startPoint: .top,
                endPoint: .bottom
            )
        )
        .toolbar(.hidden, for: .navigationBar)
        .alert(item: $infoMessage) { message in
            Alert(
                title: Text(message.title),
                message: Text(message.message),
                dismissButton: .default(Text("知道了"))
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
    }

    private func settingsRow(title: String, subtitle: String, symbol: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: symbol)
                .font(.headline)
                .foregroundStyle(.indigo)
                .frame(width: 36, height: 36)
                .background(Color.indigo.opacity(0.1), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.primary)
                Text(subtitle)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.tertiary)
        }
        .contentShape(Rectangle())
    }

    private var biometricToggleBinding: Binding<Bool> {
        Binding(
            get: {
                store.isBiometricAuthEnabled
            },
            set: { isEnabled in
                Task {
                    await store.setBiometricAuthEnabled(isEnabled)
                }
            }
        )
    }

    private var syncStatusDescription: String {
        if let lastSyncedAt = store.lastSyncedAt {
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "zh_Hant_TW")
            formatter.dateFormat = "M/d HH:mm"
            return "\(store.syncState.label)・上次同步 \(formatter.string(from: lastSyncedAt))"
        }
        return store.syncState.label
    }
}
