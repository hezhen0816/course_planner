import SwiftUI

struct AppShellView: View {
    @StateObject private var store = AppSessionStore()
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Group {
            if !store.isAuthenticated {
                AuthGateView()
            } else {
                authenticatedShell
            }
        }
        .environmentObject(store)
        .onChange(of: scenePhase) { _, newPhase in
            guard newPhase == .active, store.isAuthenticated else {
                return
            }

            Task {
                await store.refreshAppContent(suppressErrors: true)
            }
        }
    }

    private var authBackground: some View {
        ZStack {
            Color(.systemGroupedBackground)
            LinearGradient(
                colors: [Color.indigo.opacity(0.08), Color.blue.opacity(0.04), Color(.systemGroupedBackground)],
                startPoint: .top,
                endPoint: .bottom
            )
        }
        .ignoresSafeArea()
    }

    private var authenticatedShell: some View {
        TabView(selection: $store.selectedTab) {
            NavigationStack {
                HomeView()
            }
            .tabItem {
                Label(AppTab.home.title, systemImage: AppTab.home.systemImage)
            }
            .tag(AppTab.home)

            NavigationStack {
                ScheduleView()
            }
            .tabItem {
                Label(AppTab.schedule.title, systemImage: AppTab.schedule.systemImage)
            }
            .tag(AppTab.schedule)

            NavigationStack {
                PlannerView()
            }
            .tabItem {
                Label(AppTab.planner.title, systemImage: AppTab.planner.systemImage)
            }
            .tag(AppTab.planner)

            NavigationStack {
                SettingsView()
            }
            .tabItem {
                Label(AppTab.settings.title, systemImage: AppTab.settings.systemImage)
            }
            .tag(AppTab.settings)
        }
        .tint(.indigo)
    }
}

private struct AuthGateView: View {
    @EnvironmentObject private var store: AppSessionStore
    @State private var email = ""
    @State private var password = ""
    @State private var authMode: AuthFormMode = .login
    @FocusState private var focusedField: AuthField?

    var body: some View {
        ZStack {
            Color(.systemGroupedBackground)
            VStack(spacing: 0) {
                Spacer(minLength: 48)

                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(spacing: 12) {
                            Image(systemName: "point.topleft.down.curvedto.point.bottomright.up.fill")
                                .font(.title3.weight(.bold))
                                .foregroundStyle(.white)
                                .frame(width: 42, height: 42)
                                .background(Color.indigo, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                            Text("修課羅盤")
                                .font(.system(size: 30, weight: .bold, design: .rounded))
                        }

                        Text("登入後即可同步課表、匯入修課紀錄，並延續你的學分規劃。")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    HStack(spacing: 10) {
                        authModeChip(.login)
                        authModeChip(.signup)
                    }

                    VStack(alignment: .leading, spacing: 14) {
                        authFieldLabel("Email")
                        TextField("name@example.com", text: $email)
                            .textInputAutocapitalization(.never)
                            .textContentType(.emailAddress)
                            .keyboardType(.emailAddress)
                            .autocorrectionDisabled(true)
                            .focused($focusedField, equals: .email)
                            .submitLabel(.next)
                            .onSubmit {
                                focusedField = .password
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 14)
                            .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16, style: .continuous))

                        authFieldLabel("密碼")
                        SecureField("輸入密碼", text: $password)
                            .textContentType(.password)
                            .focused($focusedField, equals: .password)
                            .submitLabel(.go)
                            .onSubmit {
                                submitAuth()
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 14)
                            .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }

                    Button {
                        submitAuth()
                    } label: {
                        HStack(spacing: 10) {
                            Spacer()
                            if store.isAuthenticating {
                                ProgressView()
                                    .tint(.white)
                            }
                            Text(store.isAuthenticating ? "處理中..." : authMode.title)
                                .font(.headline.weight(.semibold))
                            Spacer()
                        }
                        .foregroundStyle(.white)
                        .padding(.vertical, 15)
                        .background(Color.indigo, in: Capsule())
                    }
                    .disabled(store.isAuthenticating || !store.isAuthConfigured)
                    .opacity(store.isAuthenticating || !store.isAuthConfigured ? 0.65 : 1)

                    if let authErrorMessage = store.authErrorMessage {
                        statusBanner(text: authErrorMessage, color: .red, systemImage: "exclamationmark.triangle.fill")
                    }

                    if let authNoticeMessage = store.authNoticeMessage {
                        statusBanner(text: authNoticeMessage, color: .green, systemImage: "checkmark.circle.fill")
                    }

                    if !store.isAuthConfigured {
                        statusBanner(text: "iOS 尚未完成雲端登入設定", color: .orange, systemImage: "gearshape.2.fill")
                    }

                    Text(authMode == .login ? "沒有帳號？切換到建立帳號" : "已經有帳號？切換回登入")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .padding(24)
                .background(Color(.systemBackground), in: RoundedRectangle(cornerRadius: 28, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .stroke(Color.black.opacity(0.04), lineWidth: 1)
                )
                .padding(.horizontal, 22)

                Spacer(minLength: 40)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            focusedField = nil
        }
        .ignoresSafeArea(.keyboard, edges: .bottom)
    }

    private func authModeChip(_ mode: AuthFormMode) -> some View {
        Button {
            authMode = mode
        } label: {
            Text(mode.title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(authMode == mode ? .white : .primary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background {
                    Capsule()
                        .fill(
                            authMode == mode
                            ? AnyShapeStyle(LinearGradient(colors: [Color.indigo, Color.blue], startPoint: .leading, endPoint: .trailing))
                            : AnyShapeStyle(Color(.secondarySystemBackground))
                        )
                }
        }
        .buttonStyle(.plain)
    }

    private func authFieldLabel(_ text: String) -> some View {
        Text(text)
            .font(.footnote.weight(.semibold))
            .foregroundStyle(.secondary)
    }

    private func statusBanner(text: String, color: Color, systemImage: String) -> some View {
        Label(text, systemImage: systemImage)
            .font(.footnote)
            .foregroundStyle(color)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(color.opacity(0.08), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func submitAuth() {
        focusedField = nil
        Task {
            if authMode == .login {
                await store.signIn(email: email, password: password)
            } else {
                await store.signUp(email: email, password: password)
            }
        }
    }
}

private enum AuthField: Hashable {
    case email
    case password
}
