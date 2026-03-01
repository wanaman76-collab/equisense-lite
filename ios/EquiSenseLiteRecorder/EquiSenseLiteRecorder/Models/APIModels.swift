import Foundation

// MARK: - Horses
struct HorseCreate: Encodable {
    let name: String
    let notes: String?
}

struct HorseOut: Identifiable, Decodable {
    let id: Int
    let name: String
    let notes: String?
}

// MARK: - Sessions
struct SessionCreate: Encodable {
    let horse_id: Int
    let surface: String?
    let notes: String?
}

struct SessionOut: Decodable {
    let id: Int
    let horse_id: Int
    let surface: String?
    let notes: String?
    let started_at: String
    let stopped_at: String?
    let status: String
}

// MARK: - Ingest
struct IngestBatch: Encodable {
    let session_id: Int
    let readings: [SensorSample]
}

struct IngestResponse: Decodable {
    let stored: Int
}

// MARK: - Compute
struct ComputeResponse: Decodable {
    let windows: Int
}
