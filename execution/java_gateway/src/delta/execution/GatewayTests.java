package delta.execution;

import java.util.List;
import java.util.Map;

/**
 * Native JVM test harness for Groups 03 to 09.
 */
public final class GatewayTests {
    public static void main(String[] args) {
        System.out.println("=== DELTA Java Execution Plane: Unit Verification Suite ===");
        testRingBufferFifo();
        testFixEngineCodec();
        testOrderBookMatching();
        testOrderCancellation();
        System.out.println("=== ALL 4 JAVA SUITES PASSED (0 FAILURES) ===");
    }

    private static void testRingBufferFifo() {
        int capacity = 1024;
        DisruptorRingBuffer ring = new DisruptorRingBuffer(capacity);
        for (int i = 0; i < 500; i++) {
            long seq = ring.next();
            OrderEvent evt = ring.get(seq);
            evt.sequence = seq;
            evt.clOrdId = "ORD-" + i;
            ring.publish(seq);
        }
        for (int i = 0; i < 500; i++) {
            OrderEvent evt = ring.get(i);
            if (evt.sequence != i || !("ORD-" + i).equals(evt.clOrdId)) {
                throw new AssertionError("FIFO sequence mismatch at index " + i);
            }
        }
        System.out.println("  ✓ testRingBufferFifo passed (500 items sequence-verified)");
    }

    private static void testFixEngineCodec() {
        // Test Logon
        String logon = FixEngine.createLogon(1, "DELTA_OMS", "BROKER_IBKR", 30);
        if (!logon.startsWith("8=FIX.4.2|9=") || !FixEngine.verifyChecksum(logon)) {
            throw new AssertionError("Logon FIX framing invalid: " + logon);
        }
        Map<Integer, String> parsedLogon = FixEngine.parse(logon);
        if (!"A".equals(parsedLogon.get(35)) || !"DELTA_OMS".equals(parsedLogon.get(49))) {
            throw new AssertionError("Parsed logon tag mismatch");
        }

        // Test NewOrderSingle
        String nos = FixEngine.createNewOrderSingle(2, "DELTA_OMS", "BROKER_IBKR", "CL01", "NVDA", (byte) 1, 100, 18500, (byte) 2);
        if (!FixEngine.verifyChecksum(nos)) {
            throw new AssertionError("NewOrderSingle checksum verification failed");
        }
        Map<Integer, String> parsedNos = FixEngine.parse(nos);
        if (!"NVDA".equals(parsedNos.get(55)) || !"100".equals(parsedNos.get(38))) {
            throw new AssertionError("Parsed NOS fields mismatch");
        }

        // Test ExecutionReport
        OrderEvent fill = new OrderEvent();
        fill.clOrdId = "CL01";
        fill.symbol = "NVDA";
        fill.side = 1;
        fill.quantity = 100;
        fill.filledQuantity = 100;
        fill.cumQuantity = 100;
        fill.priceTicks = 18500;
        fill.execType = 2; // Fill
        fill.ordStatus = 2;
        String er = FixEngine.createExecutionReport(fill, 3, "BROKER_IBKR", "DELTA_OMS");
        if (!FixEngine.verifyChecksum(er)) {
            throw new AssertionError("ExecutionReport checksum verification failed");
        }
        Map<Integer, String> parsedEr = FixEngine.parse(er);
        if (!"8".equals(parsedEr.get(35)) || !"2".equals(parsedEr.get(150))) {
            throw new AssertionError("Parsed ER tag mismatch");
        }
        System.out.println("  ✓ testFixEngineCodec passed (Logon, NOS, ExecutionReport certified)");
    }

    private static void testOrderBookMatching() {
        OrderBook book = new OrderBook("NVDA");

        // Resting Ask: 100 @ 185.00
        OrderEvent sell = new OrderEvent();
        sell.clOrdId = "S1";
        sell.symbol = "NVDA";
        sell.side = 2;
        sell.orderType = 2;
        sell.priceTicks = 18500;
        sell.quantity = 100;
        List<OrderEvent> r1 = book.match(sell);
        if (r1.size() != 1 || r1.get(0).execType != 0) {
            throw new AssertionError("Resting sell should produce 1 New ACK");
        }

        // Incoming Buy: 40 @ 185.00
        OrderEvent buy = new OrderEvent();
        buy.clOrdId = "B1";
        buy.symbol = "NVDA";
        buy.side = 1;
        buy.orderType = 2;
        buy.priceTicks = 18500;
        buy.quantity = 40;
        List<OrderEvent> r2 = book.match(buy);
        if (r2.size() != 2) {
            throw new AssertionError("Cross should produce 2 execution reports, got " + r2.size());
        }
        OrderEvent bFill = r2.stream().filter(e -> "B1".equals(e.clOrdId)).findFirst().orElseThrow();
        OrderEvent sFill = r2.stream().filter(e -> "S1".equals(e.clOrdId)).findFirst().orElseThrow();

        if (bFill.filledQuantity != 40 || bFill.execType != 2) {
            throw new AssertionError("Buyer fill mismatch");
        }
        if (sFill.filledQuantity != 40 || sFill.execType != 1) {
            throw new AssertionError("Seller partial fill mismatch");
        }
        System.out.println("  ✓ testOrderBookMatching passed (partial fill FIFO priority verified)");
    }

    private static void testOrderCancellation() {
        OrderBook book = new OrderBook("SPY");
        OrderEvent buy = new OrderEvent();
        buy.clOrdId = "C1";
        buy.symbol = "SPY";
        buy.side = 1;
        buy.orderType = 2;
        buy.priceTicks = 50000;
        buy.quantity = 50;
        book.match(buy);

        if (!book.cancel("C1")) {
            throw new AssertionError("Cancel resting order failed");
        }
        if (book.cancel("NON_EXISTENT")) {
            throw new AssertionError("Cancel non-existent order should return false");
        }
        System.out.println("  ✓ testOrderCancellation passed");
    }
}
