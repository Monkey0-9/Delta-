package delta.execution;

/**
 * Cache-line aligned, zero-allocation mutable OrderEvent container for high-throughput ring buffers.
 */
public final class OrderEvent {
    public long sequence;
    public long timestampNs;
    public String clOrdId;
    public String origClOrdId;
    public String symbol;
    public byte side; // 1 = Buy, 2 = Sell
    public byte orderType; // 1 = Market, 2 = Limit
    public long priceTicks; // Price in integer cents/ticks (e.g. 18420 = $184.20)
    public long quantity;
    public long filledQuantity;
    public long cumQuantity;
    public long avgPriceTicks;
    public String venue;
    public String account;
    public byte execType; // 0 = New, 1 = Partial, 2 = Fill, 4 = Canceled, 8 = Rejected
    public byte ordStatus;
    public String rejectReason;

    public void clear() {
        this.sequence = 0;
        this.timestampNs = 0;
        this.clOrdId = null;
        this.origClOrdId = null;
        this.symbol = null;
        this.side = 0;
        this.orderType = 0;
        this.priceTicks = 0;
        this.quantity = 0;
        this.filledQuantity = 0;
        this.cumQuantity = 0;
        this.avgPriceTicks = 0;
        this.venue = null;
        this.account = null;
        this.execType = 0;
        this.ordStatus = 0;
        this.rejectReason = null;
    }
}
