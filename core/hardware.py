import requests
import socket
import time
import state
from config import Config


def control_light_hw(state_bool):
    url = Config.LIGHT_ON_URL if state_bool else Config.LIGHT_OFF_URL
    print(f"🔌 Sending request to ESP32-CAM: {url}")
    try:
        requests.get(url, timeout=2)
        return True
    except Exception as e:
        print(f"❌ Light Error: {e}")
        return False


def udp_smoke_loop():
    # Lazy import to prevent circular dependency
    from core.audio import speak

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", Config.SMOKE_UDP_PORT))
        print(f"👃 Smoke Listener on {Config.SMOKE_UDP_PORT}")
    except:
        return

    while True:
        try:
            data, _ = sock.recvfrom(1024)
            val = int(data.decode('utf-8').strip())

            current_time = time.time()
            if current_time - state.last_smoke_alert_time > Config.SMOKE_ALERT_COOLDOWN:
                if val > Config.SMOKE_DANGER_THRESHOLD:
                    print(f"🚨 HEAVY SMOKE: {val}")
                    speak("Emergency! Heavy smoke!")
                    state.last_smoke_alert_time = current_time
                elif val > Config.SMOKE_WARN_THRESHOLD:
                    print(f"⚠️ Light Smoke: {val}")
                    speak("Caution. Light smoke.")
                    state.last_smoke_alert_time = current_time
        except:
            time.sleep(1)