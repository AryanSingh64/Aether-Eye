import os
import time
import threading
import uvicorn
import shutil
import pickle
import face_recognition
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from config import Config
import state
import core.ai as ai
from core.audio import udp_mic_loop, speak
from core.hardware import udp_smoke_loop, control_light_hw
from core.vision import scan_logic

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
def h(): return {"status": "online"}


@app.get("/scan")
def ms(bg: BackgroundTasks):
    bg.add_task(scan_logic, is_auto=False)
    return {"status": "started"}


@app.get("/status")
def st():
    return {
        "sentry": state.sentry_active,
        "auto_light": state.auto_light_active,
        "latest": state.latest_result
    }


@app.api_route("/light/{a}", methods=["GET", "POST"])
def lc(a: str):
    success = control_light_hw(a == "on")
    return {"status": "ok" if success else "err", "light": a}


@app.api_route("/sentry/{action}", methods=["GET", "POST"])
def sentry_control(action: str):
    state.sentry_active = (action == "on")
    return {"status": "activated" if state.sentry_active else "deactivated", "sentry": state.sentry_active}


@app.api_route("/autolight/{action}", methods=["GET", "POST"])
def autolight_control(action: str):
    state.auto_light_active = (action == "on")
    return {"status": "enabled" if state.auto_light_active else "disabled", "auto_light": state.auto_light_active}


# ================== FACES ==================
@app.get("/faces")
def list_faces():
    if not os.path.exists(Config.KNOWN_FACES_DIR):
        os.makedirs(Config.KNOWN_FACES_DIR)
        return []
    people_found = []
    for entry_name in os.listdir(Config.KNOWN_FACES_DIR):
        person_dir = os.path.join(Config.KNOWN_FACES_DIR, entry_name)
        if os.path.isdir(person_dir):
            valid_photos = [f for f in os.listdir(person_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            people_found.append({"name": entry_name, "photos": len(valid_photos)})
    return people_found


@app.post("/faces/{name}")
async def upload_face(name: str, files: list[UploadFile]):
    person_dir = os.path.join(Config.KNOWN_FACES_DIR, name)
    os.makedirs(person_dir, exist_ok=True)
    for file in files:
        file_path = os.path.join(person_dir, f"{int(time.time())}_{file.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    return {"status": "uploaded", "person": name, "count": len(files)}


@app.delete("/faces/{name}")
def delete_face(name: str):
    path = os.path.join(Config.KNOWN_FACES_DIR, name)
    if os.path.exists(path): shutil.rmtree(path)
    return {"status": "deleted", "person": name}


@app.post("/train")
def train_faces():
    print("🧠 Starting Training Process...")
    new_encodings = []
    new_names = []
    if not os.path.exists(Config.KNOWN_FACES_DIR):
        return {"status": "error", "message": "No known_faces folder found"}

    for person_name in os.listdir(Config.KNOWN_FACES_DIR):
        person_dir = os.path.join(Config.KNOWN_FACES_DIR, person_name)
        if not os.path.isdir(person_dir): continue

        print(f"📂 Processing folder: {person_name}")
        for file_name in os.listdir(person_dir):
            if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_path = os.path.join(person_dir, file_name)
                try:
                    img = face_recognition.load_image_file(image_path)
                    encs = face_recognition.face_encodings(img)
                    if len(encs) > 0:
                        new_encodings.append(encs[0])
                        new_names.append(person_name)
                except Exception as e:
                    print(f"  ❌ Error: {e}")

    data = {"encodings": new_encodings, "names": new_names}
    with open(Config.FACE_ENCODINGS_FILE, "wb") as f:
        pickle.dump(data, f)

    ai.load_models()
    unique = len(set(new_names))
    return {"status": "trained", "count": unique, "total_photos": len(new_encodings)}


def sentry_loop():
    while True:
        if state.sentry_active:
            print("🛡️ Sentry Scan")
            scan_logic(is_auto=True)
        time.sleep(10)


if __name__ == "__main__":
    print(f"✅ Starting Aether Eye Server on Port {Config.SERVER_PORT}")
    print(f"📡 WROOM IP: {Config.ESP32_WROOM_IP} | CAM IP: {Config.ESP32_CAM_IP}")

    ai.load_models()

    for t in [sentry_loop, udp_mic_loop, udp_smoke_loop]:
        threading.Thread(target=t, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=Config.SERVER_PORT, log_level="warning")