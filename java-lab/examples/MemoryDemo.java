import java.lang.ref.Reference;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Locale;

public class MemoryDemo {
    private static final int ARRAY_COUNT = 500;
    private static final int ARRAY_BYTES = 256 * 1024;
    private static final double MIB = 1024.0 * 1024.0;

    public static void main(String[] args) {
        if (args.length != 1
                || !(args[0].equals("transient") || args[0].equals("retained"))) {
            System.err.println("Usage: MemoryDemo transient|retained");
            System.exit(1);
        }

        String mode = args[0];
        boolean keepArrays = mode.equals("retained");
        ArrayList<byte[]> retained = new ArrayList<>(ARRAY_COUNT);
        long checksum = 0;

        for (int iteration = 1; iteration <= ARRAY_COUNT; iteration++) {
            byte[] data = new byte[ARRAY_BYTES];
            Arrays.fill(data, (byte) iteration);
            checksum += checksum(data);

            if (keepArrays) {
                retained.add(data);
            }
            // Transient mode keeps no references to earlier arrays.
            if (iteration % 50 == 0) {
                printMemory(mode, iteration, retained.size());
            }
        }

        // Read every retained array again and include the result in the summary.
        long retainedChecksum = 0;
        for (byte[] data : retained) {
            retainedChecksum += checksum(data);
        }
        System.out.printf(Locale.ROOT,
                "summary mode=%s iterations=%d checksum=%d retainedChecksum=%d retainedArrays=%d%n",
                mode, ARRAY_COUNT, checksum, retainedChecksum, retained.size());
        // Keep the list and its arrays reachable through the final summary.
        Reference.reachabilityFence(retained);
    }

    private static long checksum(byte[] data) {
        long sum = 0;
        for (byte value : data) {
            sum += value & 0xff; // Interpret each byte as an unsigned value.
        }
        return sum;
    }

    private static void printMemory(String mode, int iteration, int retainedArrays) {
        Runtime runtime = Runtime.getRuntime();
        long heap = runtime.totalMemory();
        long used = heap - runtime.freeMemory();
        System.out.printf(Locale.ROOT,
                "mode=%s iterations=%d allocatedPayloadMiB=%.2f usedHeapMiB=%.2f "
                        + "heapMiB=%.2f maxHeapMiB=%.2f retainedArrays=%d%n",
                mode, iteration, iteration * (long) ARRAY_BYTES / MIB,
                used / MIB, heap / MIB, runtime.maxMemory() / MIB, retainedArrays);
    }
}
