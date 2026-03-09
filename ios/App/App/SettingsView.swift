import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppSessionStore
    @State private var infoMessage: InfoMessage?
    @State private var isTargetSheetPresented = false

    var body: some View {
        Form {
            Section("學校帳密設定") {
                TextField("學號 / 校務帳號", text: $store.schoolAccount)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
                SecureField("密碼", text: $store.schoolPassword)
                Text("僅展示原生表單外觀，這次不會傳送或驗證任何帳號資訊。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Section("同步") {
                Button {
                    infoMessage = InfoMessage(title: "同步課表", message: "這個版本只保留原生 UI 入口，尚未串接校務或第三方課表來源。")
                } label: {
                    settingsRow(title: "同步課表", subtitle: "保留功能入口", symbol: "arrow.triangle.2.circlepath")
                }

                Button {
                    infoMessage = InfoMessage(title: "同步學分資訊", message: "學分與成績同步尚未實作，目前頁面資料皆為本地展示內容。")
                } label: {
                    settingsRow(title: "同步學分資訊", subtitle: "僅介面展示", symbol: "tray.and.arrow.down")
                }
                .buttonStyle(.plain)
            }

            Section("提醒") {
                Picker("課前提醒", selection: $store.reminderMinutes) {
                    ForEach([5, 10, 15, 30, 60], id: \.self) { minutes in
                        Text("\(minutes) 分鐘前").tag(minutes)
                    }
                }

                Text("提醒設定只保存於本次 App 執行期間，不建立本地通知。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Section("學分規劃") {
                Button {
                    isTargetSheetPresented = true
                } label: {
                    settingsRow(title: "設定畢業門檻", subtitle: "可編輯本地 session 狀態", symbol: "slider.horizontal.3")
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

            Section("功能導覽") {
                Button {
                    infoMessage = InfoMessage(title: "功能導覽", message: "目前已提供首頁、課表、學分規劃與設定四個原生 tab，後續才會接入真實資料與同步流程。")
                } label: {
                    settingsRow(title: "查看功能導覽", subtitle: "說明目前為 UI-only 版本", symbol: "book.closed")
                }
            }

            Section {
                Button(role: .destructive) {
                    infoMessage = InfoMessage(title: "登出", message: "此版本沒有登入流程，因此登出按鈕只保留視覺入口。")
                } label: {
                    HStack {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                        Text("登出")
                    }
                }
            }
        }
        .navigationTitle("設定")
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
                .frame(width: 28)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
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
}
