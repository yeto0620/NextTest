"""Start the local NextTest web workbench and open its actual listening URL."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.request import urlopen
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "dist" / "index.html"
PORT_CHOICES = tuple(range(8501, 8511))


def open_when_ready(url: str, should_open: bool) -> None:
    health_url = f"{url}/api/health"
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    if should_open:
                        webbrowser.open(url)
                    print(f"浏览器已请求打开：{'是' if should_open else '否'}", flush=True)
                    print(f"本地地址：{url}", flush=True)
                    print("按 Ctrl+C 可停止本地服务。", flush=True)
                    return
        except OSError:
            pass
        time.sleep(0.3)
    print("服务未在 45 秒内就绪。请查看本窗口中的错误提示。", flush=True)


def _print_doctor_advice(report: dict) -> None:
    print("NextTest 环境诊断未通过，服务不会启动。", flush=True)
    for error in report.get("errors", []):
        print(f"- {error}", flush=True)
    print("修复后重试；也可运行 start_nexttest.cmd --doctor 只做诊断。", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NextTest 本地 Web 工作台启动器")
    parser.add_argument("--doctor", action="store_true", help="只运行环境诊断，不启动服务")
    parser.add_argument("--no-browser", action="store_true", help="不请求打开浏览器")
    parser.add_argument("--port", type=int, choices=PORT_CHOICES, default=None, help="8501–8510")
    args = parser.parse_args(argv)

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from nexttest.desktop_readiness import choose_port, doctor

    report = doctor()
    if args.doctor:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")), flush=True)
        return 0 if report.get("ready_to_launch") is True else 1
    if not report.get("ready_to_launch"):
        _print_doctor_advice(report)
        return 1

    try:
        port, fallback = choose_port(args.port)
    except RuntimeError as exc:
        print(str(exc), flush=True)
        return 1
    if fallback:
        print(f"指定端口不可用，已改用 {port}。", flush=True)
    url = f"http://127.0.0.1:{port}"
    should_open = not args.no_browser and os.environ.get("NEXTTEST_NO_BROWSER") != "1"
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    print(f"NextTest 正在启动：{url}", flush=True)
    print(f"端口：{port}", flush=True)
    print(f"浏览器是否请求打开：{'是' if should_open else '否'}", flush=True)
    print("保持此窗口打开；按 Ctrl+C 可停止。", flush=True)
    threading.Thread(target=open_when_ready, args=(url, should_open), daemon=True).start()
    import uvicorn

    uvicorn.run("nexttest.web.api:app", host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
