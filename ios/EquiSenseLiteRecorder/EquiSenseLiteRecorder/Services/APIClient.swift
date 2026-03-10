import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case httpError(Int, String)
    case decodingError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid API URL."
        case .httpError(let code, let body): return "HTTP \(code): \(body)"
        case .decodingError(let e): return "Decode error: \(e.localizedDescription)"
        }
    }
}

struct HealthResponse: Decodable {
    let status: String
}

class APIClient {
    private let baseURL: String
    private let token: String
    private let session: URLSession

    init(baseURL: String, token: String) {
        self.baseURL = baseURL.hasSuffix("/") ? String(baseURL.dropLast()) : baseURL
        self.token = token
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 120
        self.session = URLSession(configuration: config)
    }

    // MARK: - Helpers

    private func request(_ path: String, method: String = "GET", body: Encodable? = nil) throws -> URLRequest {
        guard let url = URL(string: baseURL + path) else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue(token, forHTTPHeaderField: "X-API-Token")
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONEncoder().encode(body)
        }
        return req
    }

    private func perform<T: Decodable>(_ req: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidURL }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.httpError(http.statusCode, body)
        }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }

    // MARK: - Horses

    func createHorse(name: String, notes: String?) async throws -> HorseOut {
        let req = try request("/horses", method: "POST", body: HorseCreate(name: name, notes: notes))
        return try await perform(req)
    }

    func listHorses() async throws -> [HorseOut] {
        let req = try request("/horses")
        return try await perform(req)
    }

    // MARK: - Sessions

    func startSession(horseId: Int, surface: String?, notes: String?) async throws -> SessionOut {
        let body = SessionCreate(horse_id: horseId, surface: surface, notes: notes)
        let req = try request("/sessions", method: "POST", body: body)
        return try await perform(req)
    }

    func stopSession(id: Int) async throws -> SessionOut {
        let req = try request("/sessions/\(id)/stop", method: "POST")
        return try await perform(req)
    }

    // MARK: - Ingest

    func uploadBatch(sessionId: Int, samples: [SensorSample]) async throws -> IngestResponse {
        let batch = IngestBatch(session_id: sessionId, readings: samples)
        let req = try request("/ingest", method: "POST", body: batch)
        do {
            return try await perform(req)
        } catch APIError.httpError(409, _) {
            // Duplicate batch — treat as success with 0 stored
            return IngestResponse(stored: 0)
        }
    }

    /// Uploads all samples in batches with up to 3 retries per batch.
    /// - Parameters:
    ///   - onProgress: Called with (totalSentSoFar, totalSamples) after each batch.
    /// - Returns: Total number of samples stored on the server.
    func uploadAll(
        sessionId: Int,
        samples: [SensorSample],
        batchSize: Int = 200,
        onProgress: @escaping (Int, Int) -> Void
    ) async throws -> Int {
        var totalStored = 0
        let chunks = stride(from: 0, to: samples.count, by: batchSize).map {
            Array(samples[$0..<min($0 + batchSize, samples.count)])
        }
        for (index, chunk) in chunks.enumerated() {
            var lastError: Error?
            for attempt in 1...3 {
                do {
                    let resp = try await uploadBatch(sessionId: sessionId, samples: chunk)
                    totalStored += resp.stored
                    onProgress(min((index + 1) * batchSize, samples.count), samples.count)
                    lastError = nil
                    break
                } catch {
                    lastError = error
                    if attempt < 3 {
                        // Exponential backoff: 1s, 2s
                        try? await Task.sleep(nanoseconds: UInt64(attempt) * 1_000_000_000)
                    }
                }
            }
            if let err = lastError { throw err }
        }
        return totalStored
    }

    // MARK: - Compute

    func compute(sessionId: Int) async throws -> ComputeResponse {
        let req = try request("/sessions/\(sessionId)/compute", method: "POST")
        return try await perform(req)
    }

    // MARK: - Health

    func health() async throws -> Bool {
        let req = try request("/health", method: "GET")
        let resp: HealthResponse = try await perform(req)
        return resp.status.lowercased() == "ok"
    }
}
