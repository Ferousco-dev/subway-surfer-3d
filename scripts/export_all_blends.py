import bpy
import glob
import os

ROOT = "/Users/oresajooluwaferanmiidunuoluwa/Desktop/PROJECTS/subway-surfer"
CHAR_GLB_DIR = os.path.join(ROOT, "hello", "Assets")
ENV_GLB_DIR = os.path.join(ROOT, "second", "Assets", "Mesh")
OUT_CHARS = os.path.join(ROOT, "blender", "characters")
OUT_ENV = os.path.join(ROOT, "blender", "environment")
os.makedirs(OUT_CHARS, exist_ok=True)
os.makedirs(OUT_ENV, exist_ok=True)

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

# 1. Convert every character (avatar_*.glb + matching *_Mesh.glb / *_head.glb) to blender/characters/<name>.blend
avatars = sorted(glob.glob(os.path.join(CHAR_GLB_DIR, "avatar_*.glb")))
all_files_lower = {f.lower(): f for f in os.listdir(CHAR_GLB_DIR)}
converted_chars = 0

for av in avatars:
    cname = os.path.basename(av).removeprefix("avatar_").removesuffix(".glb")
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=av)
    # Also import matching body & head GLBs if present
    for suffix in ("_mesh.glb", "_head.glb"):
        match = all_files_lower.get((cname + suffix).lower())
        if match:
            bpy.ops.import_scene.gltf(filepath=os.path.join(CHAR_GLB_DIR, match))
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            for poly in obj.data.polygons:
                poly.use_smooth = True
    out_path = os.path.join(OUT_CHARS, f"{cname}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    converted_chars += 1

# 2. Convert key environment & train assets to blender/environment/<name>.blend
env_assets = [
    "LavaSpill_cargoWagon_01.glb",
    "LavaSpill_cargoWagon_02.glb",
    "extra_buildingMedFillers_01.glb",
    "extra_buildingMedFillers_02.glb",
    "extra_buildingMedFillers_03.glb",
    "pillars_building_01.glb",
    "pillars_mid.glb",
    "Car_lux_01.glb",
]
converted_env = 0
for ea in env_assets:
    p = os.path.join(ENV_GLB_DIR, ea)
    if not os.path.exists(p):
        continue
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=p)
    out_path = os.path.join(OUT_ENV, ea.removesuffix(".glb") + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    converted_env += 1

print(f"EXPORTED_BLENDS: characters={converted_chars}, environment={converted_env}")
