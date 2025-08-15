import fcntl
import json
import os
import signal
import subprocess
import time
import psutil
import pwd
import grp
from typing import List
from log import setup_logger
from env import SANDBOX_UID, SANDBOX_GID, ENV

# 初始化日志
logger = setup_logger()

MAX_BYTES_PER_READ = 1024
SLEEP_BETWEEN_READS = 0.1
SC_CLK_TCK = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
CPU_COUNT = os.cpu_count() or 1  # 如果返回None，默认为1


def set_nonblocking(reader):
    fd = reader.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

def get_system_cpu():
    try:
        with open("/proc/stat") as proc_stat:
            cpu_total = proc_stat.readline().strip().split()[1:]
            cpu_total = [int(i) for i in cpu_total]
            system_cpu = sum(cpu_total)
    except Exception as _:
        system_cpu = 0
    return system_cpu

def get_process_cpu_mem(pid):
    parent = psutil.Process(pid)
    descendants = parent.children(recursive=True)
    all_processes = [parent] + descendants
    process_cpu = 0
    process_peak_memory = 0
    for process in all_processes:
        with open(f"/proc/{process.pid}/stat") as pid_stat:
            vals = pid_stat.read().split()
            process_cpu += sum(map(float, vals[13:17]))
        with open(f"/proc/{process.pid}/status") as pid_status:
            vm_peak_line = [l for l in pid_status if l.startswith("VmPeak:")]
            if len(vm_peak_line) != 0:
                vm_peak_line = vm_peak_line[0]
                vm_peak_line = vm_peak_line.split(":")[-1].strip()
                # 一般都是kB
                if vm_peak_line.endswith("kB"):
                    process_peak_memory += int(vm_peak_line.split()[0])
                elif vm_peak_line.endswith("mB"):
                    process_peak_memory += int(vm_peak_line.split()[0]) * 1024
                elif vm_peak_line.endswith("gB"):
                    process_peak_memory += int(vm_peak_line.split()[0]) * 1024 * 1024
                # 应该命中不到
                else:
                    process_peak_memory += int(vm_peak_line.split()[0])

    return process_cpu, process_peak_memory

def run(
    args: List[str],
    timeout_seconds: int = 15,
    max_output_size: int = 2048,
    env=None,
    shell=False,
    cwd=None
) -> dict:
    start_time = time.time()
    logger.info(f"执行命令: {args}, 工作目录: {cwd}")
    if env is None:
        env = ENV.copy()
    p = subprocess.Popen(
        args,
        user=SANDBOX_UID,
        group=SANDBOX_GID,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        bufsize=MAX_BYTES_PER_READ,
        shell=False,
        cwd=cwd
    )

    system_cpu_start = get_system_cpu()
    process_cpu = 0
    process_peak_memory = 0

    set_nonblocking(p.stdout)
    set_nonblocking(p.stderr)

    process_group_id = os.getpgid(p.pid)

    # We sleep for 0.1 seconds in each iteration.
    max_iterations = timeout_seconds * 10
    stdout_saved_bytes = []
    stderr_saved_bytes = []
    stdout_bytes_read = 0
    stderr_bytes_read = 0

    for _ in range(max_iterations):
        # 统计性能消耗
        try:
            process_cpu, process_peak_memory = get_process_cpu_mem(p.pid)
        except Exception as e:
            # print("获取进程cpu和mem信息发生异常", e)
            pass
        this_stdout_read = p.stdout.read(MAX_BYTES_PER_READ)
        this_stderr_read = p.stderr.read(MAX_BYTES_PER_READ)
        # this_stdout_read and this_stderr_read may be None if stdout or stderr
        # are closed. Without these checks, test_close_output fails.
        if this_stdout_read is not None and stdout_bytes_read < max_output_size:
            stdout_saved_bytes.append(this_stdout_read)
            stdout_bytes_read += len(this_stdout_read)
        if this_stderr_read is not None and stderr_bytes_read < max_output_size:
            stderr_saved_bytes.append(this_stderr_read)
            stderr_bytes_read += len(this_stderr_read)
        exit_code = p.poll()
        if exit_code is not None:
            break
        time.sleep(SLEEP_BETWEEN_READS)

    try:
        # Kills the process group. Without this line, test_fork_once fails.
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass

    timeout = exit_code is None
    exit_code = exit_code if exit_code is not None else -1
    stdout = b"".join(stdout_saved_bytes).decode("utf-8", errors="ignore")
    stderr = b"".join(stderr_saved_bytes).decode("utf-8", errors="ignore")
    system_cpu_end = get_system_cpu()
    if system_cpu_start != system_cpu_end:
        process_cpu_util = (
            process_cpu / (system_cpu_end - system_cpu_start) * 100 * CPU_COUNT
        )
    else:
        process_cpu_util = 0
    end_time = time.time()
    process_exec_time = end_time - start_time
    result = {
        "cmd": args, # 最终执行的命令
        "timeout": timeout,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "process_cpu_util": round(process_cpu_util, 2), # 进程占用的平均cpu利用率, 单位: %
        "process_cpu_time": round(process_cpu / SC_CLK_TCK, 2), # 进程占用的总cpu时间, 单位: s
        "process_exec_time": round(process_exec_time, 2), # 进程执行时间, 单位: s
        "process_peak_memory": process_peak_memory, # 进程执行过程中占用的最大内存, 单位: kB
    }
    return result