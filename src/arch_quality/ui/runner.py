"""runner.py — 命令执行引擎。

以子进程方式调用现有 arch-quality CLI，后台线程读取 stdout/stderr，
按 UTF-8 解码缓存，供 SSE 实时推送。支持取消（terminate）。

设计要点：
- 每次运行生成 run_id，独立线程 + 队列缓冲输出行
- 注入 PYTHONIOENCODING=utf-8，解决 Windows 控制台 GBK 乱码
- 运行结束记录退出码、起止时间、输出行
"""

import os
import queue
import subprocess
import threading
import time
import uuid


class RunState:
    """单次运行的状态与输出缓冲。"""

    def __init__(self, run_id: str, cmd_list: list, cwd: str):
        self.run_id = run_id
        self.cmd_list = cmd_list
        self.cwd = cwd
        self.command_string = " ".join(cmd_list)
        self.proc = None
        self.lines = []            # [(timestamp, channel, text)]
        self.status = "pending"    # pending / running / completed / failed / cancelled
        self.exit_code = None
        self.started_at = None
        self.finished_at = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._queue = queue.Queue()

    def append(self, channel, text):
        with self._lock:
            self.lines.append((time.time(), channel, text))

    def snapshot(self):
        with self._lock:
            return list(self.lines)


class Runner:
    """并发安全的命令运行管理器。"""

    def __init__(self):
        self._runs = {}
        self._lock = threading.Lock()

    def start(self, cmd_list: list, cwd: str = None) -> str:
        run_id = uuid.uuid4().hex[:12]
        state = RunState(run_id, cmd_list, cwd or os.getcwd())
        with self._lock:
            self._runs[run_id] = state

        thread = threading.Thread(target=self._spawn, args=(state,), daemon=True)
        thread.start()
        return run_id

    def _spawn(self, state: RunState):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        state.status = "running"
        state.started_at = time.time()
        try:
            state.proc = subprocess.Popen(
                state.cmd_list,
                cwd=state.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
        except OSError as e:
            state.status = "failed"
            state.exit_code = -1
            state.finished_at = time.time()
            state.append("stderr", f"[启动失败] {e}\n")
            return

        def _pump(stream, channel):
            try:
                for line in stream:
                    state.append(channel, line)
                    state._queue.put((channel, line))
            except Exception:
                pass

        t1 = threading.Thread(target=_pump, args=(state.proc.stdout, "stdout"), daemon=True)
        t2 = threading.Thread(target=_pump, args=(state.proc.stderr, "stderr"), daemon=True)
        t1.start()
        t2.start()
        state.proc.wait()
        t1.join(timeout=1)
        t2.join(timeout=1)
        state.exit_code = state.proc.returncode
        state.status = "completed" if state.proc.returncode == 0 else "failed"
        state.finished_at = time.time()
        state._queue.put(("__done__", None))

    def cancel(self, run_id: str) -> bool:
        state = self._runs.get(run_id)
        if not state or state.proc is None or state.status not in ("running", "pending"):
            return False
        try:
            state.proc.terminate()
        except Exception:
            try:
                state.proc.kill()
            except Exception:
                pass
        state.status = "cancelled"
        return True

    def get(self, run_id: str):
        return self._runs.get(run_id)

    def iter_lines(self, run_id: str):
        """迭代运行输出行（用于 SSE 推送）。调用方读取完即消费。"""
        state = self._runs.get(run_id)
        if not state:
            return
        # 先补发历史行
        for ts, channel, text in state.snapshot():
            yield channel, text
        # 再消费队列
        while True:
            try:
                item = state._queue.get(timeout=0.5)
            except queue.Empty:
                if state.status in ("completed", "failed", "cancelled"):
                    break
                continue
            if item[0] == "__done__":
                break
            channel, text = item
            yield channel, text


def summary(state: RunState) -> dict:
    """运行摘要（供前端轮询）。"""
    return {
        "run_id": state.run_id,
        "command": state.command_string,
        "status": state.status,
        "exit_code": state.exit_code,
        "started_at": state.started_at,
        "finished_at": state.finished_at,
    }