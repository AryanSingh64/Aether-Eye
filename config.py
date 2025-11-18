import os


class Config:
    # ================== NETWORK ==================
    # Your explicit IPs
    ESP32_CAM_IP = "10.239.67.247"
    ESP32_WROOM_IP = "10.239.67.196"

    SERVER_PORT = 5000
    MIC_UDP_PORT = 4444
    SPK_UDP_PORT = 5555
    SMOKE_UDP_PORT = 6666

    # ================== URLS ==================
    CAM_SOURCE = f"http://{ESP32_CAM_IP}:81/stream"
    LIGHT_ON_URL = f"http://{ESP32_CAM_IP}/light/on"
    LIGHT_OFF_URL = f"http://{ESP32_CAM_IP}/light/off"

    # ================== THRESHOLDS ==================
    MASTER_VOLUME_DB = -4.0
    SMOKE_WARN_THRESHOLD = 500
    SMOKE_DANGER_THRESHOLD = 2000
    SMOKE_ALERT_COOLDOWN = 10
    HAZARD_ALERT_COOLDOWN = 10.0

    # Vision logic
    AUTO_LIGHT_ENABLED = True
    LIGHT_THRESHOLD = 60
    LIGHT_SWITCH_COOLDOWN = 2.0
    SCAN_DURATION = 30

    # Image Processing
    BRIGHTNESS_BOOST = True
    BRIGHTNESS_ALPHA = 1.3
    BRIGHTNESS_BETA = 12

    # ================== AI MODELS ==================
    # Paths (calculated relative to this config file)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    KNOWN_FACES_DIR = os.path.join(BASE_DIR, "known_faces")
    FACE_ENCODINGS_FILE = os.path.join(BASE_DIR, "face_encodings.pkl")

    VOSK_MODEL_PATH = "model"
    YOLO_STD_PATH = "yolov8m.pt"
    YOLO_CUSTOM_PATH = "bestv1.pt"

    # Model parameters
    STD_CONF = 0.50
    CUSTOM_CONF = 0.40
    FACE_CONF = 0.6
    FACE_PRIORITY = True
    FACE_REGION_EXPAND = 30
    DOG_CLASS_FILTER = True

    # Tracker
    MIN_FRAMES_STABLE = 2
    SPATIAL_CLUSTERING_DISTANCE = 80
    MAX_TRACK_AGE = 30

    # ================== AUDIO ==================
    EDGE_VOICE = "en-US-JennyNeural"
    SPK_SAMPLE_RATE = 16000
    SPK_CHUNK_SIZE = 1024

    # ================== LISTS ==================
    PERSON_ALIASES = {"person", "man", "woman", "boy", "girl"}
    ANIMAL_CLASSES = {"dog", "cat", "bird", "horse", "sheep", "cow"}
    INDOOR_NAMES = {*PERSON_ALIASES, "chair", "sofa", "couch", "bed", "dining table", "tv", "laptop", "microwave",
                    "sink", "bottle", "cup", "backpack"}
    HAZARD_LIST = {"knife", "scissors", "fire", "smoke", "pistol", "gun", "weapon"}

    # Commands
    SCAN_TRIGGERS = ["scan room", "room scan", "scandal", "start scan", "check room", "look around", "room scan karo",
                     "Hey Aether"]
    LIGHT_ON_TRIGGERS = ["light on", "turn on light", "lights on"]
    LIGHT_OFF_TRIGGERS = ["light off", "turn off light", "lights off"]