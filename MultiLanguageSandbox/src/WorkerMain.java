import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.tools.*;
import java.lang.reflect.*;
import java.net.URL;
import java.net.URLClassLoader;
import java.time.LocalDateTime;
import org.junit.platform.launcher.*;
import org.junit.platform.launcher.core.*;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.engine.*;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import org.junit.platform.launcher.listeners.TestExecutionSummary;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.ZoneId;

public class WorkerMain {
    private static void logWithTime(PrintWriter logWriter, String msg) {
        String now = ZonedDateTime.now(ZoneId.of("Asia/Shanghai"))
            .format(DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSXXX"));
        logWriter.println("[" + now + "] " + msg);
    }

    public static void main(String[] args) throws Exception {
        int port = 5000;
        if (args.length > 0) port = Integer.parseInt(args[0]);
        final PrintWriter logWriter = new PrintWriter(new FileWriter("/data/logs/java_logs/worker_main_" + port + ".log", true), true);
        logWithTime(logWriter, "[WorkerMain] Starting on port " + port);
        ServerSocket server = new ServerSocket(port, 1, InetAddress.getByName("127.0.0.1"));
        logWithTime(logWriter, "Worker started on port " + port);

        while (true) {
            try (Socket socket = server.accept()) {
                logWithTime(logWriter, "[WorkerMain] Accepted connection from " + socket.getRemoteSocketAddress());
                BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
                BufferedWriter out = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8));

                // 1. 读取 code_path 路径
                String codePath = in.readLine();
                logWithTime(logWriter, "[WorkerMain] Received codePath: " + codePath);
                if (codePath == null || codePath.trim().isEmpty() || !(new File(codePath).exists())) {
                    logWithTime(logWriter, "[WorkerMain] codePath not exist or empty: " + codePath);
                    out.write("COMPILE_ERROR\ncodePath not exist or empty\n__END__\n");
                    out.flush();
                    continue;
                }
                // 2. 读取超时时间（秒）
                String timeoutLine = in.readLine();
                int timeout = 10; // default
                int MAX_TIMEOUT = 60;
                try {
                    timeout = Integer.parseInt(timeoutLine.trim());
                    if (timeout <= 1 || timeout > MAX_TIMEOUT) {
                        logWithTime(logWriter, "[WorkerMain] timeout out of range, use default 10s. Input: " + timeoutLine);
                        timeout = 10;
                    } else {
                        timeout = Math.max(1, Math.min(timeout - 1, MAX_TIMEOUT));
                    }
                } catch (Exception e) {
                    logWithTime(logWriter, "[WorkerMain] Invalid timeout, using default 10s. Input: " + timeoutLine);
                    timeout = 10;
                }
                logWithTime(logWriter, "[WorkerMain] Using timeout: " + timeout + "s");

                String javaFile = codePath;
                String classDir = new File(javaFile).getParent();
                String fileName = new File(javaFile).getName();
                String className = fileName.substring(0, fileName.lastIndexOf('.'));
                logWithTime(logWriter, "[WorkerMain] classDir: " + classDir);

                // 3. 编译（直接用JavaCompiler API）
                try {
                    logWithTime(logWriter, "[WorkerMain] Starting in-process compilation...");
                    JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
                    if (compiler == null) {
                        out.write("COMPILE_ERROR\nNo JavaCompiler found (are you using a JRE instead of a JDK?)\n__END__\n");
                        out.flush();
                        continue;
                    }
                    ByteArrayOutputStream compileErr = new ByteArrayOutputStream();
                    int compileResult = compiler.run(null, null, compileErr, "-d", classDir, javaFile);
                    if (compileResult != 0) {
                        out.write("COMPILE_ERROR\n");
                        out.write(compileErr.toString("UTF-8"));
                        out.write("__END__\n");
                        out.flush();
                        continue;
                    }
                    logWithTime(logWriter, "[WorkerMain] Compilation finished successfully.");
                } catch (Exception ce) {
                    logWithTime(logWriter, "[WorkerMain] Compilation EXCEPTION: " + ce.getMessage());
                    out.write("COMPILE_ERROR\nEXCEPTION: " + ce.getMessage() + "\n__END__\n");
                    out.flush();
                    continue;
                }

                // 4. 运行 JUnit 测试
                try {
                    logWithTime(logWriter, "[WorkerMain] Starting in-process JUnit execution...");
                    String junitJar = "/opt/java_libs/junit-platform-console-standalone.jar";
                    String jsonJar = "/opt/java_libs/json.jar";
                    URL[] urls = new URL[]{
                        new File(classDir).toURI().toURL(),
                        new File(junitJar).toURI().toURL(),
                        new File(jsonJar).toURI().toURL()
                    };
                    URLClassLoader classLoader = new URLClassLoader(urls, WorkerMain.class.getClassLoader());

                    // 只扫描 Test*.class 文件
                    File dir = new File(classDir);
                    File[] classFiles = dir.listFiles((d, name) -> name.endsWith(".class") && name.contains("Test"));
                    if (classFiles == null || classFiles.length == 0) {
                        out.write("RUNTIME_ERROR\nNo Test*.class files found\n__END__\n");
                        out.flush();
                        continue;
                    }

                    List<Class<?>> testClasses = new ArrayList<>();
                    for (File f : classFiles) {
                        String classFileName = f.getName();
                        String candidateClassName = classFileName.substring(0, classFileName.lastIndexOf('.'));
                        try {
                            Class<?> clazz = classLoader.loadClass(candidateClassName);
                            // 检查是否有 @Test 注解的方法
                            boolean hasTestMethod = false;
                            for (java.lang.reflect.Method m : clazz.getDeclaredMethods()) {
                                if (m.isAnnotationPresent(org.junit.jupiter.api.Test.class)) {
                                    hasTestMethod = true;
                                    break;
                                }
                            }
                            if (hasTestMethod) {
                                testClasses.add(clazz);
                                logWithTime(logWriter, "[WorkerMain] Added test class: " + candidateClassName);
                            } else {
                                logWithTime(logWriter, "[WorkerMain] Skipped non-test class: " + candidateClassName);
                            }
                        } catch (Exception ex) {
                            logWithTime(logWriter, "[WorkerMain] Failed to load class: " + candidateClassName + " : " + ex.getMessage());
                        }
                    }
                    if (testClasses.isEmpty()) {
                        out.write("RUNTIME_ERROR\nNo test classes with @Test found in Test*.class\n__END__\n");
                        out.flush();
                        continue;
                    }

                    Launcher launcher = LauncherFactory.create();
                    SummaryGeneratingListener listener = new SummaryGeneratingListener();

                    ByteArrayOutputStream baos = new ByteArrayOutputStream();
                    PrintStream ps = new PrintStream(baos, true, "UTF-8");
                    PrintStream oldOut = System.out;
                    PrintStream oldErr = System.err;
                    System.setOut(ps);
                    System.setErr(ps);

                    Thread runThread = new Thread(() -> {
                        try {
                            for (Class<?> testClass : testClasses) {
                                LauncherDiscoveryRequest request = LauncherDiscoveryRequestBuilder.request()
                                    .selectors(DiscoverySelectors.selectClass(testClass))
                                    .build();
                                launcher.registerTestExecutionListeners(listener);
                                launcher.execute(request);
                            }
                        } catch (Exception e) {
                            e.printStackTrace(ps);
                        }
                    });
                    runThread.start();
                    runThread.join(timeout * 1000L);
                    boolean finished = !runThread.isAlive();
                    if (!finished) {
                        runThread.interrupt();
                        out.write("RUN_RESULT\nTIMEOUT\n__END__\n");
                        out.flush();
                        System.setOut(oldOut);
                        System.setErr(oldErr);
                        continue;
                    }
                    System.setOut(oldOut);
                    System.setErr(oldErr);

                    String outputStr = baos.toString("UTF-8");
                    TestExecutionSummary summary = listener.getSummary();
                    outputStr += "\n======================\n";
                    outputStr += "Total tests:     " + summary.getTestsFoundCount() + "\n";
                    outputStr += "Successful:      " + summary.getTestsSucceededCount() + "\n";
                    outputStr += "Failed:          " + summary.getTestsFailedCount() + "\n";
                    outputStr += "Aborted:         " + summary.getTestsAbortedCount() + "\n";
                    outputStr += "Skipped:         " + summary.getTestsSkippedCount() + "\n";
                    outputStr += String.format("Total time:      %.3f s\n", summary.getTimeFinished() - summary.getTimeStarted() > 0 ? (summary.getTimeFinished() - summary.getTimeStarted()) / 1000.0 : 0);
                    String overallResult = summary.getTestsFailedCount() > 0 ? "FAILED" : "PASSED";
                    outputStr += "OVERALL_RESULT: " + overallResult + "\n";

                    out.write("RUN_RESULT\n");
                    out.write(outputStr);
                    out.write("__END__\n");
                    out.flush();
                    logWithTime(logWriter, "[WorkerMain] JUnit execution finished for codePath: " + codePath);
                } catch (Exception e) {
                    logWithTime(logWriter, "[WorkerMain] JUnit Execution EXCEPTION: " + e.getMessage());
                    e.printStackTrace(logWriter);
                    out.write("RUNTIME_ERROR\n" + e.getMessage() + "\n__END__\n");
                    out.flush();
                }

                logWithTime(logWriter, "[WorkerMain] Finished request for codePath: " + codePath);
                logWriter.flush();
            } catch (Exception e) {
                logWithTime(logWriter, "[WorkerMain] Outer EXCEPTION: " + e.getMessage());
                e.printStackTrace(logWriter);
                logWriter.flush();
            }
        }
    }
}

