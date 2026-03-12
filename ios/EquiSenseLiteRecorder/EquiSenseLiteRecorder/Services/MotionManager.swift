import Foundation
import CoreMotion

/// Captures CoreMotion deviceMotion at 50 Hz and emits SensorSample (epoch-ms timestamped).
/// Adds a simple auto-calibration step on every start:
/// - For the first N seconds we estimate bias (mean) of userAcceleration + rotationRate
/// - After that, we subtract the bias from subsequent samples
class MotionManager {
    private let manager = CMMotionManager()

    private var startEpochMs: Int64 = 0
    private var startUptime: TimeInterval = 0

    // MARK: - Auto calibration

    /// Seconds of data used to estimate bias at start of recording.
    private let calibrationSeconds: TimeInterval = 3.0

    private var calibrationEndUptime: TimeInterval = 0
    private var isCalibrated: Bool = false

    private var calCount: Int = 0
    private var calSumAx: Double = 0
    private var calSumAy: Double = 0
    private var calSumAz: Double = 0
    private var calSumGx: Double = 0
    private var calSumGy: Double = 0
    private var calSumGz: Double = 0

    private var biasAx: Double = 0
    private var biasAy: Double = 0
    private var biasAz: Double = 0
    private var biasGx: Double = 0
    private var biasGy: Double = 0
    private var biasGz: Double = 0

    private func resetCalibration() {
        isCalibrated = false
        calCount = 0
        calSumAx = 0
        calSumAy = 0
        calSumAz = 0
        calSumGx = 0
        calSumGy = 0
        calSumGz = 0

        biasAx = 0
        biasAy = 0
        biasAz = 0
        biasGx = 0
        biasGy = 0
        biasGz = 0
    }

    private func finalizeCalibrationIfNeeded(currentUptime: TimeInterval) {
        guard !isCalibrated else { return }
        guard currentUptime >= calibrationEndUptime else { return }

        // Compute mean bias if we got any samples
        if calCount > 0 {
            let n = Double(calCount)
            biasAx = calSumAx / n
            biasAy = calSumAy / n
            biasAz = calSumAz / n
            biasGx = calSumGx / n
            biasGy = calSumGy / n
            biasGz = calSumGz / n
        }

        isCalibrated = true
    }

    // MARK: - Public API

    func start(onSample: @escaping (SensorSample) -> Void) {
        guard manager.isDeviceMotionAvailable else { return }

        // Reset epoch anchoring
        startEpochMs = Int64(Date().timeIntervalSince1970 * 1000)
        startUptime = ProcessInfo.processInfo.systemUptime

        // Reset calibration state
        resetCalibration()
        calibrationEndUptime = startUptime + calibrationSeconds

        manager.deviceMotionUpdateInterval = 1.0 / 50.0

        manager.startDeviceMotionUpdates(to: .main) { [weak self] motion, error in
            guard let self, let motion, error == nil else { return }

            // timestamp
            let offsetMs = Int64((motion.timestamp - self.startUptime) * 1000)
            let tsMs = self.startEpochMs + offsetMs

            // raw readings
            let rawAx = motion.userAcceleration.x
            let rawAy = motion.userAcceleration.y
            let rawAz = motion.userAcceleration.z
            let rawGx = motion.rotationRate.x
            let rawGy = motion.rotationRate.y
            let rawGz = motion.rotationRate.z

            // accumulate calibration until window ends
            if !self.isCalibrated {
                if motion.timestamp < self.calibrationEndUptime {
                    self.calCount += 1
                    self.calSumAx += rawAx
                    self.calSumAy += rawAy
                    self.calSumAz += rawAz
                    self.calSumGx += rawGx
                    self.calSumGy += rawGy
                    self.calSumGz += rawGz
                } else {
                    self.finalizeCalibrationIfNeeded(currentUptime: motion.timestamp)
                }
            }

            // apply bias after calibrated
            let ax = rawAx - (self.isCalibrated ? self.biasAx : 0)
            let ay = rawAy - (self.isCalibrated ? self.biasAy : 0)
            let az = rawAz - (self.isCalibrated ? self.biasAz : 0)
            let gx = rawGx - (self.isCalibrated ? self.biasGx : 0)
            let gy = rawGy - (self.isCalibrated ? self.biasGy : 0)
            let gz = rawGz - (self.isCalibrated ? self.biasGz : 0)

            let sample = SensorSample(
                ts_ms: tsMs,
                ax: ax,
                ay: ay,
                az: az,
                gx: gx,
                gy: gy,
                gz: gz
            )
            onSample(sample)
        }
    }

    func stop() {
        manager.stopDeviceMotionUpdates()
    }
}
