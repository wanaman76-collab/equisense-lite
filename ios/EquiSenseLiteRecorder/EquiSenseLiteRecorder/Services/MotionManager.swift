import Foundation
import CoreMotion

class MotionManager {
    private let manager = CMMotionManager()
    private var startEpochMs: Int64 = 0
    private var startUptime: TimeInterval = 0

    func start(onSample: @escaping (SensorSample) -> Void) {
        guard manager.isDeviceMotionAvailable else { return }
        startEpochMs = Int64(Date().timeIntervalSince1970 * 1000)
        startUptime = ProcessInfo.processInfo.systemUptime
        manager.deviceMotionUpdateInterval = 1.0 / 50.0
        manager.startDeviceMotionUpdates(to: .main) { [weak self] motion, error in
            guard let self, let motion, error == nil else { return }
            let offsetMs = Int64((motion.timestamp - self.startUptime) * 1000)
            let sample = SensorSample(
                ts_ms: self.startEpochMs + offsetMs,
                ax: motion.userAcceleration.x,
                ay: motion.userAcceleration.y,
                az: motion.userAcceleration.z,
                gx: motion.rotationRate.x,
                gy: motion.rotationRate.y,
                gz: motion.rotationRate.z
            )
            onSample(sample)
        }
    }

    func stop() {
        manager.stopDeviceMotionUpdates()
    }
}
