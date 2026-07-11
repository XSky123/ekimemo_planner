from __future__ import annotations

import argparse
import html
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.solver.solve_team import read_jsonl, solve  # noqa: E402


UI_PATH = ROOT / "pipeline" / "ui" / "solver_ui.html"
PROFILES = ROOT / "data" / "role_profiles" / "role_profiles.jsonl"


def denko_options() -> str:
    denko: dict[str, dict[str, Any]] = {}
    for profile in read_jsonl(PROFILES):
        item = profile["denko"]
        denko.setdefault(item["denko_id"], item)
    return "\n".join(
        f'<option value="{html.escape(item["denko_id"], quote=True)}" label="{html.escape(str(item.get("name") or ""), quote=True)}"></option>'
        for _, item in sorted(denko.items())
    )


def ui_document() -> bytes:
    document = UI_PATH.read_text(encoding="utf-8").replace("__DENKO_OPTIONS__", denko_options())
    return document.encode("utf-8")


class SolverHandler(BaseHTTPRequestHandler):
    server_version = "EkimemoSolver/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Keep local use quiet; schema and solver errors are returned to the UI.
        return

    def respond_json(self, status: int, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            payload = ui_document()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/api/health":
            self.respond_json(HTTPStatus.OK, {"status": "ok"})
            return
        self.respond_json(HTTPStatus.NOT_FOUND, {"error_zh": "路径不存在"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/solve":
            self.respond_json(HTTPStatus.NOT_FOUND, {"error_zh": "路径不存在"})
            return
        try:
            size = int(self.headers.get("Content-Length") or "0")
            if size <= 0 or size > 128_000:
                raise ValueError("请求大小无效")
            request = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("请求必须是对象")
            self.respond_json(HTTPStatus.OK, solve(request))
        except (ValueError, json.JSONDecodeError) as exc:
            self.respond_json(HTTPStatus.BAD_REQUEST, {"error_zh": f"请求无效：{exc}"})
        except Exception as exc:  # keep the local interface actionable without exposing a traceback
            self.respond_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error_zh": f"求解失败：{exc}"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the local Step5 Ekimemo solver UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SolverHandler)
    print(f"http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
