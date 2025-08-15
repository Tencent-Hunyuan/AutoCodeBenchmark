#!/usr/bin/env python3
"""
JVM Pool Manager (HTTP server mode)
Manages persistent JVM processes to reduce startup time, supports global sharing of 8 JVM processes and ageLimit auto-restart.
"""

import socket
import subprocess
import random
import threading
import time
import os
from flask import Flask, request, jsonify
from log import setup_logger
from env import SANDBOX_UID, SANDBOX_GID

logger = setup_logger()

class JavaWorkerProcess:
    def __init__(self, port, proc):
        self.port = port
        self.proc = proc
        self.status = 'idle'
        self.last_used = time.time()
        self.age = 0  # reuse count
        self.restart_count = 0

class JVMPoolManager:
    def __init__(self, worker_num=8, base_port=5000, age_limit=200):
        # 确保日志目录存在并设置权限
        log_dir = "/data/logs/java_logs"
        os.makedirs(log_dir, exist_ok=True)
        try:
            os.chown(log_dir, SANDBOX_UID, SANDBOX_GID)
        except Exception as e:
            logger.warning(f"[JVMPool] Failed to chown {log_dir}: {e}")
        self.workers = []
        self.lock = threading.Lock()
        self.age_limit = age_limit
        self.worker_num = worker_num
        self.base_port = base_port
        
        for i in range(worker_num):
            port = base_port + i
            proc = subprocess.Popen(
                ["java", "-cp", ".:/opt/java_libs/junit-platform-console-standalone.jar:/opt/java_libs/json.jar", "WorkerMain", str(port)],
                user=SANDBOX_UID,
                group=SANDBOX_GID,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self.workers.append(JavaWorkerProcess(port, proc))
        logger.info(f"[JVMPool] Started {worker_num} JavaWorker processes on ports {base_port}-{base_port+worker_num-1}")
        # 启动后台线程定期检查worker健康
        self._stop_monitor = threading.Event()
        self.monitor_thread = threading.Thread(target=self._monitor_workers, daemon=True)
        self.monitor_thread.start()

    def _monitor_workers(self):
        while not self._stop_monitor.is_set():
            with self.lock:
                for worker in self.workers:
                    if worker.proc.poll() is not None:  # 进程已退出
                        try:
                            worker.proc.wait(timeout=1)  # 这里加wait，防止僵尸
                        except Exception as e:
                            logger.warning(f"[JVMPool] wait() failed: {e}")
                        logger.warning(f"[JVMPool] Worker crashed or exited unexpectedly, restarting: port={worker.port}")
                        self._restart_worker(worker)
            time.sleep(2)

    def get_available_worker(self, timeout=3):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                idle_workers = [w for w in self.workers if w.status == 'idle' and w.proc.poll() is None]
                if idle_workers:
                    worker = random.choice(idle_workers)
                    worker.status = 'busy'
                    worker.last_used = time.time()
                    logger.info(f"[JVMPool] Assign worker: port={worker.port}, current age={worker.age}")
                    return worker
            logger.info("[JVMPool] All workers are busy, waiting for an available one...")
            time.sleep(0.05)
        logger.warning("[JVMPool] Timeout while waiting for available worker, no JVM process available")
        return None

    def release_worker(self, worker):
        with self.lock:
            worker.status = 'idle'
            worker.last_used = time.time()
            worker.age += 1
            logger.info(f"[JVMPool] Release worker: port={worker.port}, new age={worker.age}")
            if worker.age >= self.age_limit:
                self._restart_worker(worker)

    def _restart_worker(self, worker):
        logger.info(f"[JVMPool] Restarting worker: port={worker.port}, age={worker.age}")
        if worker.proc.poll() is None:
            worker.proc.terminate()
            try:
                worker.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                worker.proc.kill()
                worker.proc.wait()
        else:
            try:
                worker.proc.wait(timeout=1)
            except Exception as e:
                logger.warning(f"[JVMPool] wait() failed in restart: {e}")
        proc = subprocess.Popen(
            ["java", "-cp", ".:/opt/java_libs/junit-platform-console-standalone.jar:/opt/java_libs/json.jar", "WorkerMain", str(worker.port)],
            user=SANDBOX_UID,
            group=SANDBOX_GID,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        worker.proc = proc
        worker.status = 'idle'
        worker.last_used = time.time()
        worker.age = 0
        worker.restart_count += 1
        logger.info(f"[JVMPool] Worker restarted: port={worker.port}, restart_count={worker.restart_count}")

    def send_to_worker(self, worker, java_code_path, timeout=10):
        import socket
        try:
            logger.info(f"[JVMPool] Sending task to worker: port={worker.port}, code_path={java_code_path}, timeout={timeout}")
            s = socket.create_connection(("127.0.0.1", worker.port), timeout=5)
            s.settimeout(timeout)
            s.sendall((java_code_path + "\n").encode())
            s.sendall((str(timeout) + "\n").encode())
            result = b""
            start_time = time.time()
            found_end = False
            try:
                while True:
                    try:
                        chunk = s.recv(4096)
                        if not chunk:
                            break
                        result += chunk
                        if b"__END__\n" in result:
                            found_end = True
                            break
                    except socket.timeout:
                        break
                    if time.time() - start_time > timeout:
                        break
            finally:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                s.close()
            self.release_worker(worker)
            if b"__END__\n" in result:
                result = result.split(b"__END__\n", 1)[0]
            return result.decode()
        except Exception as e:
            logger.error(f"[JVMPool] Worker task error: port={worker.port}, error={e}")
            self.release_worker(worker)
            return f"ERROR: {e}"

    def execute_test(self, java_code_path, timeout=10):
        logger.info(f"[JVMPool] Received execution request: code_path={java_code_path}, timeout={timeout}")
        worker = self.get_available_worker()
        if not worker:
            logger.error("[JVMPool] No available JVM process, request denied")
            return False, "", "No available JVM process"
        result = self.send_to_worker(worker, java_code_path, timeout=timeout)
        if result.startswith("COMPILE_ERROR"):
            logger.info(f"[JVMPool] Compilation error: code_path={java_code_path}")
            return False, "", result
        elif result == "TIMEOUT":
            logger.warning(f"[JVMPool] Execution timeout: code_path={java_code_path}")
            return False, "", "TIMEOUT"
        elif result.startswith("RUNTIME_ERROR"):
            logger.warning(f"[JVMPool] Execution runtime error: code_path={java_code_path}, result={result[:100]}")
            return False, "", result
        elif result.startswith("RUN_RESULT"):
            logger.info(f"[JVMPool] Execution success: code_path={java_code_path}")
            return True, result[len("RUN_RESULT\n"):], ""
        else:
            logger.warning(f"[JVMPool] Execution abnormal: code_path={java_code_path}, result={result[:100]}")
            return False, "", result

    def shutdown(self):
        self._stop_monitor.set()
        self.monitor_thread.join(timeout=3)
        for worker in self.workers:
            if worker.proc.poll() is None:
                worker.proc.terminate()
                try:
                    worker.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    worker.proc.kill()
                    worker.proc.wait()
        logger.info("[JVMPool] All JavaWorker processes terminated.")

    def get_health(self):
        with self.lock:
            total = len(self.workers)
            idle = sum(1 for w in self.workers if w.status == 'idle' and w.proc.poll() is None)
            busy = sum(1 for w in self.workers if w.status == 'busy' and w.proc.poll() is None)
            dead = sum(1 for w in self.workers if w.proc.poll() is not None)
            restarts = sum(w.restart_count for w in self.workers)
            return {
                "total": total,
                "idle": idle,
                "busy": busy,
                "dead": dead,
                "restarts": restarts,
                "workers": [
                    {
                        "port": w.port,
                        "status": w.status,
                        "age": w.age,
                        "restart_count": w.restart_count,
                        "alive": w.proc.poll() is None
                    } for w in self.workers
                ]
            }

# ====== HTTP Server ======
app = Flask(__name__)
jvm_pool = JVMPoolManager()

@app.route("/java_execute", methods=["POST"])
def java_execute():
    logger.info(f"[HTTP] Received /java_execute request: remote={request.remote_addr}")
    data = request.get_json()
    java_code_path = data.get("java_code_path")
    timeout = data.get("timeout", 10)  # default 10s
    if not java_code_path:
        logger.warning("[HTTP] Missing java_code_path parameter")
        return jsonify({"success": False, "output": "", "error": "Missing java_code_path"}), 400
    success, output, err = jvm_pool.execute_test(java_code_path, timeout=timeout)
    logger.info(f"[HTTP] /java_execute finished: code_path={java_code_path}, success={success}")
    return jsonify({
        "success": success,
        "output": output,
        "error": err
    })

@app.route("/health", methods=["GET"])
def health():
    status = jvm_pool.get_health()
    return jsonify({"status": "ok", "pool": status})

if __name__ == "__main__":
    logger.info("[JVMPoolServer] HTTP server started: 127.0.0.1:6000")
    app.run(host="127.0.0.1", port=6000, threaded=True)