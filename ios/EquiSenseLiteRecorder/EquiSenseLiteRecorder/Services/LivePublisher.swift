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
    /// Configurable at build time; keep ≤ 1 s for a responsive live chart.
    static let publishInterval: TimeInterval = 0.2 // 200 ms

    /// Maximum readings sent per live-ingest request (backend limit is 100).
    /// Keeping this at 50 leaves headroom and matches ~1 s of 50 Hz data.
    static let maxBatchSize: Int = 50

    /// Maximum pending-sample buffer size while the network is unavailable.
    /// Oldest samples are discarded when this limit is reached.
    static let maxOfflineBuffer: Int = 200

    // MARK: - State

    private var timer: Timer?
    private var pending: [SensorSample] = []
    private var sessionId: Int?
    private var apiClient: APIClient?
    private let networkMonitor: NetworkMonitor

    /// Cumulative count of samples flushed successfully (debug builds only).
    private var totalFlushed: Int = 0
    /// Cumulative count of flush failures (debug builds only).
    private var totalErrors: Int = 0

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
        self.totalFlushed = 0
        self.totalErrors = 0

        #if DEBUG
        print("[LivePublisher] started session=\(sessionId) interval=\(Self.publishInterval)s maxBatch=\(Self.maxBatchSize)")
        #endif

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

        #if DEBUG
        print("[LivePublisher] stopped session=\(sessionId ?? -1) totalFlushed=\(totalFlushed) totalErrors=\(totalErrors) pendingDiscarded=\(pending.count)")
        #endif

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
            if pending.count > Self.maxOfflineBuffer {
                pending = Array(pending.suffix(Self.maxOfflineBuffer))
                #if DEBUG
                print("[LivePublisher] offline — buffer trimmed to \(Self.maxOfflineBuffer) samples")
                #endif
            }
            return
        }

        let batch = Array(pending.prefix(Self.maxBatchSize))
        pending = Array(pending.dropFirst(batch.count))

        do {
            try await client.sendLiveBatch(sessionId: sid, samples: batch)
            totalFlushed += batch.count
            #if DEBUG
            if totalFlushed % 500 == 0 {
                print("[LivePublisher] health session=\(sid) flushed=\(totalFlushed) errors=\(totalErrors) pending=\(pending.count)")
            }
            #endif
        } catch {
            totalErrors += 1
            // Silently discard: live feed failure must never interrupt recording.
            #if DEBUG
            print("[LivePublisher] flush error (ignored) session=\(sid) error=\(error.localizedDescription) totalErrors=\(totalErrors)")
            #endif
        }
    }
}
