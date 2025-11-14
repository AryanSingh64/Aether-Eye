import cv2
import time
import numpy as np
import face_recognition
from collections import defaultdict
from datetime import datetime

from config import Config
import state
import core.ai as ai
from core.audio import speak
from core.hardware import control_light_hw


class ObjectTracker:
    def __init__(self):
        self.tracked_objects = {}
        self.face_regions = []

    def set_face_regions(self, face_boxes):
        self.face_regions = face_boxes

    def get_centroid(self, box):
        return int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2)

    def is_in_face_region(self, box):
        if not Config.FACE_PRIORITY or not self.face_regions: return False
        x1, y1, x2, y2 = box
        for fx1, fy1, fx2, fy2 in self.face_regions:
            if not (x2 < (fx1 - Config.FACE_REGION_EXPAND) or x1 > (fx2 + Config.FACE_REGION_EXPAND) or y2 < (
                    fy1 - Config.FACE_REGION_EXPAND) or y1 > (fy2 + Config.FACE_REGION_EXPAND)): return True
        return False

    def update(self, detections_by_class):
        current_detections = defaultdict(list)
        for cls, boxes in detections_by_class.items():
            if Config.DOG_CLASS_FILTER and cls in Config.ANIMAL_CLASSES:
                boxes = [b for b in boxes if not self.is_in_face_region(b)]
            for box in boxes:
                current_detections[cls].append(self.get_centroid(box))

        new_tracked_objects = defaultdict(list)
        # ... (existing tracking logic preserved) ...
        for cls, old_objects in self.tracked_objects.items():
            for old_obj in old_objects:
                matched = False
                if cls in current_detections:
                    for i, new_cent in enumerate(current_detections[cls]):
                        distance = np.linalg.norm(np.array(old_obj["centroid"]) - np.array(new_cent))
                        if distance < Config.SPATIAL_CLUSTERING_DISTANCE:
                            old_obj["centroid"] = new_cent
                            old_obj["count"] += 1
                            old_obj["age"] = 0
                            new_tracked_objects[cls].append(old_obj)
                            current_detections[cls].pop(i)
                            matched = True
                            break
                if not matched:
                    old_obj["age"] += 1
                    if old_obj["age"] < Config.MAX_TRACK_AGE:
                        new_tracked_objects[cls].append(old_obj)
        for cls, new_cents in current_detections.items():
            for cent in new_cents:
                new_tracked_objects[cls].append({"centroid": cent, "count": 1, "age": 0})
        self.tracked_objects = dict(new_tracked_objects)

    def get_stable(self):
        return {k: [o["centroid"] for o in v if o["count"] >= Config.MIN_FRAMES_STABLE] for k, v in
                self.tracked_objects.items()}


def draw_label(frame, label, box, color):
    text_y = max(int(box[1]) - 10, 20)
    cv2.rectangle(frame, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), color, 2)
    (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(frame, (int(box[0]), text_y - h - 5), (int(box[0]) + w, text_y + 5), color, -1)
    cv2.putText(frame, label, (int(box[0]), text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def rec_face(frame, box):
    if not ai.KNOWN_FACES['encodings']: return "Unknown"
    x1, y1, x2, y2 = map(int, box)
    h, w, _ = frame.shape
    person_crop = frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    if person_crop.size == 0: return "Unknown"
    try:
        rgb = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb, model="hog")
        if not face_locations: return "Unknown"
        encodings = face_recognition.face_encodings(rgb, known_face_locations=face_locations)
        if encodings:
            matches = face_recognition.compare_faces(ai.KNOWN_FACES['encodings'], encodings[0],
                                                     tolerance=Config.FACE_CONF)
            if True in matches:
                return ai.KNOWN_FACES['names'][matches.index(True)]
    except:
        pass
    return "Unknown"


def gen_summary(ppl, objs, light, all_hazards=None, full=False):
    k = [p for p in ppl if p != "Unknown"]
    u = ppl.count("Unknown")
    c = {k: len(v) for k, v in objs.items() if v}
    crit_stable = {x for x in c if x in Config.HAZARD_LIST}
    crit_all = all_hazards or set()
    all_critical = crit_stable.union(crit_all)

    p = []
    if all_critical: p.append(f"ALERT! I see {' and '.join(all_critical)}.")
    if u: p.append(f"Warning, {u} unknown person.")

    if full:
        if k: p.append(f"I see {' and '.join(k)}.")
        if c:
            d = [f"{len(v)} {k}{'s' if len(v) > 1 else ''}" for k, v in objs.items() if
                 v and k not in Config.PERSON_ALIASES and k not in all_critical]
            if d: p.append(f"Objects: {', '.join(d[:5])}.")
        if not (all_critical or u or k or c): p.append("Room is empty.")
        p.append(f"Light is {'on' if light else 'off'}.")
    elif not all_critical and u == 0 and [x for x in k if x not in state.prev_memory["people"]]:
        p.append(f"{' and '.join(k)} arrived.")

    state.prev_memory["people"] = k
    return " ".join(p)


def scan_logic(is_auto=False):
    cap = cv2.VideoCapture(Config.CAM_SOURCE)
    if not cap.isOpened():
        print("❌ Cam offline")
        speak("Camera offline.") if not is_auto else None
        return

    print(f"👀 Scanning...")
    tracker = ObjectTracker()
    p_ids = {}
    fc = 0
    start = time.time()
    all_hazards_seen_this_scan = set()

    try:
        while time.time() - start < Config.SCAN_DURATION:
            suc, frame = cap.read()
            if not suc: time.sleep(0.1); continue
            fc += 1

            if Config.BRIGHTNESS_BOOST:
                frame = cv2.convertScaleAbs(frame, alpha=Config.BRIGHTNESS_ALPHA, beta=Config.BRIGHTNESS_BETA)

            # Light Logic
            nl = np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 2]) < Config.LIGHT_THRESHOLD
            if state.auto_light_active and nl != state.esp_l and (
                    time.time() - state.last_l > Config.LIGHT_SWITCH_COOLDOWN):
                control_light_hw(nl)
                state.esp_l, state.last_l = nl, time.time()
            if state.esp_l is None: state.esp_l = nl

            dets = defaultdict(list)
            f_boxes = []

            # Standard Model
            if ai.yolo_std:
                results = ai.yolo_std.track(frame, persist=True, classes=ai.STD_CLASSES_ID, conf=Config.STD_CONF,
                                            verbose=False)
                for b in results[0].boxes:
                    n, box = ai.yolo_std.names[int(b.cls[0])], b.xyxy[0].cpu().numpy().tolist()
                    if n in Config.PERSON_ALIASES and b.id is not None:
                        tid = int(b.id[0])
                        if tid not in p_ids or fc % 15 == 0:
                            pid = rec_face(frame, box)
                            p_ids[tid] = pid
                            if pid != "Unknown": f_boxes.append(box)
                        draw_label(frame, p_ids[tid], box, (0, 255, 0))
                    else:
                        dets[n].append(box)
                        draw_label(frame, n, box, (255, 0, 0))

            # Custom Model
            if ai.yolo_custom:
                results = ai.yolo_custom.track(frame, persist=True, conf=Config.CUSTOM_CONF, verbose=False)
                for b in results[0].boxes:
                    n, box = ai.yolo_custom.names[int(b.cls[0])], b.xyxy[0].cpu().numpy().tolist()
                    dets[n].append(box)
                    draw_label(frame, n, box, (0, 0, 255))

            current_hazards = {k for k in dets if k in Config.HAZARD_LIST}
            if current_hazards:
                all_hazards_seen_this_scan.update(current_hazards)
                if time.time() - state.last_hazard_alert_time > Config.HAZARD_ALERT_COOLDOWN:
                    alert_text = f"ALERT! I see {' and '.join(current_hazards)}."
                    print(f"🚨 {alert_text}")
                    speak(alert_text)
                    state.last_hazard_alert_time = time.time()

            tracker.set_face_regions(f_boxes)
            tracker.update(dets)
            cv2.imshow("AetherEye", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    stable_objects = tracker.get_stable()
    summ = gen_summary(list(set(p_ids.values())), stable_objects, not state.esp_l, all_hazards_seen_this_scan,
                       full=not is_auto)

    if summ:
        state.latest_result = {
            "text": summ,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "light": "on" if not state.esp_l else "off"
        }
        print(f"📝 {summ}")
        speak(summ)