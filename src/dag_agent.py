"""dag_agent.py — DAG-агент параллельного выполнения задач"""
from __future__ import annotations
import json, os, threading, time
from queue import Queue
from typing import Any, Callable
from src.argos_logger import get_logger
log = get_logger("argos.dag")

DAG_DIR = "config/dags"
os.makedirs(DAG_DIR, exist_ok=True)

BUILTIN_FUNCTIONS: dict[str,Callable] = {}

def register(name):
    def decorator(fn):
        BUILTIN_FUNCTIONS[name] = fn; return fn
    return decorator

@register("status")
def node_status(core, data):
    return core._system_status() if core else "no core"

@register("telegram_notify")
def node_telegram(core, data):
    msg = str(data)[:4000] if data else "DAG выполнен"
    log.info("telegram_notify: %s", msg[:80])
    if core and hasattr(core,"telegram") and core.telegram:
        core.telegram.send(msg)
    return f"Уведомление: {msg[:50]}..."

@register("ai_query")
def node_ai(core, data):
    if not core: return "no core"
    r = core.process(str(data)[:500] if data else "статус")
    return r.get("answer","") if isinstance(r,dict) else str(r)

@register("save_file")
def node_save(core, data):
    path = f"logs/dag_result_{int(time.time())}.txt"
    os.makedirs("logs", exist_ok=True)
    with open(path,"w",encoding="utf-8") as f: f.write(str(data) if data else "")
    return f"Сохранено: {path}"

class DAGNode:
    def __init__(self, node_id, func):
        self.node_id = node_id
        self.func = func if callable(func) else BUILTIN_FUNCTIONS.get(func)
        self.result = None
        self.error = None

class DAGAgent:
    def __init__(self, core=None):
        self.core = core
        self.nodes: dict[str,DAGNode] = {}
        self.edges: dict[str,list]    = {}
        self.incoming: dict[str,int]  = {}
        self._dag_id = None
        self._running = False

    def add_node(self, node_id, func):
        self.nodes[node_id] = DAGNode(node_id, func)
        if node_id not in self.edges: self.edges[node_id] = []
        if node_id not in self.incoming: self.incoming[node_id] = 0

    def add_edge(self, from_id, to_id):
        self.edges.setdefault(from_id,[]).append(to_id)
        self.incoming[to_id] = self.incoming.get(to_id,0) + 1

    def run(self, timeout=60) -> dict:
        ready = Queue()
        for nid,cnt in self.incoming.items():
            if cnt == 0: ready.put(nid)
        results = {}
        self._running = True
        t0 = time.time()
        while not ready.empty() and self._running:
            if time.time()-t0 > timeout:
                log.warning("DAG timeout"); break
            nid = ready.get()
            node = self.nodes[nid]
            try:
                input_data = results.get(list(self.edges.keys())[0]) if results else None
                node.result = node.func(self.core, input_data) if node.func else f"no func: {nid}"
            except Exception as e:
                node.error = str(e); node.result = f"ERROR: {e}"
                log.error("DAG node %s: %s", nid, e)
            results[nid] = node.result
            for next_id in self.edges.get(nid,[]):
                self.incoming[next_id] -= 1
                if self.incoming[next_id] == 0: ready.put(next_id)
        self._running = False
        return results

    def from_chain(self, steps: list[str]):
        """Создаёт линейный DAG из списка шагов."""
        self.nodes.clear(); self.edges.clear(); self.incoming.clear()
        for i,step in enumerate(steps):
            nid = f"step_{i}"
            self.add_node(nid, step)
            if i > 0: self.add_edge(f"step_{i-1}", nid)
        return self

    def status(self) -> str:
        return (f"🌐 DAG-Агент:\n"
                f"  Узлов: {len(self.nodes)}  Выполняется: {self._running}")
