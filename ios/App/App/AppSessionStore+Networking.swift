import Foundation

extension AppSessionStore {
    func makeURL(path: String) throws -> URL {
        guard
            let supabaseURL,
            let url = URL(string: path, relativeTo: supabaseURL)
        else {
            throw NSError(domain: "CoursePlannerAuth", code: 4, userInfo: [
                NSLocalizedDescriptionKey: "雲端服務網址設定錯誤"
            ])
        }
        return url
    }

    func applyAPIHeaders(to request: inout URLRequest) {
        guard let supabaseAnonKey else {
            return
        }

        request.setValue(supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
    }

    func performJSONRequest<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request)
        try validateHTTPResponse(response, data: data)

        let decoder = JSONDecoder()
        return try decoder.decode(T.self, from: data)
    }

    func validateHTTPResponse(_ response: URLResponse, data: Data) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        guard (200 ..< 300).contains(httpResponse.statusCode) else {
            if
                let authError = try? JSONDecoder().decode(SupabaseAuthErrorResponse.self, from: data),
                let message = authError.errorDescription ?? authError.message
            {
                throw NSError(domain: "CoursePlannerAuth", code: httpResponse.statusCode, userInfo: [
                    NSLocalizedDescriptionKey: message
                ])
            }

            if
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                let detail = json["detail"] as? String
            {
                throw NSError(domain: "CoursePlannerAuth", code: httpResponse.statusCode, userInfo: [
                    NSLocalizedDescriptionKey: detail
                ])
            }

            throw NSError(domain: "CoursePlannerAuth", code: httpResponse.statusCode, userInfo: [
                NSLocalizedDescriptionKey: "請求失敗，HTTP \(httpResponse.statusCode)"
            ])
        }
    }

    var supabaseURL: URL? {
        guard let rawValue = Bundle.main.object(forInfoDictionaryKey: "SupabaseURL") as? String else {
            return nil
        }
        return URL(string: rawValue)
    }

    var supabaseAnonKey: String? {
        Bundle.main.object(forInfoDictionaryKey: "SupabaseAnonKey") as? String
    }

    static var backendServiceBaseURL: String {
        Bundle.main.object(forInfoDictionaryKey: "BackendServiceBaseURL") as? String
            ?? "https://course-planner-backend-production.up.railway.app"
    }

    static func backendURL(path: String) throws -> URL {
        guard
            let baseURL = URL(string: backendServiceBaseURL),
            let url = URL(string: path, relativeTo: baseURL)
        else {
            throw URLError(.badURL)
        }
        return url
    }
}
