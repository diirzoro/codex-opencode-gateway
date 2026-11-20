import java.net.HttpURLConnection;
import java.net.URI;
import java.io.InputStream;
import java.util.Base64;

/** Fixed loopback GET relay compiled into the trusted Java runtime image. */
public final class PreviewFetch {
    private static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (char ch : value.toCharArray()) {
            if (ch == '\\' || ch == '"') out.append('\\').append(ch);
            else if (ch < 32 || ch > 126) out.append(String.format("\\u%04x", (int)ch));
            else out.append(ch);
        }
        return out.append('"').toString();
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || !args[0].startsWith("/") || args[0].startsWith("//")
                || args[0].length() > 2048 || args[0].chars().anyMatch(c -> c < 32 || c == 127))
            throw new IllegalArgumentException("Invalid path");
        HttpURLConnection connection = (HttpURLConnection)URI.create("http://127.0.0.1:8080" + args[0]).toURL().openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(5000);
        try {
            int status = connection.getResponseCode();
            InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            byte[] body = new byte[0];
            if (stream != null) {
                try (stream) { body = stream.readNBytes(262145); }
            }
            if (body.length > 262144) throw new IllegalArgumentException("Response too large");
            String type = connection.getContentType();
            if (type == null) type = "application/octet-stream";
            if (type.length() > 256) throw new IllegalArgumentException("Invalid media type");
            System.out.print("{\"status\":" + status + ",\"type\":" + quote(type)
                + ",\"body\":\"" + Base64.getEncoder().encodeToString(body) + "\"}");
        } finally { connection.disconnect(); }
    }
}
