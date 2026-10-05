package delta.execution;

import java.io.*;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;

/**
 * Institutional High-Throughput Java Execution Gateway Daemon.
 * Couples LMAX-style Disruptor ring buffers, Limit Order Book matching, and FIX formatting.
 */
public final class DeltaJavaGatewayServer {
    public static final String CONTRACT_VERSION = "1.0.0";
    private final int port;
    private final ConcurrentHashMap<String, OrderBook> books = new ConcurrentHashMap<>();
    private final DisruptorRingBuffer ringBuffer = new DisruptorRingBuffer(1024 * 16);
    private volatile boolean running = true;
    private ServerSocket serverSocket;
    private final long bootMs = System.currentTimeMillis();
    private final java.util.concurrent.atomic.AtomicLong cursor = new java.util.concurrent.atomic.AtomicLong(0);

    public DeltaJavaGatewayServer(int port) {
        this.port = port;
    }

    public void start() throws IOException {
        serverSocket = new ServerSocket(port);
        System.out.println("[DELTA-JAVA-GATEWAY] Listening on port " + port + " (Disruptor 16k slots initialized)");

        Thread.startVirtualThread(() -> {
            while (running) {
                try {
                    Socket client = serverSocket.accept();
                    Thread.startVirtualThread(() -> handleClient(client));
                } catch (IOException e) {
                    if (!running) break;
                }
            }
        });
    }

    private void handleClient(Socket socket) {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
             BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8))) {

            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;

                if (line.equals("PING")) {
                    writer.write("PONG\n");
                    writer.flush();
                    continue;
                }

                if (line.equals("VERSION")) {
                    writer.write("VERSION_OK " + CONTRACT_VERSION + "\n");
                    writer.flush();
                    continue;
                }

                if (line.equals("STATUS")) {
                    long uptime = System.currentTimeMillis() - bootMs;
                    writer.write("STATUS_OK 0 " + cursor.get()
                        + " " + uptime + " " + books.size() + "\n");
                    writer.flush();
                    continue;
                }

                if (line.startsWith("MATCH ")) {
                    // MATCH <clOrdId> <symbol> <side:BUY|SELL> <type:MKT|LMT> <priceTicks> <qty>
                    String[] parts = line.split(" ");
                    if (parts.length >= 7) {
                        String clOrdId = parts[1];
                        String symbol = parts[2].toUpperCase();
                        byte side = (byte) (parts[3].equalsIgnoreCase("BUY") ? 1 : 2);
                        byte type = (byte) (parts[4].equalsIgnoreCase("MKT") ? 1 : 2);
                        long priceTicks = Long.parseLong(parts[5]);
                        long qty = Long.parseLong(parts[6]);

                        long seq = ringBuffer.next();
                        OrderEvent event = ringBuffer.get(seq);
                        event.clear();
                        event.sequence = seq;
                        event.clOrdId = clOrdId;
                        event.symbol = symbol;
                        event.side = side;
                        event.orderType = type;
                        event.priceTicks = priceTicks;
                        event.quantity = qty;
                        event.timestampNs = System.nanoTime();
                        ringBuffer.publish(seq);
                        cursor.incrementAndGet();

                        OrderBook book = books.computeIfAbsent(symbol, OrderBook::new);
                        var reports = book.match(event);

                        StringBuilder resp = new StringBuilder("MATCH_OK " + reports.size() + "\n");
                        for (var r : reports) {
                            String fixMsg = FixEngine.createExecutionReport(r, seq, "DELTA_JAVA", "DELTA_OMS");
                            resp.append(r.clOrdId).append(",")
                                .append(r.symbol).append(",")
                                .append(r.side == 1 ? "BUY" : "SELL").append(",")
                                .append(r.filledQuantity).append(",")
                                .append(r.cumQuantity).append(",")
                                .append(r.priceTicks).append(",")
                                .append(r.execType).append(",")
                                .append(fixMsg).append("\n");
                        }
                        writer.write(resp.toString());
                        writer.flush();
                    }
                } else if (line.startsWith("CANCEL ")) {
                    String[] parts = line.split(" ");
                    if (parts.length >= 3) {
                        String symbol = parts[1].toUpperCase();
                        String clOrdId = parts[2];
                        OrderBook book = books.get(symbol);
                        boolean ok = (book != null) && book.cancel(clOrdId);
                        writer.write(ok ? "CANCEL_OK\n" : "CANCEL_REJECT\n");
                        writer.flush();
                    }
                } else {
                    writer.write("ERR ERR_UNKNOWN_COMMAND\n");
                    writer.flush();
                }
            }
        } catch (IOException ignored) {
        }
    }

    public void stop() {
        running = false;
        try {
            if (serverSocket != null) serverSocket.close();
        } catch (IOException ignored) {}
    }

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 8999;
        DeltaJavaGatewayServer server = new DeltaJavaGatewayServer(port);
        server.start();
        System.out.println("[DELTA-JAVA-GATEWAY] Running on port " + port);
        
        CountDownLatch latch = new CountDownLatch(1);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            server.stop();
            latch.countDown();
        }));
        latch.await();
    }
}
