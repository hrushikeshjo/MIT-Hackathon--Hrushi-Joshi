from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from agents.orchestrator import Orchestrator
from core.local_analysis import issue_catalog
from core.web_data import collect_web_data
from main import DEMO_SITUATION, DEMO_SITUATIONS


ROOT = Path(__file__).resolve().parent
DASHBOARD = ROOT / "ui" / "dashboard.html"


class DisasterResponseHandler(BaseHTTPRequestHandler):
    server_version = "DisasterResponseMAS/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/dashboard"}:
            self._send_html(DASHBOARD.read_text(encoding="utf-8"))
            return
        if path == "/api/demo":
            self._send_json({"situation": DEMO_SITUATION.strip()})
            return
        if path == "/api/demos":
            self._send_json({"demos": DEMO_SITUATIONS})
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/analyze", "/api/issues", "/api/web-data"}:
            self.send_error(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            situation = str(payload.get("situation", "")).strip()
            if not situation:
                self._send_json({"error": "Situation report is required."}, status=400)
                return

            if path == "/api/issues":
                issues = issue_catalog(situation)
                by_category: dict[str, int] = {}
                for issue in issues:
                    category = issue.get("category", "uncategorized")
                    by_category[category] = by_category.get(category, 0) + 1
                self._send_json(
                    {
                        "issues": issues,
                        "summary": {
                            "total_active_issues": len(
                                [issue for issue in issues if issue.get("status") == "active"]
                            ),
                            "total_needs_confirmation": len(
                                [issue for issue in issues if issue.get("status") == "needs_confirmation"]
                            ),
                            "by_category": by_category,
                            "highest_priority_score": max(
                                [issue.get("priority_score", 0) for issue in issues],
                                default=0,
                            ),
                        },
                    }
                )
                return

            if path == "/api/web-data":
                self._send_json(collect_web_data(situation))
                return

            report = asyncio.run(Orchestrator().run(situation))
            self._send_json(report)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body."}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_html(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, body: dict, status: int = 200) -> None:
        encoded = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), DisasterResponseHandler)
    print(f"Disaster Response MAS dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
