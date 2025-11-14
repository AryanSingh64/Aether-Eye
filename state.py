import threading

# Global Flags
sentry_active = False
auto_light_active = True
is_speaking = False

# Locks
speaking_lock = threading.Lock()

# Data Storage
latest_result = {"text": "System ready.", "timestamp": "", "light": "unknown"}
prev_memory = {"people": [], "objects": {}}

# Hardware State
last_smoke_alert_time = 0
last_hazard_alert_time = 0
esp_l = None
last_l = 0