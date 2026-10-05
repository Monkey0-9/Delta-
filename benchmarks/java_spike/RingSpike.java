package delta.benchmarks;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;
import java.util.Arrays;

/**
 * 200-line Mechanical Sympathy SPSC Ring Spike for Group 02.
 * Measures single-producer single-consumer lock-free handoff throughput and latency percentiles.
 */
public final class RingSpike {
    public static final class SimpleEvent {
        public long sequence;
        public long timestampNs;
        public long priceTicks;
        public long quantity;
    }

    private final int capacity;
    private final int mask;
    private final SimpleEvent[] ring;

    // Cache-line padding around head
    protected long p1, p2, p3, p4, p5, p6, p7;
    private volatile long head = 0;
    protected long p8, p9, p10, p11, p12, p13, p14;
    // Cache-line padding around tail
    private volatile long tail = 0;
    protected long p15, p16, p17, p18, p19, p20, p21;

    private static final VarHandle HEAD;
    private static final VarHandle TAIL;

    static {
        try {
            HEAD = MethodHandles.lookup().findVarHandle(RingSpike.class, "head", long.class);
            TAIL = MethodHandles.lookup().findVarHandle(RingSpike.class, "tail", long.class);
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    public RingSpike(int capacity) {
        this.capacity = capacity;
        this.mask = capacity - 1;
        this.ring = new SimpleEvent[capacity];
        for (int i = 0; i < capacity; i++) {
            this.ring[i] = new SimpleEvent();
        }
    }

    public static void main(String[] args) throws Exception {
        int N = 1_000_000;
        int capacity = 1024 * 64;
        RingSpike queue = new RingSpike(capacity);

        // Warmup runs
        runBenchmark(queue, 200_000, false);
        Thread.sleep(50);

        // 3 Certified measurement runs
        System.out.println("=== DELTA Group 02: Java SPSC Ring Baseline Benchmark (N=1,000,000) ===");
        for (int run = 1; run <= 3; run++) {
            runBenchmark(queue, N, true);
        }
    }

    private static void runBenchmark(RingSpike queue, int N, boolean report) throws Exception {
        long[] latenciesNs = new long[N];
        long[] consumerChecksum = new long[1];

        Thread consumer = new Thread(() -> {
            long currentTail = 0;
            long consumed = 0;
            while (consumed < N) {
                long currentHead = (long) HEAD.getVolatile(queue);
                while (currentTail < currentHead) {
                    SimpleEvent evt = queue.ring[(int) (currentTail & queue.mask)];
                    consumerChecksum[0] += evt.priceTicks;
                    latenciesNs[(int) consumed] = System.nanoTime() - evt.timestampNs;
                    currentTail++;
                    consumed++;
                }
                TAIL.setVolatile(queue, currentTail);
            }
        });

        consumer.start();

        long startNs = System.nanoTime();
        for (long i = 0; i < N; i++) {
            while (i - (long) TAIL.getVolatile(queue) >= queue.capacity) {
                Thread.onSpinWait();
            }
            SimpleEvent evt = queue.ring[(int) (i & queue.mask)];
            evt.sequence = i;
            evt.timestampNs = System.nanoTime();
            evt.priceTicks = 18420;
            evt.quantity = 100;
            HEAD.setVolatile(queue, i + 1);
        }

        consumer.join();
        long elapsedNs = System.nanoTime() - startNs;

        if (report) {
            Arrays.sort(latenciesNs);
            double seconds = elapsedNs / 1_000_000_000.0;
            long opsPerSec = (long) (N / seconds);
            long p50 = latenciesNs[(int) (N * 0.50)];
            long p95 = latenciesNs[(int) (N * 0.95)];
            long p99 = latenciesNs[(int) (N * 0.99)];
            long max = latenciesNs[N - 1];

            System.out.printf("Run Result: %,d ops/sec | p50: %d ns | p95: %d ns | p99: %d ns | max: %,d ns (chksum: %d)%n",
                    opsPerSec, p50, p95, p99, max, consumerChecksum[0]);
        }
    }
}
