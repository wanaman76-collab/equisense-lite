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
    let is_baseline: Bool?
}

// MARK: - Ingest
struct IngestBatch: Encodable {
    let session_id: Int
    let readings: [SensorSample]
}

struct IngestResponse: Decodable {
    let stored: Int
}

// MARK: - Baseline toggle
struct BaselineToggleIn: Encodable {
    let enabled: Bool
}

struct BaselineRecomputeResponse: Decodable {
    let horse_id: Int
    let updated: [[String: Double]]
}

// MARK: - Compute (new report shape)

struct ComputeReportMetrics: Decodable {
    let cadence_spm_mean: Double?
    let cadence_spm_std: Double?
    let stride_var_median: Double?
    let stride_var_iqr: Double?
    let asymmetry_proxy_median: Double?
    let asymmetry_proxy_iqr: Double?
    let energy_mean: Double?
    let windows_with_gaps: Int
}

struct ComputeReportBaseline: Decodable {
    let cadence_spm_median: Double?
    let cadence_spm_mad: Double?
    let stride_var_median: Double?
    let stride_var_mad: Double?
    let asymmetry_proxy_median: Double?
    let asymmetry_proxy_mad: Double?
}

struct ComputeReport: Decodable {
    let overall_label: String
    let trot_confidence: String
    let explanations: [String]
    let metrics: ComputeReportMetrics
    let baseline: ComputeReportBaseline
}

struct ComputeResponse: Decodable {
    let windows: Int
    let anomalies_total: Int
    let anomalies_medium_high: Int
    let report: ComputeReport
}
