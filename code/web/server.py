"""Local API and page server. Run with the project's Python environment."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import errno
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import sys
from typing import Any, Literal
from xml.sax.saxutils import escape
import urllib.error
import urllib.request
import webbrowser

WEB_ROOT = Path(__file__).resolve().parent
PROJECT_ID = hashlib.sha256(str(WEB_ROOT.parent.resolve()).casefold().encode("utf-8")).hexdigest()[:16]
sys.path.insert(0, str(WEB_ROOT.parent))

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict
import uvicorn

from model.service import InputError, SleepModel


@asynccontextmanager
async def lifespan(app):
    app.state.model = SleepModel()
    if getattr(app.state, "open_browser", False):
        asyncio.get_running_loop().call_later(.5, webbrowser.open, app.state.url)
    yield


app = FastAPI(title="眠序 · 睡眠体验原型", lifespan=lifespan)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: dict[str, Any]
    mode: Literal["record", "simulation"] = "record"


@app.exception_handler(InputError)
async def input_error_handler(request: Request, exc: InputError):
    return JSONResponse(status_code=422, content=dict(message=str(exc), errors=exc.errors))


@app.exception_handler(RequestValidationError)
async def schema_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=dict(message="请求格式不正确", errors={"_form": "请提交 inputs 字段对象，模式为 record 或 simulation"}))


@app.get("/api/health")
def health():
    return dict(status="ready", service="sleep_notes", project_id=PROJECT_ID,
                model="seven_input_ridge", report_engine="local_contributions")


@app.get("/api/config")
def config(request: Request):
    return request.app.state.model.config()


@app.post("/api/predict")
def predict(body: PredictionRequest, request: Request):
    return request.app.state.model.evaluate(body.inputs, body.mode)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_ROOT / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/styles.css", include_in_schema=False)
def styles():
    return FileResponse(WEB_ROOT / "styles.css", media_type="text/css", headers={"Cache-Control": "no-cache"})


@app.get("/app.js", include_in_schema=False)
def script():
    return FileResponse(WEB_ROOT / "app.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    return FileResponse(WEB_ROOT / "favicon.svg", media_type="image/svg+xml")


def public_base_url(request: Request) -> str:
    return (os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL")
            or str(request.base_url)).rstrip("/")


@app.get("/robots.txt", include_in_schema=False)
def robots(request: Request):
    return Response("User-agent: *\nAllow: /\nDisallow: /api/\n"
                    f"Sitemap: {public_base_url(request)}/sitemap.xml\n",
                    media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request):
    url = escape(public_base_url(request) + "/")
    return Response('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    f'<url><loc>{url}</loc></url></urlset>', media_type="application/xml")


def same_project_running(port: int) -> bool:
    """Only reuse a ready instance belonging to this exact project directory."""
    try:
        # Local checks must not go through a system proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            data = json.loads(response.read(8192))
        return isinstance(data, dict) and data.get("status") == "ready" and data.get("service") == "sleep_notes" and data.get("project_id") == PROJECT_ID
    except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException):
        return False


def select_listener(port: int) -> tuple[socket.socket | None, int]:
    """Reserve a socket before loading the model; don't race a second launcher."""
    for candidate in range(port, min(port + 20, 65536)):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", candidate))
        except OSError as exc:
            listener.close()
            if exc.errno not in (errno.EADDRINUSE, errno.EACCES) and getattr(exc, "winerror", None) not in (10048, 10013):
                raise
            if same_project_running(candidate):
                return None, candidate
            continue
        listener.listen(socket.SOMAXCONN)
        listener.setblocking(False)
        return listener, candidate
    raise OSError("附近 20 个端口均不可用，请使用 --port 指定其他端口")


def main() -> None:
    parser = argparse.ArgumentParser(description="启动本地睡眠交互原型")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open-browser", action="store_true", help="服务就绪后打开网页")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("端口必须为 1–65535")
    try:
        listener, port = select_listener(args.port)
    except OSError as exc:
        parser.exit(1, f"无法启动网页：{exc}\n")
    url = f"http://127.0.0.1:{port}"
    if listener is None:
        print(f"本项目网页已在运行，无需重复启动。请访问 {url}", flush=True)
        print("如需载入修改后的后端代码，请先在原服务终端按 Ctrl+C，再启动。", flush=True)
        if args.open_browser:
            webbrowser.open(url)
        return
    if port != args.port:
        print(f"端口 {args.port} 已被其他程序占用，自动改用 {port}。", flush=True)
    print(f"网页地址：{url}；保持终端运行，按 Ctrl+C 停止。", flush=True)
    app.state.open_browser = args.open_browser
    app.state.url = url
    try:
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
        uvicorn.Server(config).run(sockets=[listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
