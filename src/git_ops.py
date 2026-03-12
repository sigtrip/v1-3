"""git_ops.py — Безопасные Git-операции Аргоса"""
from __future__ import annotations
import fnmatch, os, subprocess
from src.argos_logger import get_logger
log = get_logger("argos.gitops")

class ArgosGitOps:
    DEFAULT_DENYLIST = [".env","*.env",".pem",".p12",".key",
                        "config/*secret*","config/*token*"]

    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)

    def _run(self, *args, timeout=40):
        p = subprocess.run(["git",*args], cwd=self.repo_path,
            capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, ((p.stdout or "")+(("\n"+p.stderr) if p.stderr else "")).strip()

    def _is_repo(self):
        return self._run("rev-parse","--is-inside-work-tree")[0] == 0

    def _branch(self):
        c,o = self._run("rev-parse","--abbrev-ref","HEAD")
        return o.strip() if c==0 else "main"

    def _remote(self):
        c,o = self._run("remote")
        if c!=0: return "origin"
        rs = [x.strip() for x in o.splitlines() if x.strip()]
        return "origin" if "origin" in rs else (rs[0] if rs else "origin")

    def _blocked(self):
        c,o = self._run("status","--short")
        if c!=0: return []
        paths=[]
        for line in o.splitlines():
            if len(line)<4: continue
            p=line[3:].strip()
            if " -> " in p: p=p.split(" -> ",1)[1].strip()
            paths.append(p.replace("\\","/"))
        blocked=[]
        for p in paths:
            n=p.lstrip("./")
            for pat in self.DEFAULT_DENYLIST:
                if fnmatch.fnmatch(n,pat):
                    blocked.append(n); break
        return sorted(set(blocked))

    def status(self):
        if not self._is_repo(): return "❌ Не git-репозиторий."
        c,o = self._run("status","--short")
        if not o.strip(): return f"🌿 Git чистый (branch={self._branch()})"
        return f"🌿 Git ({self._branch()}):\n"+o[:800]

    def commit(self, message: str):
        if not self._is_repo(): return "❌ Не git-репозиторий."
        msg=(message or "").strip()
        if not msg: return "❌ Пустое сообщение."
        c,o=self._run("status","--short")
        if not o.strip(): return "ℹ️ Нет изменений."
        b=self._blocked()
        if b and os.getenv("ARGOS_GITOPS_ALLOW_BLOCKED","0") not in {"1","true"}:
            return f"⛔ Заблокированы чувствительные файлы:\n" + "\n".join(f"  - {p}" for p in b[:10])
        self._run("add","-A")
        c2,o2=self._run("commit","-m",msg,timeout=60)
        if c2!=0: return f"❌ commit error:\n{o2[:500]}"
        return f"✅ Коммит:\n{o2[:500]}"

    def push(self):
        if not self._is_repo(): return "❌ Не git-репозиторий."
        c,o=self._run("push",self._remote(),self._branch(),timeout=90)
        if c!=0: return f"❌ push error:\n{o[:500]}"
        return f"🚀 Push: {self._remote()}/{self._branch()}\n{o[:300]}"

    def commit_and_push(self, message: str):
        r=self.commit(message)
        if r.startswith("❌") or r.startswith("ℹ️"): return r
        return r+"\n\n"+self.push()

GitOps = ArgosGitOps
