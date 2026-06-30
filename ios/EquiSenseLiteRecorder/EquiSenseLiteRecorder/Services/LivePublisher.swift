import Foundation

/// Batches sensor samples during active recording and periodically POSTs
/// them to ``/sessions/{sessionId}/live-ingest`` for real-time broadcast
/// to WebSocket subscribers on the Mac dashboard.
///
/// Design goals:
/// - Fire-and-forget: network failures are swallowed silently so recording
///   is never interrupted.
/// - Offline-first: if the network is unavailable the batch is dropped and
///   normal local buffering continues unaffected.
/// - No duplication of persistence: live-ingest does NOT persist data;
///   the full upload via ``APIClient.uploadAll`` handles persistence.
@MainActor
class LivePublisher {
    // MARK: - Configuration

    /// How often (in seconds) buffered samples are flushed to the backend.
    static let publishInterval: TimeInterval = 0.2 // 200 ms

    /// Maximum readings sent per live-ingest request (backend limit is 100).
    static let maxBatchSize: Int = 50

    // MARK: - State

    private var timer: Timer?
    private var pending: [SensorSample] = []
    private var sessionId: Int?
    private var apiClient: APIClient?
    private let networkMonitor: NetworkMonitor

    // MARK: - Init

    init(networkMonitor: NetworkMonitor) {
        self.networkMonitor = networkMonitor
    }

    // MARK: - Public API

    /// Start live publishing for the given session.
    func start(sessionId: Int, client: APIClient) {
        self.sessionId = sessionId
        self.apiClient = client
        self.pending = []

        timer = Timer.scheduledTimer(
            withTimeInterval: Self.publishInterval,
            repeats: true
        ) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                await self.flush()
            }
        }
    }

    /// Stop live publishing and discard any pending samples.
    func stop() {
        timer?.invalidate()
        timer = nil
        pending = []
        sessionId = nil
        apiClient = nil
    }

    /// Enqueue a sample for the next publish batch.
    func enqueue(_ sample: SensorSample) {
        pending.append(sample)
    }

    // MARK: - Private

    private func flush() async {
        guard !pending.isEmpty else { return }

        guard let sid = sessionId, let client = apiClient else {
            // Recording has stopped — discard remaining buffer.
            pending = []
            return
        }

        guard networkMonitor.isOnline else {
            // Graceful degradation: keep the most recent samples so the live
            // feed recovers quickly when network returns, but cap growth to
            // avoid unbounded memory use during extended offline periods.
            if pending.count > 200 {
                pending = Array(pending.suffix(200))
            }
            return
        }

        let batch = Array(pending.prefix(Self.maxBatchSize))
        pending = Array(pending.dropFirst(batch.count))

        do {
            try await client.sendLiveBatch(sessionId: sid, samples: batch)
        } catch {
            // Silently discard: live feed failure must never interrupt recording.
        }
    }
}
