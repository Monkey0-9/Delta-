package delta.execution;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;
import java.util.function.Consumer;

/**
 * Lock-free, mechanical sympathy LMAX-style ring buffer.
 * Provides microsecond inter-thread event handoffs without mutex lock contention.
 */
public final class DisruptorRingBuffer {
    private final int bufferSize;
    private final int mask;
    private final OrderEvent[] entries;

    // Cache-line padding before cursor
    protected long p1, p2, p3, p4, p5, p6, p7;
    private volatile long cursor = -1L;
    protected long p8, p9, p10, p11, p12, p13, p14;

    private static final VarHandle CURSOR;

    static {
        try {
            CURSOR = MethodHandles.lookup().findVarHandle(DisruptorRingBuffer.class, "cursor", long.class);
        } catch (ReflectiveOperationException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    public DisruptorRingBuffer(int capacity) {
        if (Integer.bitCount(capacity) != 1) {
            throw new IllegalArgumentException("Capacity must be a power of 2");
        }
        this.bufferSize = capacity;
        this.mask = capacity - 1;
        this.entries = new OrderEvent[capacity];
        for (int i = 0; i < capacity; i++) {
            this.entries[i] = new OrderEvent();
        }
    }

    public long next() {
        return (long) CURSOR.getAndAdd(this, 1L) + 1L;
    }

    public OrderEvent get(long sequence) {
        return entries[(int) (sequence & mask)];
    }

    public void publish(long sequence) {
        VarHandle.releaseFence();
    }

    public int getBufferSize() {
        return bufferSize;
    }

    public long getCursor() {
        return (long) CURSOR.getVolatile(this);
    }
}
