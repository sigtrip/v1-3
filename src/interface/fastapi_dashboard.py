"""
fastapi_dashboard.py — современный dashboard Аргоса на FastAPI.
Если FastAPI/uvicorn недоступны, core автоматически использует legacy dashboard.
"""
import hashlib
import json
import os
import threading
import time
from collections import deque

from src.argos_logger import get_logger

log = get_logger("argos.fastapi_dashboard")


class FastAPIDashboard:
    def __init__(self, core, admin, flasher, port: int = 8080):
        self.core = core
        self.admin = admin
        self.flasher = flasher
        self.port = port
        self._start_t = time.time()
        self._thread = None
        self._server = None
        self._history = deque(maxlen=120)
        self._status_cache = None
        self._status_cache_ts = 0.0
        self._log_cache = ""
        self._log_cache_ts = 0.0
        self._log_etag = ""
        self._log_mtime = 0.0
        self._dashboard_rev = 0

    def start(self) -> str:
        try:
            from fastapi import FastAPI, Request, Response
            from fastapi.responses import HTMLResponse, JSONResponse
            import psutil
            import uvicorn
        except Exception as e:
            return f"❌ FastAPI Dashboard: {e}"

        app = FastAPI(title="Argos Dashboard", docs_url="/docs")

        html = """<!doctype html><html lang='ru'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width, initial-scale=1'/><title>Argos FastAPI Dashboard</title><script src='https://cdn.jsdelivr.net/npm/chart.js'></script><style>body{font-family:Inter,Arial,sans-serif;background:#0b1020;color:#dce7ff;margin:0;padding:20px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#131b35;border:1px solid #243055;border-radius:12px;padding:14px}button{padding:8px 12px;border-radius:8px;border:1px solid #3d4f88;background:#1b2957;color:#dce7ff;cursor:pointer}input{padding:8px;border-radius:8px;border:1px solid #3d4f88;background:#0f1732;color:#dce7ff;width:100%}pre{background:#0a1024;padding:10px;border-radius:8px;max-height:260px;overflow:auto}.row{display:flex;gap:8px}.small{opacity:.8;font-size:.9em}</style></head><body><h2>👁️ Argos FastAPI Dashboard</h2><div class='small'>Метрики, логи, команды</div><div class='grid'><div class='card'><canvas id='chart'></canvas></div><div class='card'><div id='stats'>Loading...</div><div class='row' style='margin-top:10px'><button onclick='toggleVoice()' id='voiceBtn'>Toggle Voice</button><button onclick='quick(`iot статус`)'>IoT</button><button onclick='quick(`шаблоны шлюзов`)'>Gateways</button></div></div><div class='card'><div class='row'><input id='cmd' placeholder='Команда...' onkeydown='if(event.key===`Enter`)sendCmd()'/><button onclick='sendCmd()'>Send</button></div><pre id='resp'></pre></div><div class='card'><pre id='log'></pre></div></div><script>const ctx=document.getElementById('chart');const chart=new Chart(ctx,{type:'line',data:{labels:[],datasets:[{label:'CPU %',data:[],borderColor:'#40c4ff'},{label:'RAM %',data:[],borderColor:'#7CFF6B'}]}});let voiceOn=false;async function tick(){const r=await fetch('/api/status');const d=await r.json();voiceOn=!!d.voice_on;document.getElementById('voiceBtn').innerText=voiceOn?'🔇 Voice OFF':'🔊 Voice ON';document.getElementById('stats').innerHTML=`<b>${d.state}</b><br/>CPU: ${d.cpu.toFixed(1)}% · RAM: ${d.ram.toFixed(1)}% · Disk: ${d.disk.toFixed(1)}%<br/>Uptime: ${d.uptime} · P2P: ${d.p2p_nodes}`;chart.data.labels.push(new Date().toLocaleTimeString());chart.data.datasets[0].data.push(d.cpu);chart.data.datasets[1].data.push(d.ram);if(chart.data.labels.length>30){chart.data.labels.shift();chart.data.datasets[0].data.shift();chart.data.datasets[1].data.shift()}chart.update();const lg=await fetch('/api/log');const j=await lg.json();document.getElementById('log').textContent=j.lines||'';}async function sendCmd(){const v=document.getElementById('cmd').value.trim();if(!v)return;document.getElementById('cmd').value='';const r=await fetch('/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:v})});const d=await r.json();document.getElementById('resp').textContent=d.answer||d.error||'-';setTimeout(tick,200);}function quick(cmd){document.getElementById('cmd').value=cmd;sendCmd();}function toggleVoice(){quick(voiceOn?'голос выкл':'голос вкл')}setInterval(tick,2500);tick();</script></body></html>"""
        html = html.replace(
            "<button onclick='sendCmd()'>Send</button>",
            "<button onclick='sendCmd()'>Send</button><button onclick='startListen()'>🎙 Listen</button>",
            1,
        )
        html = html.replace(
            "function toggleVoice(){quick(voiceOn?'голос выкл':'голос вкл')}setInterval(tick,2500);tick();",
            "function startListen(){const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){document.getElementById('resp').textContent='SpeechRecognition not supported';return;}const rec=new SR();rec.lang='ru-RU';rec.interimResults=false;rec.maxAlternatives=1;document.getElementById('resp').textContent='🎙 Listening...';rec.onresult=(event)=>{const text=((event.results||[])[0]||[])[0]?.transcript||'';if(!text.trim()){document.getElementById('resp').textContent='Not recognized';return;}document.getElementById('cmd').value=text.trim();sendCmd();};rec.onerror=(e)=>{document.getElementById('resp').textContent='Mic error: '+(e.error||'unknown');};rec.start();}function toggleVoice(){quick(voiceOn?'голос выкл':'голос вкл')}setInterval(tick,2500);tick();",
            1,
        )
        html = html.replace(
            "let voiceOn=false;",
            "let voiceOn=false;let dashboardRev=0;",
            1,
        )
        html = html.replace(
            "const r=await fetch('/api/status');const d=await r.json();",
            "const r=await fetch('/api/dashboard?since='+dashboardRev);const d=await r.json();if(d.changed===false){dashboardRev=d.rev||dashboardRev;return;}dashboardRev=d.rev||dashboardRev;",
            1,
        )
        html = html.replace(
            "const lg=await fetch('/api/log');const j=await lg.json();document.getElementById('log').textContent=j.lines||'';",
            "document.getElementById('log').textContent=d.log_lines||'';",
            1,
        )

        def _refresh_status(now: float):
            if self._status_cache is not None and (now - self._status_cache_ts) < 1.0:
                return
            uptime_s = int(time.time() - self._start_t)
            h, m = divmod(uptime_s // 60, 60)
            uptime = f"{h}ч {m}мин"
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            state = self.core.quantum.generate_state()["name"] if self.core else "Offline"
            voice = bool(self.core.voice_on) if self.core else False
            p2p_nodes = len(self.core.p2p.registry.all()) if self.core and self.core.p2p else 0
            self._history.append({"ts": time.time(), "cpu": cpu, "ram": ram, "disk": disk})
            payload = {
                "state": state,
                "voice_on": voice,
                "uptime": uptime,
                "cpu": cpu,
                "ram": ram,
                "disk": disk,
                "p2p_nodes": p2p_nodes,
                "history": list(self._history),
            }
            if payload != self._status_cache:
                self._dashboard_rev += 1
            self._status_cache = payload
            self._status_cache_ts = now

        def _refresh_logs(now: float):
            try:
                log_path = "logs/argos.log"
                if os.path.exists(log_path):
                    mtime = os.path.getmtime(log_path)
                    if mtime != self._log_mtime or (now - self._log_cache_ts) > 1.0:
                        prev = self._log_cache
                        with open(log_path, encoding="utf-8") as f:
                            lines = "".join(f.readlines()[-120:])
                        self._log_cache = lines
                        self._log_cache_ts = now
                        self._log_mtime = mtime
                        self._log_etag = hashlib.md5(f"{mtime}:{len(lines)}".encode("utf-8")).hexdigest()
                        if self._log_cache != prev:
                            self._dashboard_rev += 1
            except Exception:
                pass

        @app.get("/", response_class=HTMLResponse)
        async def index():
            return HTMLResponse(content=html)

        @app.get("/api/status")
        async def status():
            now = time.time()
            _refresh_status(now)
            return JSONResponse(self._status_cache)

        @app.get("/api/log")
        async def logs(request: Request):
            now = time.time()
            _refresh_logs(now)

            inm = (request.headers.get("if-none-match") or "").strip('"')
            if inm and self._log_etag and inm == self._log_etag:
                return Response(status_code=304, headers={"ETag": self._log_etag, "Cache-Control": "no-cache"})

            return JSONResponse({"lines": self._log_cache}, headers={"ETag": self._log_etag, "Cache-Control": "no-cache"})

        @app.get("/api/dashboard")
        async def dashboard(request: Request):
            """Batch endpoint with delta/since support."""
            now = time.time()
            _refresh_status(now)
            _refresh_logs(now)

            try:
                since = int((request.query_params.get("since") or "0").strip() or 0)
            except Exception:
                since = 0

            if since >= self._dashboard_rev:
                return JSONResponse({"changed": False, "rev": self._dashboard_rev})

            payload = dict(self._status_cache)
            payload["changed"] = True
            payload["rev"] = self._dashboard_rev
            payload["log_lines"] = self._log_cache
            payload["log_etag"] = self._log_etag
            return JSONResponse(payload)

        @app.post("/api/cmd")
        async def cmd(payload: dict):
            command = (payload or {}).get("cmd", "")
            if not command:
                return JSONResponse({"error": "Пустая команда"}, status_code=400)
            try:
                result = await self.core.process_logic_async(command, self.admin, self.flasher)
                return JSONResponse(result)
            except Exception as e:
                return JSONResponse({"answer": f"Ошибка: {e}"})

        config = uvicorn.Config(app=app, host="0.0.0.0", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)

        def _run():
            self._server.run()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        log.info("FastAPI Dashboard запущен на http://localhost:%d", self.port)
        return f"🌐 FastAPI панель: http://localhost:{self.port}"

    def stop(self):
        if self._server:
            self._server.should_exit = True


# README-compatible aliases
ArgosAPI = FastAPIDashboard
create_app = FastAPIDashboard
