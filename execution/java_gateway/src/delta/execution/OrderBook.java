package delta.execution;

import java.util.*;

/**
 * Institutional price-time FIFO Limit Order Book with integer-tick pricing.
 * Zero float conversions during hot-path execution.
 */
public final class OrderBook {
    public static final class BookOrder {
        public final String clOrdId;
        public final byte side;
        public final long priceTicks;
        public long quantity;
        public final long timestampNs;

        public BookOrder(String clOrdId, byte side, long priceTicks, long quantity, long timestampNs) {
            this.clOrdId = clOrdId;
            this.side = side;
            this.priceTicks = priceTicks;
            this.quantity = quantity;
            this.timestampNs = timestampNs;
        }
    }

    private final String symbol;
    // Bids descending
    private final TreeMap<Long, List<BookOrder>> bids = new TreeMap<>(Collections.reverseOrder());
    // Asks ascending
    private final TreeMap<Long, List<BookOrder>> asks = new TreeMap<>();
    private final Map<String, BookOrder> activeOrders = new HashMap<>();

    public OrderBook(String symbol) {
        this.symbol = symbol;
    }

    public synchronized List<OrderEvent> match(OrderEvent incoming) {
        List<OrderEvent> executionReports = new ArrayList<>();
        long remainingQty = incoming.quantity;
        byte side = incoming.side;
        long limitPrice = incoming.priceTicks;

        TreeMap<Long, List<BookOrder>> oppositeSide = (side == 1) ? asks : bids;

        Iterator<Map.Entry<Long, List<BookOrder>>> levelIterator = oppositeSide.entrySet().iterator();
        while (levelIterator.hasNext() && remainingQty > 0) {
            Map.Entry<Long, List<BookOrder>> level = levelIterator.next();
            long price = level.getKey();

            if (side == 1 && price > limitPrice && incoming.orderType == 2) break; // Buy limit breached
            if (side == 2 && price < limitPrice && incoming.orderType == 2) break; // Sell limit breached

            List<BookOrder> queue = level.getValue();
            Iterator<BookOrder> orderIterator = queue.iterator();

            while (orderIterator.hasNext() && remainingQty > 0) {
                BookOrder resting = orderIterator.next();
                long fillQty = Math.min(remainingQty, resting.quantity);

                remainingQty -= fillQty;
                resting.quantity -= fillQty;

                // Execution report for incoming order
                OrderEvent execIncoming = new OrderEvent();
                execIncoming.clOrdId = incoming.clOrdId;
                execIncoming.symbol = this.symbol;
                execIncoming.side = side;
                execIncoming.priceTicks = price;
                execIncoming.filledQuantity = fillQty;
                execIncoming.cumQuantity = incoming.quantity - remainingQty;
                execIncoming.execType = (remainingQty == 0) ? (byte) 2 : (byte) 1; // 2=Fill, 1=Partial
                execIncoming.ordStatus = execIncoming.execType;
                execIncoming.timestampNs = System.nanoTime();
                executionReports.add(execIncoming);

                // Execution report for resting order
                OrderEvent execResting = new OrderEvent();
                execResting.clOrdId = resting.clOrdId;
                execResting.symbol = this.symbol;
                execResting.side = resting.side;
                execResting.priceTicks = price;
                execResting.filledQuantity = fillQty;
                execResting.cumQuantity = fillQty;
                execResting.execType = (resting.quantity == 0) ? (byte) 2 : (byte) 1;
                execResting.ordStatus = execResting.execType;
                execResting.timestampNs = System.nanoTime();
                executionReports.add(execResting);

                if (resting.quantity == 0) {
                    orderIterator.remove();
                    activeOrders.remove(resting.clOrdId);
                }
            }

            if (queue.isEmpty()) {
                levelIterator.remove();
            }
        }

        // Place remainder in book if Limit order
        if (remainingQty > 0 && incoming.orderType == 2) {
            BookOrder bookOrder = new BookOrder(incoming.clOrdId, side, limitPrice, remainingQty, System.nanoTime());
            TreeMap<Long, List<BookOrder>> sameSide = (side == 1) ? bids : asks;
            sameSide.computeIfAbsent(limitPrice, k -> new ArrayList<>()).add(bookOrder);
            activeOrders.put(incoming.clOrdId, bookOrder);

            OrderEvent ack = new OrderEvent();
            ack.clOrdId = incoming.clOrdId;
            ack.symbol = this.symbol;
            ack.side = side;
            ack.priceTicks = limitPrice;
            ack.quantity = incoming.quantity;
            ack.filledQuantity = incoming.quantity - remainingQty;
            ack.cumQuantity = ack.filledQuantity;
            ack.execType = 0; // New
            ack.ordStatus = (ack.cumQuantity > 0) ? (byte) 1 : (byte) 0;
            ack.timestampNs = System.nanoTime();
            executionReports.add(ack);
        }

        return executionReports;
    }

    public synchronized boolean cancel(String clOrdId) {
        BookOrder order = activeOrders.remove(clOrdId);
        if (order == null) return false;
        TreeMap<Long, List<BookOrder>> map = (order.side == 1) ? bids : asks;
        List<BookOrder> queue = map.get(order.priceTicks);
        if (queue != null) {
            queue.removeIf(o -> o.clOrdId.equals(clOrdId));
            if (queue.isEmpty()) {
                map.remove(order.priceTicks);
            }
        }
        return true;
    }

    public String getSymbol() {
        return symbol;
    }

    public synchronized Long getBestBid() {
        return bids.isEmpty() ? null : bids.firstKey();
    }

    public synchronized Long getBestAsk() {
        return asks.isEmpty() ? null : asks.firstKey();
    }
}
