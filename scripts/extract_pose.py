import json
import os
import sys
import cv2
import mediapipe as mp

VIDEO = "/Users/oresajooluwaferanmiidunuoluwa/.gemini/antigravity/brain/5239a2b0-c812-4c95-9ae2-b5507b95f07d/.user_uploaded/media_1795210651827_ac4864ed.mp4"
OUT_JSON = "/Users/oresajooluwaferanmiidunuoluwa/Desktop/PROJECTS/subway-surfer/extracted/characters-3d/pose_mocap.json"
FRAMES_DIR = "/Users/oresajooluwaferanmiidunuoluwa/Desktop/PROJECTS/subway-surfer/extracted/characters-3d/video_frames"
os.makedirs(FRAMES_DIR, exist_ok=True)

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Video: {total} frames @ {fps:.2f} fps")

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

frames_data = []
idx = 0
max_frames = 375  # 15 seconds (before TikTok outro)

while idx < max_frames:
    ok, frame = cap.read()
    if not ok:
        break
    idx += 1
    # Save 1 keyframe per second for visual reference
    if idx % 25 == 1:
        cv2.imwrite(os.path.join(FRAMES_DIR, f"frame_{idx:04d}.jpg"), frame)

    # Crop slightly around center dancer for cleaner tracking
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = pose.process(rgb)

    if res.pose_world_landmarks:
        lms = [
            {
                "x": round(lm.x, 4),
                "y": round(lm.y, 4),
                "z": round(lm.z, 4),
                "v": round(lm.visibility, 3),
            }
            for lm in res.pose_world_landmarks.landmark
        ]
        # Also store hip screen position for root translation
        img_lms = res.pose_landmarks.landmark
        hip_x = (img_lms[23].x + img_lms[24].x) * 0.5
        hip_y = (img_lms[23].y + img_lms[24].y) * 0.5
        frames_data.append({"frame": idx, "hip_screen": [round(hip_x, 4), round(hip_y, 4)], "world": lms})
    else:
        frames_data.append({"frame": idx, "hip_screen": None, "world": None})

cap.release()
pose.close()

valid = sum(1 for f in frames_data if f["world"] is not None)
with open(OUT_JSON, "w") as f:
    json.dump({"fps": fps, "total_frames": len(frames_data), "valid_frames": valid, "frames": frames_data}, f)

print(f"Saved {len(frames_data)} frames ({valid} with 3D pose landmarks) to {OUT_JSON}")
