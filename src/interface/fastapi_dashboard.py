"""fastapi_dashboard.py — REST API и веб-панель Аргоса"""
from __future__ import annotations
import os
from src.argos_logger import get_logger
log = get_logger("argos.dashboard")

def create_app(core=None):
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse, HTMLResponse
        import uvicorn

        app = FastAPI(title="Argos Universal OS", version="1.3.0")

        @app.get("/")
        async def root():
            return HTMLResponse("""
            <html><head><title>ARGOS v1.3</title></head>
            <body style="background:#0a0a0a;color:#00ff41;font-family:monospace;padding:20px">
            <h1>🔱 ARGOS UNIVERSAL OS v1.3</h1>
            <p>API: <a href="/docs" style="color:#00ff41">/docs</a></p>
            <p>Status: <a href="/api/status" style="color:#00ff41">/api/status</a></p>
            </body></html>""")

        @app.get("/api/status")
        async def status():
            if not core: return JSONResponse({"status":"core_not_loaded"})
            r = core.process("статус системы")
            return JSONResponse({"status":"ok","answer":r.get("answer","") if isinstance(r,dict) else str(r)})

        @app.post("/api/command")
        async def command(body: dict):
            if not core: return JSONResponse({"error":"core_not_loaded"},status_code=503)
            text = body.get("text","").strip()
            if not text: return JSONResponse({"error":"empty command"},status_code=400)
            r = core.process(text)
            return JSONResponse(r if isinstance(r,dict) else {"answer":str(r)})

        @app.get("/api/health")
        async def health():
            return JSONResponse({"status":"ok","version":"1.3.0"})

        return app, uvicorn

    except ImportError:
        log.warning("FastAPI/uvicorn не установлены")
        return None, None

def run_dashboard(core=None, host="0.0.0.0", port=8080):
    app, uvicorn = create_app(core)
    if app is None: return
    log.info("Dashboard: http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")
