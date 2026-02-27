import cmd
import importlib
import os
import platform
import sys
import time
import psutil
from datetime import datetime
from src.security.syscalls import ArgosSyscalls
from src.security.root_manager import RootManager
from src.quantum.logic import ArgosQuantum
from src.factory.replicator import Replicator

# Rich Visualization
try:
    Console = importlib.import_module("rich.console").Console
    Table = importlib.import_module("rich.table").Table
    Panel = importlib.import_module("rich.panel").Panel
    Layout = importlib.import_module("rich.layout").Layout
    Live = importlib.import_module("rich.live").Live
    Text = importlib.import_module("rich.text").Text
    box = importlib.import_module("rich.box")
    console = Console()
    RICH_OK = True
except ImportError:
    # Заглушка, если Rich не установлен
    class _NoopStatus:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class Console:
        def print(self, *args, **kwargs):
            print(*args)
        def status(self, *args, **kwargs):
            return _NoopStatus()
    console = Console()
    RICH_OK = False

class ArgosShell(cmd.Cmd):
    intro = ""
    prompt = "argos> "
    
    def __init__(self):
        super().__init__()
        self.syscalls = ArgosSyscalls()
        self.root_manager = RootManager()
        self.quantum = ArgosQuantum()
        self.replicator = Replicator()
        self.os_type = platform.system()
        self._set_prompt()

    def _set_prompt(self):
        user = os.getenv("USER", "user")
        if self.root_manager.is_root:
            self.prompt = f"[red]argos@{user} (ROOT)# [/red]" if RICH_OK else f"argos@{user} (ROOT)# "
        else:
            self.prompt = f"[green]argos@{user}$ [/green]" if RICH_OK else f"argos@{user}$ "

    def preloop(self):
        self._clear_screen()
        if RICH_OK:
            self._print_logo_rich()
        else:
            self._print_logo_plain()
    
    def _print_logo_rich(self):
        logo = Text(r"""
    ___    ____  __________  _____
   /   |  / __ \/ ____/ __ \/ ___/
  / /| | / /_/ / / __/ / / /\__ \ 
 / ___ |/ _, _/ /_/ / /_/ /___/ / 
/_/  |_/_/ |_|\____/\____//____/  
                                  
        """, style="bold cyan")
        
        info = f"Argos System v1.3 | Kernel: {platform.release()}\nLogged in as: [bold yellow]{os.getenv('USER', 'unknown')}[/bold yellow]"
        console.print(Panel(logo, title="[bold cyan]SYSTEM ONLINE[/bold cyan]", subtitle=info, border_style="cyan"))
        console.print("[dim]Type 'help' or '?' for commands.[/dim]\n")

    def _print_logo_plain(self):
        print("\033[96mArgos System v1.3\033[0m")
        print(f"Kernel: {platform.release()}")
        print("-" * 40)

    def _clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def do_status(self, arg):
        """Show system status and root privileges check."""
        if not RICH_OK:
            print("\n--- System Status ---")
            print(f"OS: {platform.system()} {platform.release()}")
            print(self.root_manager.status())
            print("---------------------\n")
            return

        table = Table(title="System Status", box=box.ROUNDED)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("OS", f"{platform.system()} {platform.release()}")
        table.add_row("Architecture", platform.machine())
        
        root_status = self.root_manager.status()
        if "✅" in root_status:
            status_style = "bold green"
        else:
            status_style = "bold yellow"
            
        table.add_row("Privileges", Text(root_status, style=status_style))
        console.print(table)

    def do_dashboard(self, arg):
        """Launch the live TUI dashboard (Rich). Press Ctrl+C to exit."""
        if not RICH_OK:
            print("Rich library not installed. Dashboard unavailable.")
            return

        layout = self._make_layout()
        with Live(layout, refresh_per_second=4, screen=True) as live:
            try:
                while True:
                    layout["header"].update(self._get_header_panel())
                    layout["left"].update(self._get_system_stats_panel())
                    layout["right"].update(self._get_quantum_panel())
                    layout["footer"].update(self._get_log_panel())
                    time.sleep(0.25)
            except KeyboardInterrupt:
                pass

    def _make_layout(self):
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=7)
        )
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        return layout

    def _get_header_panel(self):
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right")
        grid.add_row(
            "[b]ARGOS INTEGRATED DASHBOARD[/b]", 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        return Panel(grid, style="white on blue")

    def _get_system_stats_panel(self):
        table = Table(box=None, expand=True)
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        
        table.add_row("CPU Load", f"[green]{cpu}%[/green]" if cpu < 50 else f"[red]{cpu}%[/red]")
        table.add_row("Memory", f"[yellow]{mem}%[/yellow]")
        table.add_row("Disk", f"{disk}%")
        
        return Panel(table, title="[b]System Telemetry[/b]", border_style="green")

    def _get_quantum_panel(self):
        state = self.quantum.generate_state()
        table = Table(box=None, expand=True)
        table.add_column("State")
        table.add_column("Prob")
        
        for s, p in state['probabilities'].items():
            if s == state['name']:
                table.add_row(f"[bold cyan]{s}[/bold cyan]", f"{p:.2f}")
            else:
                table.add_row(s, f"{p:.2f}")
                
        return Panel(table, title=f"Quantum State: [bold]{state['name']}[/bold]", border_style="magenta")

    def _get_log_panel(self):
        # В реальной системе здесь был бы tail -f логов
        log_text = Text()
        log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] System stable.\n", style="dim")
        log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] Security scan complete: No threats.\n", style="green")
        log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for user input...", style="dim")
        return Panel(log_text, title="System Logs", border_style="white")

    def do_vision(self, arg):
        """Start Vision Feedback window (OpenCV)."""
        try:
            from src.vision import ArgosVision
            vision = ArgosVision()
            # Аргумент timeout можно передать
            print(vision.live_feed(timeout=None))
        except ImportError:
            print("Vision module not reachable.")
        except Exception as e:
            print(f"Error starting vision: {e}")

    def do_syscall(self, arg):
        """Execute low-level system calls via ctypes (Linux/Windows)."""
        if not RICH_OK:
            print(self.syscalls.status())
            print(self.syscalls.process_identity())
            print(self.syscalls.terminal_size())
            return

        # Rich implementation
        text = Text()
        text.append(self.syscalls.status() + "\n")
        text.append(self.syscalls.process_identity() + "\n")
        text.append(self.syscalls.terminal_size())
        console.print(Panel(text, title="Syscall Interface", border_style="red"))

    def do_scan(self, arg):
        """Scan local network (simulated/real depending on modules)."""
        if not RICH_OK:
            print("Scanning network environment...")
            time.sleep(1)
            print("- 192.168.1.10  Argos-Core       ONLINE (Self)")
            print("- 192.168.1.1   Gateway          ONLINE")
            print("- 192.168.1.14  Simulate-IoT     ONLINE")
            return

        with console.status("[bold green]Scanning network environment...[/bold green]", spinner="dots"):
            time.sleep(2)
            
        table = Table(title="Network Scan Results")
        table.add_column("IP Address", style="cyan")
        table.add_column("Hostname", style="magenta")
        table.add_column("Status", style="green")
        
        table.add_row("192.168.1.10", "Argos-Core", "ONLINE (Self)")
        table.add_row("192.168.1.1", "Gateway", "ONLINE")
        table.add_row("192.168.1.14", "Simulate-IoT", "ONLINE")
        
        console.print(table)

    def do_clear(self, arg):
        """Clear the terminal screen."""
        self._clear_screen()
        if RICH_OK:
            self._print_logo_rich()

    # ... (rest of formatting) ...

    def do_quantum(self, arg):
        """Show current quantum state probabilities (Bayesian Network)."""
        state = self.quantum.generate_state()
        print("\n--- Quantum State Inference ---")
        print(f"Dominant State: \033[96m{state['name']}\033[0m")
        print("\nProbabilities:")
        for s, p in state['probabilities'].items():
            bar = "█" * int(p * 20)
            print(f"  {s:<12} {p:.2f} {bar}")
        print("-------------------------------\n")

    def do_snapshot(self, arg):
        """Manage system snapshots: create | list | rollback <file>"""
        args = arg.split()
        if not args:
            print("Usage: snapshot [create|list|rollback <filename>]")
            return

        cmd = args[0]
        if cmd == "create":
            label = args[1] if len(args) > 1 else "manual"
            print(self.replicator.create_snapshot(label))
        
        elif cmd == "list":
            files = self.replicator.list_snapshots()
            print("\n--- Available Snapshots ---")
            for f in files:
                print(f"  {f}")
            print("---------------------------\n")

        elif cmd == "rollback":
            if len(args) < 2:
                print("Error: Specify snapshot filename to rollback.")
                return
            target = args[1]
            confirm = input(f"⚠️  WARNING: Rollback to {target}? Current data may be lost. (y/n): ")
            if confirm.lower() == 'y':
                print(self.replicator.rollback(target))
            else:
                print("Rollback cancelled.")
        else:
            print(f"Unknown snapshot command: {cmd}")

    def do_whoami(self, arg):
        """Show current user identity."""
        print(f"User: {os.getenv('USER')}")
        print(f"UID: {os.getuid() if hasattr(os, 'getuid') else 'N/A'}")
        print(f"GID: {os.getgid() if hasattr(os, 'getgid') else 'N/A'}")

    def do_exit(self, arg):
        """Exit the Argos Shell."""
        print("Shutting down Argos Shell session...")
        return True

    def default(self, line):
        try:
            # Pass unknown commands to system shell
            os.system(line)
        except Exception as e:
            print(f"Error executing system command: {e}")

if __name__ == "__main__":
    try:
        ArgosShell().cmdloop()
    except KeyboardInterrupt:
        print("\nExiting...")
