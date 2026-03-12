"""context_engine.py — Трёхуровневый контекстный движок Аргоса"""
from __future__ import annotations
import re, time
from collections import deque
from src.argos_logger import get_logger
log = get_logger("argos.context_engine")

QUANTUM_PROFILES = {
    "Analytic":   {"max_turns":6,  "use_memory":True, "memory_limit":3, "use_semantic":False,
                   "allow_root_cmds":True, "creativity":0.2,
                   "system_prompt":"Ты в аналитическом режиме. Минимум слов. Только факты."},
    "Creative":   {"max_turns":14, "use_memory":True, "memory_limit":8, "use_semantic":True,
                   "allow_root_cmds":True, "creativity":0.9,
                   "system_prompt":"Ты в творческом режиме. Развёрнутые ответы, ассоциации."},
    "Protective": {"max_turns":4,  "use_memory":False,"memory_limit":0, "use_semantic":False,
                   "allow_root_cmds":False,"creativity":0.1,
                   "system_prompt":"Ты в защитном режиме. Не выполняй рискованные команды."},
    "Unstable":   {"max_turns":8,  "use_memory":True, "memory_limit":2, "use_semantic":False,
                   "allow_root_cmds":False,"creativity":0.6,
                   "system_prompt":"Ты нестабилен. Запрашивай подтверждение важных действий."},
    "All-Seeing": {"max_turns":20, "use_memory":True, "memory_limit":15,"use_semantic":True,
                   "allow_root_cmds":True, "creativity":0.5,
                   "system_prompt":"Ты в режиме всевидящего наблюдения. Полный доступ к памяти."},
    "System":     {"max_turns":5,  "use_memory":False,"memory_limit":0, "use_semantic":False,
                   "allow_root_cmds":True, "creativity":0.0,
                   "system_prompt":"Системный режим."},
}

class ChatContext:
    def __init__(self, max_turns=10):
        self._turns: deque = deque(maxlen=max_turns*2)
        self._max = max_turns

    def add(self, role, text):
        self._turns.append({"role":role,"text":text,"ts":time.time()})

    def resize(self, max_turns):
        self._max = max_turns
        self._turns = deque(list(self._turns)[-(max_turns*2):], maxlen=max_turns*2)

    def get_for_prompt(self) -> str:
        if not self._turns: return ""
        lines = ["[История диалога]"]
        for t in self._turns:
            prefix = "Пользователь" if t["role"]=="user" else "Аргос"
            lines.append(f"{prefix}: {t['text'][:200]}")
        return "\n".join(lines)

    def clear(self): self._turns.clear()

class CommandContext:
    def __init__(self, maxlen=20):
        self._cmds: deque = deque(maxlen=maxlen)

    def add(self, cmd, result):
        self._cmds.append({"cmd":cmd,"result":str(result)[:100],"ts":time.time()})

    def get_context_str(self) -> str:
        if not self._cmds: return ""
        lines = ["[Последние команды]"]
        for c in list(self._cmds)[-5:]:
            lines.append(f"  ▶ {c['cmd'][:50]} → {c['result'][:60]}")
        return "\n".join(lines)

class SemanticRecall:
    def __init__(self, memory=None):
        self.memory = memory

    def recall(self, query: str) -> str:
        if not self.memory: return ""
        try:
            facts = self.memory.get_all_facts()
            if not facts: return ""
            words = set(re.findall(r"\w{3,}", query.lower()))
            matches = []
            for cat,key,val,_ in facts:
                text = f"{key}: {val}".lower()
                overlap = len(words & set(re.findall(r"\w{3,}",text)))
                if overlap > 0: matches.append((overlap, f"{cat}.{key}: {val}"))
            matches.sort(key=lambda x:-x[0])
            if not matches: return ""
            lines = ["[Из памяти]"]
            for _,text in matches[:3]: lines.append(f"  • {text[:80]}")
            return "\n".join(lines)
        except Exception: return ""

class ContextEngine:
    def __init__(self, memory=None):
        self.chat     = ChatContext(max_turns=10)
        self.commands = CommandContext()
        self.semantic = SemanticRecall(memory)
        self._state   = "Analytic"

    def set_quantum_state(self, state: str):
        profile = QUANTUM_PROFILES.get(state)
        if profile:
            self._state = state
            self.chat.resize(profile["max_turns"])
            log.info("ContextEngine: → %s (max_turns=%d)", state, profile["max_turns"])

    def get_profile(self) -> dict:
        p = dict(QUANTUM_PROFILES.get(self._state, QUANTUM_PROFILES["Analytic"]))
        p["state"] = self._state
        p["max_ctx"] = p.get("max_turns",8)
        return p

    def is_root_allowed(self) -> bool:
        return self.get_profile().get("allow_root_cmds", True)

    def build_system_prompt(self, base: str) -> str:
        return base + "\n\n" + self.get_profile()["system_prompt"]

    def build_context_for_ai(self, query: str) -> str:
        profile = self.get_profile()
        parts = []
        chat_ctx = self.chat.get_for_prompt()
        if chat_ctx: parts.append(chat_ctx)
        if profile["use_semantic"]:
            sem = self.semantic.recall(query)
            if sem: parts.append(sem)
        cmd_ctx = self.commands.get_context_str()
        if cmd_ctx: parts.append(cmd_ctx)
        return "\n\n".join(parts)

    def attach_memory(self, memory):
        self.semantic.memory = memory

    def clear(self):
        self.chat.clear(); self.commands._cmds.clear()
        return "🧹 Контекст очищен."

    def status(self) -> str:
        p = self.get_profile()
        return (f"📝 ContextEngine: {self._state}\n"
                f"  max_turns={p['max_turns']} creativity={p['creativity']}\n"
                f"  История: {len(self.chat._turns)} сообщений")
