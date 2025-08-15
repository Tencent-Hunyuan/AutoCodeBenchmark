# Multi-Language Code Sandbox Service

A secure, high-performance multi-language code execution sandbox service that supports compilation and execution of 30+ programming languages.

## 🚀 Features

- **Multi-language Support**: Supports 30+ programming languages including Python, JavaScript, Go, Java, C++, Rust, etc.
- **Security Isolation**: Based on Docker containers and iptables firewall rules to ensure secure code execution
- **Intelligent Code Splicing**: Automatically handles splicing of function code and test code, supporting various language-specific syntax
- **High Performance**: Based on Gunicorn multi-process architecture, supports concurrent execution
- **RESTful API**: Provides clean HTTP API interface

## 📋 Supported Programming Languages

- **C** - Compiled with gcc
- **C#** - Uses .NET Core runtime
- **C++** - Compiled with g++
- **CoffeeScript** - Compiles to JavaScript
- **Common Lisp** - Uses SBCL interpreter
- **Dart** - Supports assertion checking
- **Elixir** - Based on Erlang VM
- **Emacs Lisp** - Uses Emacs batch mode
- **Erlang** - Uses erlc compiler
- **F#** - Based on .NET platform
- **Fortran** - Uses gfortran compiler
- **Go** - Uses go compiler
- **Groovy** - Uses groovy interpreter
- **Haskell** - Uses GHC compiler
- **Java** - Integrated with JUnit test framework
- **JavaScript** - Uses Node.js runtime
- **Julia** - Uses julia interpreter
- **Kotlin** - Uses kotlinc script mode
- **Lua** - Uses lua interpreter
- **Pascal** - Uses Free Pascal compiler
- **Perl** - Uses perl interpreter
- **PHP** - Uses php interpreter
- **PowerShell** - Uses pwsh execution
- **Python** - Uses python3 interpreter
- **R** - Uses Rscript execution
- **Racket** - Uses racket interpreter
- **Ruby** - Uses ruby interpreter
- **Rust** - Uses Cargo build system
- **Scala** - Uses Ammonite REPL
- **Scheme** - Uses Racket execution
- **Shell** - Uses bash execution
- **Swift** - Uses swift interpreter
- **Tcl** - Uses tclsh execution
- **TypeScript** - Uses tsx execution
- **Vimscript** - Uses vim execution
- **Visual Basic** - Based on .NET platform

## 🏗️ Architecture Design

### Overall Architecture

```
┌──────────────┐    ┌──────────────┐    ┌────────────────┐
│ HTTP Client  │───▶│  Flask Web   │───▶│    Executor    │
└──────────────┘    └──────────────┘    └────────────────┘
                           │                    │
                           │                    │
                           ▼                    ▼ 
                    ┌──────────────┐    ┌────────────────┐
                    │ Code Splicer │    │ Safe Subprocess│
                    └──────────────┘    └────────────────┘
                           │                     
                           ▼                     
                    ┌──────────────┐    
                    │  Code Store  │     
                    └──────────────┘    
                           │
                           ▼
                    ┌──────────────┐
                    │ Config File  │
                    └──────────────┘
```

### Core Components

#### 1. Web Service Layer
- **Flask Application**: Provides HTTP interface, handles code execution and splicing requests
- **Main Endpoints**:
  - `/submit` - Code execution service
- **Functions**: Request validation, exception handling, response formatting

#### 2. Code Processing Layer
- **Code Splicer**: Intelligently merges function code and test code
  - Multi-language syntax adaptation (Go import merging, JS function detection, etc.)
  - Code structure analysis and optimization
- **Code Store**: Manages temporary execution environment
  - File creation and cleanup
  - Syntax pre-checking
  - Permission control

#### 3. Execution Control Layer
- **Code Executor**: Unified multi-language execution management
  - Compiler/interpreter scheduling
  - Execution flow control
  - Error information collection
- **Safe Subprocess**: Low-level secure execution guarantee
  - Permission isolation
  - Resource limitations
  - Timeout control

### Security Mechanisms

#### 1. Container Isolation
- Runs based on Docker containers, completely isolated from host machine
- Uses non-privileged users to execute code
- Restricts file system access permissions

#### 2. Network Security
- iptables firewall rules strictly control network access
- Only allows necessary outbound connections (DNS, image sources, logging services)
- Denies all other network traffic by default

#### 3. Resource Limitations
- CPU and memory usage restrictions
- Execution timeout control
- File system write limitations

## 🚀 Quick Start

### 1. Pull Image

```bash
docker pull hunyuansandbox/multi-language-sandbox:latest
```

### 2. Start Service
```bash
docker run -d \
  --name sandbox-service \
  -p 8080:8080 \
  --cap-add=NET_ADMIN \
  hunyuansandbox/multi-language-sandbox:latest
```

### 3. Verify Service

After the service starts, you can verify if it's running normally:

```bash
# Check container status
docker ps | grep sandbox

# Test service health
curl -X POST http://localhost:8080/submit \
  -H "Content-Type: application/json" \
  -d '{"src_uid": "test-001", "lang": "python", "source_code": "print(\"Hello World\")"}'
```

If it returns a JSON response containing `"exec_outcome": "PASSED"`, the service is running normally.

## 📡 API Interface

### 1. Code Execution Interface

**Endpoint**: `POST /submit` (using source_code)

**Request Parameters**:
```json
{
  "src_uid": "unique-request-id",
  "lang": "python",
  "source_code": "def hello():\n    print('Hello World')\nhello()",
  "request_extensions": {
    "timeout": 10,
    "debug": false
  },
  "show_log": true
}
```

**Response Example**:
```json
{
  "src_uid": "unique-request-id",
  "all_code": "",
  "exec_cout": "Hello World\n",
  "exec_outcome": "PASSED",
  "exec_compile_message": "",
  "exec_runtime_message": "",
  "response_extensions": {
    "server_ip": "172.17.0.2",
    "exec_runtime": 0.123,
    "outcome": "PASSED",
    "stdout": "Hello World\n",
    "stderr": ""
  }
}
```

### 2. Code Spliced Execution Interface

**Endpoint**: `POST /submit` (using func_code and main_code)

**Request Parameters**:
```json
{
  "src_uid": "unique-request-id",
  "lang": "go",
  "func_code": "package main\n\nfunc add(a, b int) int {\n    return a + b\n}",
  "main_code": "package main\nimport \"fmt\"\n\nfunc main() {\n    fmt.Println(add(1, 2))\n}",
  "request_extensions": {
    "timeout": 5
  }
}
```

## 🔧 Usage Examples

### Python Code Execution
```bash
curl -X POST http://localhost:8080/submit \
  -H "Content-Type: application/json" \
  -d '{
    "src_uid": "python-test-001",
    "lang": "python",
    "source_code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n\nprint(fibonacci(10))"
  }'
```

### JavaScript Code Spliced Execution
```bash
curl -X POST http://localhost:8080/submit \
  -H "Content-Type: application/json" \
  -d '{
    "src_uid": "js-test-001",
    "lang": "javascript",
    "func_code": "\n// Function to calculate the number of structurally unique BSTs for a given n\nconst countUniqueBSTs = (n) => {\n    // Handle edge cases\n    if (n <= 0) return 0;\n    if (n === 1) return 1;\n    \n    // Create a DP array to store results of subproblems\n    const dp = new Array(n + 1).fill(0);\n    dp[0] = 1; // Base case: empty tree\n    dp[1] = 1; // Base case: single node\n    \n    // Fill the DP array in bottom-up manner\n    for (let i = 2; i <= n; i++) {\n        for (let j = 0; j < i; j++) {\n            // The number of trees when j is the root\n            dp[i] += dp[j] * dp[i - j - 1];\n        }\n    }\n    \n    return dp[n];\n};\n",
    "main_code": "\nconst assert = require(\"assert\");\n\nconst demoTesting = () => {\n    assert.strictEqual(countUniqueBSTs(2), 2);\n    assert.strictEqual(countUniqueBSTs(3), 5);\n};\n"
  }'
```

### Go Code Spliced Execution
```bash
curl -X POST http://localhost:8080/submit \
  -H "Content-Type: application/json" \
  -d '{
    "src_uid": "go-test-001",
    "lang": "go",
    "func_code": "package main\n\nfunc isPrime(n int) bool {\n    if n < 2 { return false }\n    for i := 2; i*i <= n; i++ {\n        if n%i == 0 { return false }\n    }\n    return true\n}",
    "main_code": "package main\nimport \"fmt\"\n\nfunc main() {\n    for i := 2; i <= 20; i++ {\n        if isPrime(i) {\n            fmt.Printf(\"%d \", i)\n        }\n    }\n    fmt.Println()\n}"
  }'
```

### Java Code Spliced Execution
```bash
curl -X POST http://localhost:8080/submit \
  -H "Content-Type: application/json" \
  -d '{
    "src_uid": "java-test-001",
    "lang": "java",
    "func_code": "import java.util.List;\n\nclass WineGlassMaximizer {\n    /**\n     * Calculates the maximum amount of wine that can be consumed without drinking\n     * three glasses in a row, using dynamic programming.\n     * \n     * @param glasses List of wine glass amounts\n     * @return Maximum amount that can be consumed following the rules\n     */\n    public int maxWineConsumption(List<Integer> glasses) {\n        if (glasses.isEmpty()) return 0;\n        if (glasses.size() == 1) return glasses.get(0);\n        if (glasses.size() == 2) return glasses.get(0) + glasses.get(1);\n        \n        int n = glasses.size();\n        int[] dp = new int[n];\n        \n        dp[0] = glasses.get(0);\n        dp[1] = glasses.get(0) + glasses.get(1);\n        dp[2] = Math.max(Math.max(glasses.get(0) + glasses.get(2), glasses.get(1) + glasses.get(2)), dp[1]);\n        \n        for (int i = 3; i < n; i++) {\n            dp[i] = Math.max(\n                Math.max(\n                    dp[i-3] + glasses.get(i-1) + glasses.get(i), // skip two, then take two\n                    dp[i-2] + glasses.get(i)                     // skip one, then take one\n                ),\n                dp[i-1]                                         // skip current glass\n            );\n        }\n        \n        return dp[n-1];\n    }\n}",
    "main_code": "import static org.junit.jupiter.api.Assertions.assertEquals;\nimport org.junit.jupiter.api.Test;\nimport java.util.Arrays;\nimport java.util.List;\n\nclass TestWineGlassMaximizer {\n    @Test\n    public void test() {\n        WineGlassMaximizer maximizer = new WineGlassMaximizer();\n        \n        List<Integer> input1 = Arrays.asList(1, 2, 3, 4, 5);\n        assertEquals(12, maximizer.maxWineConsumption(input1));\n        \n        List<Integer> input2 = Arrays.asList(5, 5, 5, 5);\n        assertEquals(15, maximizer.maxWineConsumption(input2));\n    }\n}"
  }'
```

## 📊 Execution Result Status

| Status | Description |
|--------|-------------|
| `PASSED` | Code executed successfully |
| `COMPILATION_ERROR` | Compilation error |
| `RUNTIME_ERROR` | Runtime error |
| `TIMEOUT` | Execution timeout |
| `SYNTAX_ERROR` | Syntax error |
| `ARGUMENT_ERROR` | Parameter error |
| `INTERNAL_ERROR` | Server internal error |

## 🔍 Monitoring and Logging

### Log Files
- **Location**: `/data/logs/`
- **Format**: JSON format, including request ID, execution time, result status, etc.
- **Rotation**: Automatically rotates by date

### Performance Monitoring
- **Request Tracking**: Each request has a unique src_uid for tracking
- **Resource Usage**: CPU, memory, execution time statistics

## 🛡️ Security Considerations

1. **Network Isolation**: Ensure container network configuration is correct, avoid accessing internal network resources
2. **Resource Limitations**: Adjust CPU and memory limits according to actual needs
3. **Permission Control**: Do not run containers as root user
4. **Regular Updates**: Update base images and dependency packages in time
5. **Monitoring Alerts**: Recommend configuring monitoring alerts for abnormal executions

## 💬 Feedback and Support

If you encounter problems or have suggestions for improvement during use, please:

- Submit Issues to report problems
- Share usage experience and best practices
- Suggest new language support requirements

## 🆘 Troubleshooting

### Common Issues

**Q: Container startup failure with permission error**
A: Ensure Docker has sufficient permissions and add the `--cap-add=NET_ADMIN` parameter

**Q: Code execution timeout**
A: Check timeout parameter settings, complex algorithms may need more time

**Q: Some language compilation failures**
A: Check if the language environment is installed correctly, review compilation error messages

**Q: Network connection issues**
A: Check iptables rules, ensure necessary network access is allowed

### Debug Mode

Enable debug mode to retain temporary files:
```json
{
  "request_extensions": {
    "debug": true
  }
}
```

### Log Viewing

```bash
# View container logs
docker logs sandbox-service

# View application logs
docker exec sandbox-service tail -f /data/logs/sandbox.log
```

