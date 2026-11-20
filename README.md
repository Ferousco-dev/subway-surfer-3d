# Subway Surfers — 3D Character Library & Motion Capture Dance Pipeline

An educational reverse-engineering, 3D asset extraction, and Blender motion-capture project exploring **Subway Surfers** (`com.kiloo.subwaysurf` v3.71.11).

Includes:
- **53 Subway Surfers characters** converted into clean, ready-to-open `.blend` files (`blender/characters/`)
- **Subway Surfers environment & train assets** as `.blend` files (`blender/environment/`)
- **Full animated trio dance scene** (`blender/scenes/subway_trio_dance.blend`) & rendered video (`subway_trio_dance.mp4`) driven by **MediaPipe Holistic** 3D pose estimation + **Wiggle 2** spring physics
- **Reproducible Python & Blender scripts** (`scripts/`)

---

## Repository Structure

```text
.
├── blender/
│   ├── characters/          # 53 individual Subway Surfers characters (.blend)
│   ├── environment/         # Train wagons, city buildings, station pillars (.blend)
│   └── scenes/
│       └── subway_trio_dance.blend  # Full animated Tricky + Jake + Fresh dance scene
├── scripts/
│   ├── extract_pose.py      # MediaPipe Pose 3D landmark extractor
│   ├── extract_holistic.py  # MediaPipe Holistic (body + 21-pt hands) extractor
│   ├── glb_holistic_dance.py# Blender rigging, mocap retargeting, camera & lighting
│   └── export_all_blends.py # Batch GLB -> .blend converter
├── subway_trio_dance.mp4    # Rendered 864x576 @ 25fps H.264 + AAC dance video
└── .gitignore               # Excludes APKs, raw binaries, and intermediate dumps
```

---

## How It Was Built

1. **APK Acquisition & Architecture Analysis**
   - Pulled `com.kiloo.subwaysurf` v3.71.11 (`base.apk` + ARM64 splits) via ADB (excluded from git via `.gitignore`).
   - Analyzed the Unity/IL2CPP structure (`global-metadata.dat` v31, 169 C# assemblies, `SYBO.RunnerCore.*`, `SYBO.Tower`, `SYBO.Analytics`) with **REA**, **JADX**, and **Apktool**.
2. **3D Asset Extraction**
   - Extracted Unity Addressables character & theme bundles and converted them to `.glb` with **AssetRipper**, then batch-converted every character and environment piece into `.blend` files.
3. **Video-to-3D Motion Capture & Blender Pipeline**
   - Extracted 375 frames of 3D body & hand landmarks from reference dance footage using **MediaPipe Holistic**.
   - Rigged Tricky, Jake, and Fresh using their real Unity joint positions (`*_jnt`), deterministic vertex-group skinning, 7-frame Gaussian smoothing, mesh-level foot grounding, **Wiggle 2** physics, 3-point lighting, and dynamic camera work.

---

## Credits & Acknowledgments

- **Subway Surfers** — All game characters, 3D models, textures, and environment assets are the intellectual property of **SYBO Games ApS** and **Kiloo**. This repository is for **educational and non-commercial research purposes only**.
- **Blender** — [blender.org](https://www.blender.org/) (3D rigging, animation, EEVEE rendering)
- **AssetRipper** — [AssetRipper/AssetRipper](https://github.com/AssetRipper/AssetRipper) (Unity Addressables bundle extraction)
- **MediaPipe** — [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe) (3D body & hand pose estimation)
- **Wiggle 2** — [shteeve3d/blender-wiggle-2](https://github.com/shteeve3d/blender-wiggle-2) by Steve Miller (secondary bone spring physics)
- **REA (Reverse Engineer Anything)** — IL2CPP metadata & Android resource analysis
- **UnityPy**, **JADX**, **Apktool**, and **FFmpeg**
