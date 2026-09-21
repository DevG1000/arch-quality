"""server.py — arch-quality Web 操作界面的 Flask 应用与入口。

路由：
  /                         主面板页面
  /api/commands             GET   返回命令元数据
  /api/history              GET   历史/收藏组合列表
  /api/history              POST  保存当前组合
  /api/history/<id>         DELETE 删除收藏
  /api/run                  POST  启动命令（返回 run_id）
  /api/stream/<run_id>      GET   SSE 实时日志流
  /api/runs/<run_id>/cancel POST  取消运行
  /api/runs/<run_id>        GET   运行状态
  /api/preview              POST  读取报告文件（Markdown/JSON）
  /api/browse               POST  目录浏览
"""

import json
import os
import sys
import time
import webbrowser
import threading
from pathlib import Path

from flask import Flask, jsonify, request, Response, render_template, stream_with_context

from .commands_meta import COMMANDS, COMMAND_ORDER, get_command, check_mutex, build_command_string
from .runner import Runner, summary

# ---------------------------------------------------------------------------
# 历史存储
# ---------------------------------------------------------------------------

HISTORY_DIR = Path(os.environ.get("USERPROFILE") or Path.home()) / ".config" / "opencode" / "arch-reports"
HISTORY_FILE = HISTORY_DIR / "ui-history.json"


def _load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_history(items: list):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_history_id(items: list) -> int:
    return max([i.get("id", 0) for i in items], default=0) + 1


# ---------------------------------------------------------------------------
# 应用
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
runner = Runner()


@app.route("/")
def index():
    resp = render_template("index.html")
    # 禁用缓存：确保前端 CSS/JS 修改即时生效（历史收藏下拉文字等）
    resp = app.response_class(resp, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/api/commands", methods=["GET"])
def api_commands():
    return jsonify({
        "order": COMMAND_ORDER,
        "commands": COMMANDS,
    })


@app.route("/api/history", methods=["GET"])
def api_history_get():
    return jsonify(_load_history())


@app.route("/api/history", methods=["POST"])
def api_history_post():
    body = request.get_json(silent=True) or {}
    cmd_id = body.get("command")
    values = body.get("values", {})
    name = (body.get("name") or "").strip()
    if cmd_id not in COMMANDS:
        return jsonify({"error": f"未知命令: {cmd_id}"}), 400
    items = _load_history()
    hid = _next_history_id(items)
    items.append({
        "id": hid,
        "command": cmd_id,
        "label": name or f"{get_command(cmd_id)['label']} #{hid}",
        "values": values,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_history(items)
    return jsonify({"ok": True, "id": hid})


@app.route("/api/history/<int:hid>", methods=["DELETE"])
def api_history_delete(hid):
    items = [i for i in _load_history() if i.get("id") != hid]
    _save_history(items)
    return jsonify({"ok": True})


@app.route("/api/run", methods=["POST"])
def api_run():
    body = request.get_json(silent=True) or {}
    cmd_id = body.get("command")
    values = body.get("values", {})
    if cmd_id not in COMMANDS:
        return jsonify({"error": f"未知命令: {cmd_id}"}), 400

    violations = check_mutex(cmd_id, values)
    if violations:
        return jsonify({"error": f"互斥参数冲突: {violations}"}), 400

    from .commands_meta import build_argv
    cmd_list = [sys.executable, "-m", get_command(cmd_id)["module"].split(":")[0]] + build_argv(cmd_id, values)
    cwd = values.get("root") or "."
    if not os.path.isdir(cwd):
        return jsonify({"error": f"项目根目录不存在: {cwd}"}), 400

    run_id = runner.start(cmd_list, cwd=cwd)
    return jsonify({"run_id": run_id, "command": " ".join(cmd_list)})


@app.route("/api/stream/<run_id>")
def api_stream(run_id):
    state = runner.get(run_id)
    if state is None:
        return jsonify({"error": "未知运行"}), 404

    def generate():
        yield "data: {\"run_id\": %s, \"command\": %s}\n\n" % (
            json.dumps(run_id), json.dumps(state.command_string))
        for channel, text in runner.iter_lines(run_id):
            payload = json.dumps({"channel": channel, "text": text}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        yield f"data: {json.dumps({'done': True, 'summary': summary(state)}, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/runs/<run_id>", methods=["GET"])
def api_run_status(run_id):
    state = runner.get(run_id)
    if state is None:
        return jsonify({"error": "未知运行"}), 404
    return jsonify(summary(state))


@app.route("/api/runs/<run_id>/cancel", methods=["POST"])
def api_run_cancel(run_id):
    ok = runner.cancel(run_id)
    return jsonify({"ok": ok})


@app.route("/api/preview", methods=["POST"])
def api_preview():
    body = request.get_json(silent=True) or {}
    path = body.get("path", "")
    if not path or not os.path.isfile(path):
        return jsonify({"error": f"文件不存在: {path}"}), 404
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return jsonify({"error": f"读取失败: {e}"}), 500
    ext = os.path.splitext(path)[1].lower()
    return jsonify({"path": path, "ext": ext, "content": content})


@app.route("/api/browse", methods=["POST"])
def api_browse():
    body = request.get_json(silent=True) or {}
    raw = body.get("path") or "."
    if not os.path.isdir(raw):
        return jsonify({"error": f"目录不存在: {raw}"}), 400
    # 规范化为绝对路径，保证界面显示/返回的一致
    path = os.path.abspath(raw)
    entries = []
    try:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            entries.append({
                "name": name,
                "is_dir": os.path.isdir(full),
                "path": os.path.abspath(full),
            })
    except OSError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"path": path, "entries": entries})


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="arch-quality Web 操作界面")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8765, help="监听端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args(argv)

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()
    print(f"arch-quality UI: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()