import customtkinter as ctk
import threading

class ArgosGUI(ctk.CTk):
    def __init__(self, core, admin, flasher, location):
        super().__init__()
        self.core    = core
        self.admin   = admin
        self.flasher = flasher
        self._listening = False

        self.title("ARGOS UNIVERSAL OS")
        self.geometry("1100x700")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Sidebar ───────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=260)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="👁️ ARGOS OS",
                     font=("Consolas", 20, "bold"), text_color="#00FFFF").pack(pady=16)

        ctk.CTkLabel(self.sidebar, text=f"📍 {location}",
                     wraplength=230, justify="left", font=("Consolas", 11)).pack(pady=4)

        self.q_label = ctk.CTkLabel(self.sidebar, text="⚛ Состояние: —",
                                    text_color="#00FF88", font=("Consolas", 12))
        self.q_label.pack(pady=6)

        self.voice_label = ctk.CTkLabel(self.sidebar, text=f"🔊 Голос: {'ВКЛ' if self.core.voice_on else 'ВЫКЛ'}",
                                        text_color="#88FF00", font=("Consolas", 11))
        self.voice_label.pack(pady=2)

        self.voice_toggle_btn = ctk.CTkButton(
            self.sidebar,
            text=("🔇 Отключить голос" if self.core.voice_on else "🔊 Включить голос"),
            height=30,
            command=self._toggle_voice_mode,
        )
        self.voice_toggle_btn.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(self.sidebar, text="🤖 Модель ИИ",
                     font=("Consolas", 11), text_color="#bbbbbb").pack(pady=(8, 2))
        self.ai_mode_var = ctk.StringVar(value=self._ai_mode_to_ui(self.core.ai_mode))
        self.ai_mode_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["Auto", "Gemini", "GigaChat", "YandexGPT", "Ollama", "Watsonx", "OpenAI", "Grok"],
            variable=self.ai_mode_var,
            command=self._on_ai_mode_changed,
        )
        self.ai_mode_menu.pack(fill="x", padx=10, pady=3)

        self.ai_mode_label = ctk.CTkLabel(
            self.sidebar,
            text=f"Режим ИИ: {self.core.ai_mode_label()}",
            text_color="#88c0ff",
            font=("Consolas", 11),
        )
        self.ai_mode_label.pack(pady=2)

        ctk.CTkLabel(self.sidebar, text="─" * 28, text_color="#333").pack(pady=8)

        # Быстрые кнопки
        for label, cmd in [
            ("📊 Статус системы",    "статус системы"),
            ("🪙 Крипто",            "крипто"),
            ("📡 Сканировать сеть",  "сканируй сеть"),
            ("📰 AI Дайджест",       "дайджест"),
            ("🔍 Сканируй порты",    "сканируй порты"),
            ("💾 Создать копию",     "репликация"),
            ("📡 IoT статус",        "iot статус"),
            ("🏭 IoT протоколы",     "iot протоколы"),
            ("🧩 Шаблоны шлюзов",    "шаблоны шлюзов"),
        ]:
            btn = ctk.CTkButton(self.sidebar, text=label, height=32,
                                command=lambda c=cmd: self._send_text(c))
            btn.pack(fill="x", padx=10, pady=3)

        ctk.CTkButton(
            self.sidebar,
            text="📟 Статус устройства",
            height=32,
            command=self._prompt_device_status,
        ).pack(fill="x", padx=10, pady=3)

        ctk.CTkButton(
            self.sidebar,
            text="🛠 Создай прошивку",
            height=32,
            command=self._prompt_create_firmware,
        ).pack(fill="x", padx=10, pady=3)

        ctk.CTkLabel(self.sidebar, text="─" * 28, text_color="#333").pack(pady=8)

        self.voice_btn = ctk.CTkButton(self.sidebar, text="🎙 Слушай меня",
                                       height=40, fg_color="#1a4a1a",
                                       hover_color="#2a6a2a",
                                       command=self._toggle_listen)
        self.voice_btn.pack(fill="x", padx=10, pady=4)

        # ── Чат ───────────────────────────────────────────
        self.chat = ctk.CTkTextbox(self, font=("Consolas", 13), wrap="word")
        self.chat.pack(side="top", fill="both", expand=True, padx=(0,10), pady=10)
        self.chat.configure(state="disabled")

        # ── Ввод ──────────────────────────────────────────
        inp = ctk.CTkFrame(self, fg_color="transparent")
        inp.pack(side="bottom", fill="x", padx=(0,10), pady=(0,10))

        self.entry = ctk.CTkEntry(inp, placeholder_text="Директива для Аргоса...", height=42,
                                  font=("Consolas", 13))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0,8))
        self.entry.bind("<Return>", lambda e: self._send_text(self.entry.get()))

        ctk.CTkButton(inp, text="▶ EXECUTE", width=110, height=42,
                      command=lambda: self._send_text(self.entry.get())).pack(side="right")

    # ── ОТПРАВКА ──────────────────────────────────────────
    def _send_text(self, text: str):
        if not text or not text.strip():
            return
        self.entry.delete(0, "end")
        state = self.core.quantum.generate_state()['name'][:3].upper()
        self._append(f"[{state}] ВСЕВОЛОД: {text}\n", "#5599ff")
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _process(self, text: str):
        res = self.core.process_logic(text, self.admin, self.flasher)
        self.after(0, self._on_response, res)

    def _on_response(self, res: dict):
        self.q_label.configure(text=f"⚛ Состояние: {res['state']}")
        self._append(f"👁 АРГОС [{res['state']}]:\n{res['answer']}\n\n", "#00d4ff")
        # Голос — уже вызывается внутри core.process_logic через self.say()
        v = "ВКЛ" if self.core.voice_on else "ВЫКЛ"
        self.voice_label.configure(text=f"🔊 Голос: {v}")
        self.voice_toggle_btn.configure(
            text=("🔇 Отключить голос" if self.core.voice_on else "🔊 Включить голос")
        )

    # ── ГОЛОСОВОЙ ВВОД ────────────────────────────────────
    def _toggle_listen(self):
        if self._listening:
            return
        self._listening = True
        self.voice_btn.configure(text="🔴 Слушаю...", fg_color="#4a1a1a")
        self._append("🎙 Слушаю тебя... Говори команду.\n", "#88ff88")
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _toggle_voice_mode(self):
        self.core.voice_on = not self.core.voice_on
        v = "ВКЛ" if self.core.voice_on else "ВЫКЛ"
        self.voice_label.configure(text=f"🔊 Голос: {v}")
        self.voice_toggle_btn.configure(
            text=("🔇 Отключить голос" if self.core.voice_on else "🔊 Включить голос")
        )
        self._append(f"🔈 Голосовой режим: {v}\n", "#88ff88")

    def _ai_mode_to_ui(self, mode: str) -> str:
        value = (mode or "auto").strip().lower()
        if value == "gemini":
            return "Gemini"
        if value == "gigachat":
            return "GigaChat"
        if value == "yandexgpt":
            return "YandexGPT"
        if value == "ollama":
            return "Ollama"
        if value == "watsonx":
            return "Watsonx"
        if value == "openai":
            return "OpenAI"
        if value == "grok":
            return "Grok"
        return "Auto"

    def _ui_to_ai_mode(self, mode: str) -> str:
        value = (mode or "Auto").strip().lower()
        if value == "gemini":
            return "gemini"
        if value == "gigachat":
            return "gigachat"
        if value == "yandexgpt":
            return "yandexgpt"
        if value == "ollama":
            return "ollama"
        if value == "watsonx":
            return "watsonx"
        if value == "openai":
            return "openai"
        if value == "grok":
            return "grok"
        return "auto"

    def _on_ai_mode_changed(self, selected: str):
        mode = self._ui_to_ai_mode(selected)
        msg = self.core.set_ai_mode(mode)
        self.ai_mode_label.configure(text=f"Режим ИИ: {self.core.ai_mode_label()}")
        self._append(f"{msg}\n", "#88c0ff")

    def _listen_loop(self):
        text = self.core.listen()
        self.after(0, self._after_listen, text)

    def _after_listen(self, text: str):
        self._listening = False
        self.voice_btn.configure(text="🎙 Слушай меня", fg_color="#1a4a1a")
        if text:
            self._send_text(text)
        else:
            self._append("👂 Не распознано. Попробуй снова.\n", "#ff8800")

    def _prompt_device_status(self):
        dlg = ctk.CTkInputDialog(text="ID устройства", title="Статус устройства")
        dev_id = (dlg.get_input() or "").strip()
        if dev_id:
            self._send_text(f"статус устройства {dev_id}")

    def _prompt_create_firmware(self):
        dlg = ctk.CTkInputDialog(
            text="Формат: id шаблон [порт]\nПример: gw1 esp32_lora /dev/ttyUSB0",
            title="Создай прошивку"
        )
        args = (dlg.get_input() or "").strip()
        if args:
            self._send_text(f"создай прошивку {args}")

    # ── ВЫВОД В ЧАТ ───────────────────────────────────────
    def _append(self, text: str, color: str = "#ffffff"):
        self.chat.configure(state="normal")
        self.chat.insert("end", text)
        self.chat.see("end")
        self.chat.configure(state="disabled")
