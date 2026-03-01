import Foundation

struct SensorSample: Codable {
    let ts_ms: Int64
    let ax: Double
    let ay: Double
    let az: Double
    let gx: Double
    let gy: Double
    let gz: Double
}
