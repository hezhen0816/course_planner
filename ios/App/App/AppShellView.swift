import SwiftUI

struct AppShellView: View {
    @StateObject private var store = AppSessionStore()

    var body: some View {
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
        .environmentObject(store)
    }
}
