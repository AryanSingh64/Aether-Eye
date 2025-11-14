import pickle
import os
import face_recognition
from ultralytics import YOLO
from vosk import Model
from config import Config

# Global Model Holders
yolo_std = None
yolo_custom = None
vosk_model = None
KNOWN_FACES = {"encodings": [], "names": []}
STD_CLASSES_ID = []


def load_models():
    global yolo_std, yolo_custom, vosk_model, KNOWN_FACES, STD_CLASSES_ID
    print("⏳ Loading AI Models...")

    # 1. Face Recognition
    try:
        with open(Config.FACE_ENCODINGS_FILE, "rb") as f:
            KNOWN_FACES = pickle.load(f)
        print(f"✅ Loaded {len(KNOWN_FACES['names'])} faces")
    except:
        KNOWN_FACES = {"encodings": [], "names": []}

    # 2. YOLO Standard
    try:
        yolo_std = YOLO(Config.YOLO_STD_PATH)
        STD_CLASSES_ID = [k for k, v in yolo_std.names.items() if v in Config.INDOOR_NAMES or v in Config.HAZARD_LIST]
        print("✅ YOLO Std loaded")
    except Exception as e:
        print(f"❌ YOLO Std failed: {e}")

    # 3. YOLO Custom
    try:
        yolo_custom = YOLO(Config.YOLO_CUSTOM_PATH)
        print("✅ YOLO Custom loaded")
    except:
        yolo_custom = None
        print("⚠️ YOLO Custom not found")

    # 4. Vosk
    try:
        from vosk import SetLogLevel
        SetLogLevel(-1)
        vosk_model = Model(Config.VOSK_MODEL_PATH)
        print("✅ Vosk loaded")
    except:
        vosk_model = None
        print("⚠️ Vosk not found")

    print("✨ READY")