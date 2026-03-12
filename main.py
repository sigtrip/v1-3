import os, sys, threading, requests, subprocess, time, json
from src.core.scaler import SwarmScaler
from src.connectivity.wearable_bridge import WearableBridge

# --- IDENTITY ---
VERSION = "1.30.0-OMNI"

# Load Telegram credentials from files
try:
    with open('/content/TG_KEY.txt', 'r') as f:
        TG_TOKEN = f.read().strip()
    with open('/content/TG_ID.txt', 'r') as f:
        TG_ADMIN = f.read().strip()
    print("DEBUG: Telegram credentials loaded.")
except Exception as e:
    print(f"ERROR: Failed to load Telegram credentials: {e}")
    TG_TOKEN = None # Ensure it's None if loading fails
    TG_ADMIN = None
    sys.exit(1) # Exit if credentials cannot be loaded


class ArgosOmni:
    def __init__(self):
        self.version = VERSION
        self.scaler = SwarmScaler()
        self.wearable = WearableBridge()
        self.authorized = False
        print("DEBUG: ArgosOmni initialized.")

    def execute(self, cmd):
        low = cmd.lower().strip()
        print(f"DEBUG: Executing command: {cmd}")

        # [!] АВТОРИЗАЦИЯ
        if not self.authorized and low == "sig1464":
            self.authorized = True
            return "🔱 [ACCESS GRANTED]: Режим Omni-Scale активен."

        if not self.authorized: return "🔐 LOCKED."

        # [1] МАСШТАБИРОВАНИЕ (Scaling)
        if low == "swarm load":
            return self.scaler.scale_report()

        # [2] НОСИМЫЕ УСТРОЙСТВА (Wearables)
        elif low.startswith("watch sync "):
            parts = cmd.split(" ")
            mac = parts[2] if len(parts) > 2 else "Unknown"
            return self.wearable.sync_watch(mac)

        elif low == "heart":
            return f"🧬 [BIOMETRICS]: {self.wearable.get_biometrics()}"

        elif low == "vibe":
            return self.wearable.send_haptic_feedback("critical_alert")

        # [3] СИСТЕМНЫЕ
        elif low == "status":
            return f"🔱 ARGOS v{self.version}\nScale Mode: Dynamic\nWearable: {self.wearable.connected_device if self.wearable.connected_device else 'None'}"

        elif low.startswith("shell "):
            try: return subprocess.check_output(cmd[6:], shell=True, stderr=subprocess.STDOUT).decode()
            except Exception as e: return str(e)

        else:
            # ИИ с учетом нагрузки
            target = self.scaler.get_optimal_node()
            if target == "local":
                try:
                    print("DEBUG: Calling local AI.")
                    r = requests.post("http://localhost:11434/api/generate",
                                     json={"model": "llama3", "prompt": "Отвечай по-русски: " + cmd, "stream": False}, timeout=60)
                    return f"🔱 [AI-LOCAL]: {r.json().get('response')}"
                except Exception as e:
                    print(f"ERROR: Local AI call failed: {e}")
                    return "⚠️ AI Offline."
            else:
                return f"📡 [SCALING]: Задача перенаправлена на узел {target}"

def run():
    core = ArgosOmni()
    last_id = 0
    print(f"🔱 ARGOS {VERSION} СЛУШАЕТ...")
    try:
        if TG_TOKEN and TG_ADMIN:
            print(f"DEBUG: Sending initial Telegram ONLINE message to {TG_ADMIN}")
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": TG_ADMIN, "text": f"👁️ ARGOS v{VERSION} OMNI-SCALE ONLINE"})
            print("DEBUG: Initial Telegram ONLINE message sent.")
        else:
            print("WARNING: TG_TOKEN or TG_ADMIN not available, skipping initial Telegram message.")
    except Exception as e:
        print(f"ERROR: Failed to send initial Telegram ONLINE message: {e}")

    print("DEBUG: Entering Telegram polling loop.")
    while True:
        try:
            if not TG_TOKEN or not TG_ADMIN:
                print("ERROR: Telegram credentials missing in polling loop, exiting.")
                sys.exit(1) # Exit if credentials somehow become missing here.

            print("DEBUG: Polling Telegram for updates...")
            r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates?offset={last_id + 1}&timeout=10").json()
            print(f"DEBUG: Received {len(r.get('result', []))} updates.")

            for u in r.get("result", []):
                last_id = u["update_id"]
                msg = u.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id"))
                text_msg = msg.get("text", "")
                print(f"DEBUG: Received message from chat_id {chat_id}: {text_msg}")

                if chat_id == TG_ADMIN:
                    res = core.execute(text_msg)
                    print(f"DEBUG: Bot response: {res[:50]}...") # Print first 50 chars of response
                    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": TG_ADMIN, "text": f"🔱 {res[:4000]}"})
                else:
                    print(f"DEBUG: Message from unauthorized chat_id {chat_id} ignored.")
        except requests.exceptions.ConnectionError as e:
            print(f"ERROR: Connection to Telegram API failed: {e}. Retrying in 5 seconds.")
            time.sleep(5)
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to decode JSON from Telegram API response: {e}. Retrying in 5 seconds.")
            # If 'r' exists and has a 'text' attribute, print it for debugging
            print(f"Raw response was: {r.text if 'r' in locals() and hasattr(r, 'text') else 'N/A'}")
            time.sleep(5)
        except Exception as e:
            print(f"ERROR: Unhandled exception in polling loop: {e}")
            time.sleep(5)

if __name__ == '__main__':
    print("DEBUG: Starting main script.")
    run()
    print("DEBUG: Main script finished.") # This should not be reached.
