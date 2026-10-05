package delta.execution;

import java.util.HashMap;
import java.util.Map;

/**
 * Institutional FIX 4.2 / 4.4 Protocol Codec.
 * High-performance, streaming-safe tag=value parser and serializer.
 * Supports Logon (A), Heartbeat (0), TestRequest (1), Logout (5),
 * NewOrderSingle (D), OrderCancelRequest (F), ExecutionReport (8), OrderCancelReject (9).
 */
public final class FixEngine {
    public static final char SOH = '\u0001';

    public static Map<Integer, String> parse(String fixMessage) {
        Map<Integer, String> fields = new HashMap<>();
        int len = fixMessage.length();
        int start = 0;

        for (int i = 0; i < len; i++) {
            char c = fixMessage.charAt(i);
            if (c == SOH || c == '|') {
                String pair = fixMessage.substring(start, i);
                int eq = pair.indexOf('=');
                if (eq > 0) {
                    try {
                        int tag = Integer.parseInt(pair.substring(0, eq));
                        String val = pair.substring(eq + 1);
                        fields.put(tag, val);
                    } catch (NumberFormatException ignored) {}
                }
                start = i + 1;
            }
        }
        return fields;
    }

    public static boolean verifyChecksum(String fixMessage) {
        int idx = fixMessage.lastIndexOf("10=");
        if (idx == -1) return false;
        int end = fixMessage.indexOf('|', idx);
        if (end == -1) end = fixMessage.indexOf(SOH, idx);
        if (end == -1) end = fixMessage.length();

        String expectedStr = fixMessage.substring(idx + 3, end).trim();
        int expectedChecksum;
        try {
            expectedChecksum = Integer.parseInt(expectedStr);
        } catch (NumberFormatException e) {
            return false;
        }

        int calculated = 0;
        for (int i = 0; i < idx; i++) {
            char c = fixMessage.charAt(i);
            calculated += (c == '|' ? SOH : c);
        }
        return (calculated % 256) == expectedChecksum;
    }

    private static String formatMessage(String msgType, String senderCompId, String targetCompId, long seqNum, String bodyFields) {
        StringBuilder sb = new StringBuilder(256);
        sb.append("35=").append(msgType)
          .append("|49=").append(senderCompId)
          .append("|56=").append(targetCompId)
          .append("|34=").append(seqNum)
          .append("|52=").append(System.currentTimeMillis())
          .append("|").append(bodyFields);
        if (!bodyFields.endsWith("|")) {
            sb.append("|");
        }

        String body = sb.toString();
        String fullHeader = "8=FIX.4.2|9=" + body.length() + "|";
        
        int checkSum = 0;
        for (int i = 0; i < fullHeader.length(); i++) {
            checkSum += (fullHeader.charAt(i) == '|' ? SOH : fullHeader.charAt(i));
        }
        for (int i = 0; i < body.length(); i++) {
            checkSum += (body.charAt(i) == '|' ? SOH : body.charAt(i));
        }
        checkSum = checkSum % 256;

        return fullHeader + body + "10=" + String.format("%03d", checkSum) + "|";
    }

    public static String createLogon(long seqNum, String sender, String target, int heartbeatInterval) {
        return formatMessage("A", sender, target, seqNum, "98=0|108=" + heartbeatInterval + "|");
    }

    public static String createHeartbeat(long seqNum, String sender, String target, String testReqId) {
        String body = (testReqId != null && !testReqId.isEmpty()) ? "112=" + testReqId + "|" : "";
        return formatMessage("0", sender, target, seqNum, body);
    }

    public static String createTestRequest(long seqNum, String sender, String target, String testReqId) {
        return formatMessage("1", sender, target, seqNum, "112=" + testReqId + "|");
    }

    public static String createLogout(long seqNum, String sender, String target, String text) {
        String body = (text != null && !text.isEmpty()) ? "58=" + text + "|" : "";
        return formatMessage("5", sender, target, seqNum, body);
    }

    public static String createNewOrderSingle(long seqNum, String sender, String target, String clOrdId, String symbol, byte side, long qty, long priceTicks, byte ordType) {
        StringBuilder b = new StringBuilder();
        b.append("11=").append(clOrdId)
         .append("|55=").append(symbol)
         .append("|54=").append(side)
         .append("|38=").append(qty)
         .append("|40=").append(ordType)
         .append("|44=").append(String.format("%.2f", priceTicks / 100.0))
         .append("|60=").append(System.currentTimeMillis())
         .append("|");
        return formatMessage("D", sender, target, seqNum, b.toString());
    }

    public static String createOrderCancelRequest(long seqNum, String sender, String target, String origClOrdId, String clOrdId, String symbol, byte side) {
        String body = "41=" + origClOrdId + "|11=" + clOrdId + "|55=" + symbol + "|54=" + side + "|";
        return formatMessage("F", sender, target, seqNum, body);
    }

    public static String createExecutionReport(OrderEvent event, long seqNum, String senderCompId, String targetCompId) {
        StringBuilder sb = new StringBuilder(128);
        sb.append("11=").append(event.clOrdId)
          .append("|37=ORD-").append(event.clOrdId)
          .append("|17=EXEC-").append(System.nanoTime())
          .append("|150=").append(event.execType)
          .append("|39=").append(event.ordStatus)
          .append("|55=").append(event.symbol)
          .append("|54=").append(event.side)
          .append("|38=").append(event.quantity)
          .append("|44=").append(String.format("%.2f", event.priceTicks / 100.0))
          .append("|32=").append(event.filledQuantity)
          .append("|31=").append(String.format("%.2f", event.priceTicks / 100.0))
          .append("|14=").append(event.cumQuantity)
          .append("|6=").append(String.format("%.2f", event.priceTicks / 100.0))
          .append("|");
        return formatMessage("8", senderCompId, targetCompId, seqNum, sb.toString());
    }

    public static String createOrderCancelReject(long seqNum, String sender, String target, String clOrdId, String origClOrdId, String reason) {
        String body = "11=" + clOrdId + "|41=" + origClOrdId + "|39=8|434=1|58=" + reason + "|";
        return formatMessage("9", sender, target, seqNum, body);
    }
}
