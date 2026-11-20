import json
import os
import cv2
import mediapipe as mp

VIDEO = "/Users/oresajooluwaferanmiidunuoluwa/.gemini/antigravity/brain/5239a2b0-c812-4c95-9ae2-b5507b95f07d/.user_uploaded/media_1795210651827_ac4864ed.mp4"
OUT_JSON = "/Users/oresajooluwaferanmiidunuoluwa/Desktop/PROJECTS/subway-surfer/extracted/characters-3d/holistic_mocap.json"

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
max_frames = 375

mp_holistic = mp.solutions.holistic
holistic = mp_holistic.Holistic(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    enable_segmentation=False,
    refine_face_landmarks=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

def pack_lms(lms):
    if not lms:
        return None
    return [{"x": round(l.x, 4), "y": round(l.y, 4), "z": round(l.z, 4)} for l in lms.landmark]

frames = []
idx = 0
while idx < max_frames:
    ok, frame = cap.read()
    if not ok:
        break
    idx += 1
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = holistic.process(rgb)
    hip_screen = None
    if res.pose_landmarks:
        il = res.pose_landmarks.landmark
        hip_screen = [round((il[23].x + il[24].x) * 0.5, 4), round((il[23].y + il[24].y) * 0.5, 4)]
    frames.append({
        "frame": idx,
        "hip_screen": hip_screen,
        "pose_world": pack_lms(res.pose_world_landmarks),
        "left_hand": pack_lms(res.left_hand_landmarks),
        "right_hand": pack_lms(res.right_hand_landmarks),
    })

cap.release()
holistic.close()

pose_n = sum(1 for f in frames if f["pose_world"])
lh_n = sum(1 for f in frames if f["left_hand"])
rh_n = sum(1 for f in frames if f["right_hand"])
with open(OUT_JSON, "w") as f:
    json.dump({"fps": fps, "total_frames": len(frames), "pose_frames": pose_n, "left_hand_frames": lh_n, "right_hand_frames": rh_n, "frames": frames}, f)

print(f"Saved {len(frames)} frames (pose={pose_n}, left_hand={lh_n}, right_hand={rh_n}) to {OUT_JSON}")
