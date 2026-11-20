import bpy
import json
import math
import os
from mathutils import Vector, Quaternion
from mathutils.geometry import intersect_point_line

ASSETS = "/Users/oresajooluwaferanmiidunuoluwa/Desktop/PROJECTS/subway-surfer/hello/Assets"
BASE3D = "/Users/oresajooluwaferanmiidunuoluwa/Desktop/PROJECTS/subway-surfer/extracted/characters-3d"
MOCAP_PATH = os.path.join(BASE3D, "holistic_mocap.json")
AUDIO_PATH = os.path.join(BASE3D, "dance_audio.wav")

with open(MOCAP_PATH, "r") as f:
    mocap = json.load(f)

# Clear default meshes/armatures while keeping the 3D view context
for obj in list(bpy.data.objects):
    if obj.type in ("MESH", "ARMATURE"):
        bpy.data.objects.remove(obj, do_unlink=True)

def mp_to_blender(lm):
    return Vector((lm["x"], lm["z"], -lm["y"]))

def dist_to_segment(p, a, b):
    closest, factor = intersect_point_line(p, a, b)
    if factor < 0.0:
        return (p - a).length
    if factor > 1.0:
        return (p - b).length
    return (p - closest).length

def build_character_from_glb(name, avatar_glb, body_glb, head_glb, tex_path):
    # 1. Read exact Unity joint positions from avatar GLB
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(ASSETS, avatar_glb))
    avatar_objs = list(set(bpy.data.objects) - before)
    bpy.context.view_layer.update()

    jnts = {}
    for o in avatar_objs:
        base_name = o.name.split(".")[0]
        if base_name.endswith("_jnt"):
            jnts[base_name] = o.matrix_world.translation.copy()
    for o in avatar_objs:
        bpy.data.objects.remove(o, do_unlink=True)

    # 2. Import body and head GLBs separately so we know which vertices belong to the head (incl. glasses/hair/cap!)
    def import_single_mesh(glb_name):
        p = os.path.join(ASSETS, glb_name)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=p)
        new_objs = list(set(bpy.data.objects) - before)
        meshes = [o for o in new_objs if o.type == "MESH"]
        for o in new_objs:
            if o.type != "MESH":
                bpy.data.objects.remove(o, do_unlink=True)
        bpy.ops.object.select_all(action="DESELECT")
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        if len(meshes) > 1:
            bpy.ops.object.join()
        return bpy.context.view_layer.objects.active

    body_obj = import_single_mesh(body_glb)
    head_obj = import_single_mesh(head_glb)
    # Include Tricky's iconic red beanie from tricky_outfit_default.glb so her head is complete
    if name == "Tricky" and os.path.exists(os.path.join(ASSETS, "tricky_outfit_default.glb")):
        beanie_obj = import_single_mesh("tricky_outfit_default.glb")
        bpy.ops.object.select_all(action="DESELECT")
        head_obj.select_set(True)
        beanie_obj.select_set(True)
        bpy.context.view_layer.objects.active = head_obj
        bpy.ops.object.join()
        head_obj = bpy.context.view_layer.objects.active
    body_obj.name = f"{name}_Body"
    head_obj.name = f"{name}_Head"

    # Shared texture material + smooth shading
    mat = bpy.data.materials.new(name=f"{name}_Mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if bsdf and os.path.exists(tex_path):
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(tex_path)
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    for obj in (body_obj, head_obj):
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for poly in obj.data.polygons:
            poly.use_smooth = True

    bpy.context.view_layer.update()
    all_pts = [body_obj.matrix_world @ Vector(c) for c in body_obj.bound_box] + \
              [head_obj.matrix_world @ Vector(c) for c in head_obj.bound_box]
    min_x = min(v.x for v in all_pts); max_x = max(v.x for v in all_pts)
    min_z = min(v.z for v in all_pts); max_z = max(v.z for v in all_pts)
    w = max_x - min_x
    h = max_z - min_z

    # Auto-scale avatar joints if they are in meters while the mesh is in centimeters (100x)
    if "Head_jnt" in jnts and jnts["Head_jnt"].z > 1e-4 and jnts["Head_jnt"].z < h * 0.2:
        jnt_scale = (h * 0.72) / jnts["Head_jnt"].z
        for k in list(jnts.keys()):
            jnts[k] = jnts[k] * jnt_scale

    # 3. Build Armature using exact Subway Surfers joint coordinates
    arm_data = bpy.data.armatures.new(f"{name}_Armature")
    arm_obj = bpy.data.objects.new(f"{name}_Rig", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    eb = arm_data.edit_bones
    bone_segs = {}
    def add_bone(bname, head, tail, parent=None, connect=False):
        b = eb.new(bname)
        b.head = Vector(head)
        t = Vector(tail)
        if (t - b.head).length < 1e-3:
            t = b.head + Vector((0, 0, h * 0.05))
        b.tail = t
        if parent:
            b.parent = parent
            b.use_connect = connect
        bone_segs[bname] = (b.head.copy(), b.tail.copy())
        return b

    root_p  = jnts.get("Root_jnt", Vector((0, 0, min_z + h * 0.44)))
    spine_p = jnts.get("LowerSpine_jnt", root_p + Vector((0, 0, h * 0.1)))
    head_p  = jnts.get("Head_jnt", Vector((0, 0, min_z + h * 0.70)))
    l_sh    = jnts.get("L_Shoulder_jnt", Vector((w * 0.16, 0, min_z + h * 0.66)))
    l_el    = jnts.get("L_Elbow_jnt", Vector((w * 0.32, 0, min_z + h * 0.58)))
    l_ha    = jnts.get("L_Hand_jnt", Vector((w * 0.45, 0, min_z + h * 0.50)))
    l_tip   = jnts.get("L_HandTip_jnt", l_ha + (l_ha - l_el).normalized() * (h * 0.08))
    r_sh    = jnts.get("R_Shoulder_jnt", Vector((-w * 0.16, 0, min_z + h * 0.66)))
    r_el    = jnts.get("R_Elbow_jnt", Vector((-w * 0.32, 0, min_z + h * 0.58)))
    r_ha    = jnts.get("R_Hand_jnt", Vector((-w * 0.45, 0, min_z + h * 0.50)))
    r_tip   = jnts.get("R_HandTip_jnt", r_ha + (r_ha - r_el).normalized() * (h * 0.08))
    l_leg   = jnts.get("L_Leg_jnt", Vector((w * 0.09, 0, min_z + h * 0.42)))
    l_knee  = jnts.get("L_Knee_jnt", Vector((w * 0.09, 0, min_z + h * 0.22)))
    l_foot  = jnts.get("L_Foot_jnt", Vector((w * 0.09, 0, min_z + h * 0.04)))
    r_leg   = jnts.get("R_Leg_jnt", Vector((-w * 0.09, 0, min_z + h * 0.42)))
    r_knee  = jnts.get("R_Knee_jnt", Vector((-w * 0.09, 0, min_z + h * 0.22)))
    r_foot  = jnts.get("R_Foot_jnt", Vector((-w * 0.09, 0, min_z + h * 0.04)))

    hips  = add_bone("Hips",       root_p,  spine_p)
    spine = add_bone("Spine",      spine_p, head_p, hips, True)
    head  = add_bone("Head",       head_p,  head_p + Vector((0, 0, h * 0.24)), spine, True)

    ua_l  = add_bone("UpperArm.L", l_sh, l_el, spine)
    la_l  = add_bone("LowerArm.L", l_el, l_ha, ua_l, True)
    ha_l  = add_bone("Hand.L",     l_ha, l_tip, la_l, True)

    ua_r  = add_bone("UpperArm.R", r_sh, r_el, spine)
    la_r  = add_bone("LowerArm.R", r_el, r_ha, ua_r, True)
    ha_r  = add_bone("Hand.R",     r_ha, r_tip, la_r, True)

    ul_l  = add_bone("UpperLeg.L", l_leg,  l_knee, hips)
    ll_l  = add_bone("LowerLeg.L", l_knee, l_foot, ul_l, True)

    ul_r  = add_bone("UpperLeg.R", r_leg,  r_knee, hips)
    ll_r  = add_bone("LowerLeg.R", r_knee, r_foot, ul_r, True)

    rest_dirs = {b.name: (b.tail - b.head).normalized() for b in eb}
    bpy.ops.object.mode_set(mode="OBJECT")

    # 4. Deterministic vertex-group skinning (ZERO floating glasses, ZERO detached heads/arms!)
    # Head mesh (incl. glasses, ears, cap, hair) -> 100% bound to Head bone
    head_obj.parent = arm_obj
    mod_h = head_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod_h.object = arm_obj
    vg_head = head_obj.vertex_groups.new(name="Head")
    vg_head.add(list(range(len(head_obj.data.vertices))), 1.0, "REPLACE")

    # Body mesh -> every vertex bound to nearest bone segment (with smooth top-2 blend)
    body_obj.parent = arm_obj
    mod_b = body_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod_b.object = arm_obj
    vgroups = {bname: body_obj.vertex_groups.new(name=bname) for bname in bone_segs}
    mw = body_obj.matrix_world
    for v in body_obj.data.vertices:
        wp = mw @ v.co
        # Vertices above neck/head_p belong to Head (e.g., Fresh's hair/glasses or Jake's hood)
        if wp.z > head_p.z + h * 0.02:
            vgroups["Head"].add([v.index], 1.0, "REPLACE")
            continue
        # Strict left/right separation so left & right shoes/legs never pull on each other!
        if wp.z < root_p.z - h * 0.03:
            side = ".L" if wp.x >= 0.0 else ".R"
            candidates = [(dist_to_segment(wp, a, b), bn) for bn, (a, b) in bone_segs.items() if bn.endswith(side) and "Leg" in bn]
        else:
            candidates = [
                (dist_to_segment(wp, a, b), bn) for bn, (a, b) in bone_segs.items()
                if not ("Leg" in bn) and not (wp.x >= 0.0 and bn.endswith(".R")) and not (wp.x < 0.0 and bn.endswith(".L"))
            ]
        dists = sorted(candidates, key=lambda x: x[0])
        d0, b0 = dists[0]
        if len(dists) == 1 or d0 < 1e-4 or dists[1][0] > d0 * 1.8:
            vgroups[b0].add([v.index], 1.0, "REPLACE")
        else:
            d1, b1 = dists[1]
            w0 = 1.0 / (d0 + 1e-4)
            w1 = 1.0 / (d1 + 1e-4)
            s = w0 + w1
            vgroups[b0].add([v.index], w0 / s, "REPLACE")
            vgroups[b1].add([v.index], w1 / s, "REPLACE")

    arm_obj.hide_viewport = True
    return arm_obj, body_obj, head_obj, rest_dirs, w, h

tricky_rig, tricky_body, tricky_head, tricky_rest, char_w, char_h = build_character_from_glb(
    "Tricky", "avatar_tricky.glb", "tricky_Mesh.glb", "tricky_head.glb",
    os.path.join(BASE3D, "tricky", "tricky_tex_low.png")
)
jake_rig, jake_body, jake_head, jake_rest, _, _ = build_character_from_glb(
    "Jake", "avatar_jake.glb", "jake_Mesh.glb", "jake_head.glb",
    os.path.join(BASE3D, "jake", "jake_outfit0_tex.png")
)
fresh_rig, fresh_body, fresh_head, fresh_rest, _, _ = build_character_from_glb(
    "Fresh", "avatar_fresh.glb", "fresh_Mesh.glb", "fresh_head.glb",
    os.path.join(BASE3D, "fresh", "fresh_outfit0_tex_low.png")
)

spacing_x = char_w * 1.15
depth_y   = char_h * 0.60

dancers = [
    ("left",   tricky_rig, tricky_body, tricky_head, tricky_rest, -spacing_x, 0),
    ("center", jake_rig,   jake_body,   jake_head,   jake_rest,    0.0,       19),
    ("right",  fresh_rig,  fresh_body,  fresh_head,  fresh_rest,   spacing_x, 37),
]

# Timeline, Real Subway Surfers GLB Environment (Tracks, Buildings, Moving Real Train Wagons), Wiggle 2 & Audio
ENV_GLB = "/Users/oresajooluwaferanmiidunuoluwa/Desktop/PROJECTS/subway-surfer/second/Assets/Mesh"
ENV_TEX = "/Users/oresajooluwaferanmiidunuoluwa/Desktop/PROJECTS/subway-surfer/extracted/env/exported"
env_tex_path = os.path.join(ENV_TEX, "SubwayCityPlantInvasion_environment.png")

env_mat = bpy.data.materials.new(name="SubwayEnv_Mat")
env_mat.use_nodes = True
bsdf_e = env_mat.node_tree.nodes.get("Principled BSDF")
if bsdf_e and os.path.exists(env_tex_path):
    t_node = env_mat.node_tree.nodes.new("ShaderNodeTexImage")
    t_node.image = bpy.data.images.load(env_tex_path)
    env_mat.node_tree.links.new(t_node.outputs["Color"], bsdf_e.inputs["Base Color"])

def place_env_glb(filename, loc, rot_z=0.0, scale=0.4, mat=None, parent=None):
    p = os.path.join(ENV_GLB, filename)
    if not os.path.exists(p):
        return []
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=p)
    objs = list(set(bpy.data.objects) - before)
    for o in objs:
        if o.type == "MESH":
            o.scale = (scale, scale, scale)
            o.rotation_euler = (0.0, 0.0, math.radians(rot_z))
            o.location = loc
            if mat:
                o.data.materials.clear()
                o.data.materials.append(mat)
            if parent:
                o.parent = parent
    return objs

# Grounded platform floor right at Z = 0.0
bpy.ops.mesh.primitive_plane_add(size=char_w * 24, location=(0.0, char_h * 1.5, 0.0))
floor = bpy.context.active_object
floor.name = "SubwayPlatform"
floor_mat = bpy.data.materials.new(name="Platform_Mat")
floor_mat.use_nodes = True
bsdf_f = floor_mat.node_tree.nodes.get("Principled BSDF")
if bsdf_f:
    bsdf_f.inputs["Base Color"].default_value = (0.18, 0.19, 0.22, 1.0)
    bsdf_f.inputs["Roughness"].default_value = 0.75
floor.data.materials.append(floor_mat)

# Keep the entire foreground dance platform 100% flat & clear for all 3 dancers; place city buildings & train cleanly in the background
bg_y = char_h * 4.5
for idx_b, bfile in enumerate(("extra_buildingMedFillers_01.glb", "pillars_building_01.glb", "extra_buildingMedFillers_02.glb", "extra_buildingMedFillers_03.glb")):
    place_env_glb(bfile, ((idx_b - 1.5) * char_w * 6.0, bg_y + char_h * 4.5, 0.0), rot_z=0, scale=0.35, mat=env_mat)

# Real Subway Surfers Train Wagons rushing past on the background track (auto-scaled & always visible!)
train_root = bpy.data.objects.new("SubwayTrain_Root", None)
bpy.context.collection.objects.link(train_root)
for c, wfile in enumerate(("LavaSpill_cargoWagon_01.glb", "LavaSpill_cargoWagon_02.glb", "LavaSpill_cargoWagon_01.glb")):
    objs = place_env_glb(wfile, (c * char_w * 4.5, 0.0, 0.0), rot_z=90, scale=0.8, mat=env_mat, parent=train_root)
    bpy.context.view_layer.update()
    for o in objs:
        if o.type == "MESH":
            bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
            th = max(v.z for v in bb) - min(v.z for v in bb)
            if th > 1e-4:
                s = (char_h * 1.65) / th
                o.scale = (o.scale.x * s, o.scale.y * s, o.scale.z * s)

# Loop the train across the background every 125 frames so it is always visible passing behind them
for cycle_start in (1, 126, 251):
    train_root.location = (-char_w * 6.0, bg_y, 0.0)
    train_root.keyframe_insert(data_path="location", frame=cycle_start)
    train_root.location = (char_w * 6.0, bg_y, 0.0)
    train_root.keyframe_insert(data_path="location", frame=min(cycle_start + 120, 375))

scene = bpy.context.scene
if hasattr(scene, "wiggle"):
    scene.wiggle.enable = True
for _, rig, _, _, _, _, _ in dancers:
    if hasattr(rig.pose, "wiggle_enable"):
        rig.pose.wiggle_enable = True
    for bname in ("Hand.L", "Hand.R"):
        if bname in rig.pose.bones and hasattr(rig.pose.bones[bname], "wiggle_tail"):
            rig.pose.bones[bname].wiggle_tail = True
            rig.pose.bones[bname].wiggle_stiff = 220.0
            rig.pose.bones[bname].wiggle_damp = 4.0

scene.render.fps = 25
scene.frame_start = 1
scene.frame_end = 375
scene.sync_mode = "AUDIO_SYNC"
if os.path.exists(AUDIO_PATH):
    if not scene.sequence_editor:
        scene.sequence_editor_create()
    scene.sequence_editor.strips.new_sound(name="DanceAudio", filepath=AUDIO_PATH, channel=1, frame_start=1)

# 7-frame Gaussian-weighted smoothing for buttery-smooth motion
raw_frames = mocap["frames"]
GAUSS_W = (1, 2, 3, 4, 3, 2, 1)
def smooth_pose(idx):
    acc = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(33)]
    wsum = 0.0
    for offset, gw in zip(range(-3, 4), GAUSS_W):
        k = idx + offset
        if 0 <= k < len(raw_frames) and raw_frames[k].get("pose_world"):
            pw = raw_frames[k]["pose_world"]
            for j in range(33):
                acc[j]["x"] += pw[j]["x"] * gw
                acc[j]["y"] += pw[j]["y"] * gw
                acc[j]["z"] += pw[j]["z"] * gw
            wsum += gw
    if wsum <= 0:
        return None
    return [{"x": a["x"]/wsum, "y": a["y"]/wsum, "z": a["z"]/wsum} for a in acc]

def clamped_quat(q, max_deg):
    axis, angle = q.to_axis_angle()
    lim = math.radians(max_deg)
    if abs(angle) > lim:
        angle = math.copysign(lim, angle)
    return Quaternion(axis, angle)

def apply_pose(arm_obj, char_rest_dirs, pose_lms, frame):
    pb = arm_obj.pose.bones
    pts = [mp_to_blender(l) for l in pose_lms]
    hip_mid = (pts[23] + pts[24]) * 0.5
    sh_mid  = (pts[11] + pts[12]) * 0.5
    ear_mid = (pts[7]  + pts[8])  * 0.5

    # Keep head facing straight forward (never pitching down!), with subtle rhythmic tilt
    t_sec = (frame - 1) / 25.0
    tilt_x = math.sin(t_sec * math.pi * 1.075) * 0.16
    head_vec = Vector((tilt_x, 0.0, 1.0)).normalized()
    # 3D world-space hand vectors from MediaPipe pose (wrist -> index/pinky midpoint)
    l_hand_mid = (pts[19] + pts[17]) * 0.5
    r_hand_mid = (pts[20] + pts[18]) * 0.5

    # Prevent arms & hands from clipping into the torso: keep elbows/wrists outside torso and slightly forward (-Y)
    def keep_arm_clear(vec, is_left):
        v = vec.copy()
        if is_left and v.x < 0.22:
            v.x = 0.22
            v.y = min(v.y, -0.35)
        elif not is_left and v.x > -0.22:
            v.x = -0.22
            v.y = min(v.y, -0.35)
        return v.normalized()

    # Dampen noisy MediaPipe Z-depth on legs so knees bend cleanly without twisting sideways
    def clean_leg(v):
        return Vector((v.x * 0.7, v.y * 0.45, v.z)).normalized()

    targets = {
        "Spine":      (sh_mid - hip_mid).normalized(),
        "Head":       head_vec,
        "UpperArm.L": keep_arm_clear((pts[13] - pts[11]).normalized(), True),
        "LowerArm.L": keep_arm_clear((pts[15] - pts[13]).normalized(), True),
        "Hand.L":     keep_arm_clear((l_hand_mid - pts[15]).normalized(), True),
        "UpperArm.R": keep_arm_clear((pts[14] - pts[12]).normalized(), False),
        "LowerArm.R": keep_arm_clear((pts[16] - pts[14]).normalized(), False),
        "Hand.R":     keep_arm_clear((r_hand_mid - pts[16]).normalized(), False),
        "UpperLeg.L": clean_leg((pts[25] - pts[23]).normalized()),
        "LowerLeg.L": clean_leg((pts[27] - pts[25]).normalized()),
        "UpperLeg.R": clean_leg((pts[26] - pts[24]).normalized()),
        "LowerLeg.R": clean_leg((pts[28] - pts[26]).normalized()),
    }

    max_angles = {
        "Spine": 35, "Head": 35,
        "UpperArm.L": 140, "LowerArm.L": 135, "Hand.L": 50,
        "UpperArm.R": 140, "LowerArm.R": 135, "Hand.R": 50,
        "UpperLeg.L": 70,  "LowerLeg.L": 85,
        "UpperLeg.R": 70,  "LowerLeg.R": 85,
    }

    world_deltas = {"Hips": Quaternion()}
    order = [
        ("Spine", "Hips"),
        ("Head", "Spine"),
        ("UpperArm.L", "Spine"),
        ("LowerArm.L", "UpperArm.L"),
        ("Hand.L", "LowerArm.L"),
        ("UpperArm.R", "Spine"),
        ("LowerArm.R", "UpperArm.R"),
        ("Hand.R", "LowerArm.R"),
        ("UpperLeg.L", "Hips"),
        ("LowerLeg.L", "UpperLeg.L"),
        ("UpperLeg.R", "Hips"),
        ("LowerLeg.R", "UpperLeg.R"),
    ]
    for bname, pname in order:
        if bname not in pb or bname not in targets:
            continue
        p_delta = world_deltas.get(pname, Quaternion())
        rest_q = pb[bname].bone.matrix_local.to_quaternion()
        rest_d = char_rest_dirs[bname]
        targ_d = targets[bname]
        if rest_d.length < 1e-4 or targ_d.length < 1e-4:
            continue
        delta_world = rest_d.rotation_difference(targ_d)
        bone_local_q = rest_q.inverted() @ p_delta.inverted() @ delta_world @ rest_q
        bone_local_q = clamped_quat(bone_local_q, max_angles.get(bname, 90))
        pb[bname].rotation_mode = "QUATERNION"
        pb[bname].rotation_quaternion = bone_local_q
        pb[bname].keyframe_insert(data_path="rotation_quaternion", frame=frame)
        # Recompute actual world delta after clamping
        world_deltas[bname] = p_delta @ rest_q @ bone_local_q @ rest_q.inverted()

for idx in range(0, len(raw_frames), 2):
    item = raw_frames[idx]
    f = item["frame"]
    pose_lms = smooth_pose(idx)
    if not pose_lms:
        continue
    t = (f - 1) / 25.0
    hip_screen = item.get("hip_screen") or [0.5, 0.5]
    bounce_z = max(0.0, (0.58 - hip_screen[1]) * char_h * 0.20)

    for role, rig, body_obj, head_obj, char_rest, base_x, blink_offset in dancers:
        apply_pose(rig, char_rest, pose_lms, f)
        if t < 3.2:
            y = -depth_y * 0.7 if role == "right" else (0.0 if role == "center" else depth_y * 0.7)
            x = base_x; yaw = 0.0
        elif t < 6.5:
            y = -depth_y * 1.2 if role == "center" else depth_y * 0.9
            x = 0.0 if role == "center" else base_x * 1.15; yaw = 0.0
        elif t < 10.5:
            y = 0.0; x = base_x; yaw = 0.0
        else:
            y = depth_y * 0.35 * (-1 if role == "center" else 1)
            x = base_x * 1.1; yaw = math.radians(45)

        # Exact mesh-level ground-lock: evaluate deformed sneaker vertices so the lowest sole touches Z = 0.00!
        rig.location = (x, y, 0.0)
        rig.rotation_euler = (0.0, 0.0, yaw)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        eval_body = body_obj.evaluated_get(depsgraph)
        mw_b = eval_body.matrix_world
        min_mesh_z = min((mw_b @ v.co).z for v in eval_body.data.vertices)
        rig.location = (x, y, -min_mesh_z)
        rig.keyframe_insert(data_path="location", frame=f)
        rig.keyframe_insert(data_path="rotation_euler", frame=f)

# 3-Point Studio Lighting + Subway Surfers Sky World
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.35, 0.62, 0.92, 1.0)
    bg_node.inputs["Strength"].default_value = 0.9

for lname, ltype, energy, loc, rot in [
    ("KeyLight",  "SUN",  3.2, (0, 0, char_h * 4), (math.radians(48), 0, math.radians(-28))),
    ("FillLight", "AREA", 180.0, (-char_w * 3, -char_h * 2.5, char_h * 2.2), (math.radians(65), 0, math.radians(-35))),
    ("RimLight",  "AREA", 240.0, (char_w * 2.5, char_h * 3.0, char_h * 2.5), (math.radians(-125), 0, math.radians(25))),
]:
    ld = bpy.data.lights.new(name=lname, type=ltype)
    ld.energy = energy
    lo = bpy.data.objects.new(name=lname, object_data=ld)
    lo.location = loc
    lo.rotation_euler = rot
    bpy.context.collection.objects.link(lo)

# Cinematic TikTok Camera (9:16 1080x1920) synced to the 4 dance sections
cam_target = bpy.data.objects.new("CameraTarget", None)
cam_target.location = (0.0, 0.0, char_h * 0.52)
bpy.context.collection.objects.link(cam_target)

cam_obj = scene.camera
if not cam_obj:
    cam_data = bpy.data.cameras.new("TikTokCamera")
    cam_obj = bpy.data.objects.new("TikTokCamera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj
cam_obj.data.lens = 32.0
cam_obj.data.clip_end = 5000.0
track = cam_obj.constraints.new(type="TRACK_TO")
track.target = cam_target
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"

# Match real video framing (864x576, 3:2 landscape) so all 3 dancers stay clearly in frame
cam_keyframes = [
    (1,   (0.0,           -char_h * 3.2, char_h * 0.72), (0.0, 0.0,           char_h * 0.52)),
    (75,  (char_w * 0.25, -char_h * 3.1, char_h * 0.70), (0.0, 0.0,           char_h * 0.52)),
    (85,  (0.0,           -char_h * 2.1, char_h * 0.68), (0.0, -depth_y*0.8,  char_h * 0.56)),  # 3-6.5s: Smooth push-in close-up on Jake
    (155, (-char_w * 0.15,-char_h * 2.0, char_h * 0.70), (0.0, -depth_y*0.8,  char_h * 0.56)),
    (170, (0.0,           -char_h * 3.3, char_h * 0.72), (0.0, 0.0,           char_h * 0.52)),  # Wide trio + moving train
    (255, (char_w * 0.3,  -char_h * 3.2, char_h * 0.72), (0.0, 0.0,           char_h * 0.52)),
    (270, (-char_w * 1.1, -char_h * 3.1, char_h * 0.65), (0.0, 0.0,           char_h * 0.52)),  # Side-angle orbit keeping all 3 in frame
    (375, (char_w * 1.2,  -char_h * 3.0, char_h * 0.70), (0.0, 0.0,           char_h * 0.52)),
]
for kf, cloc, tloc in cam_keyframes:
    cam_obj.location = cloc
    cam_obj.keyframe_insert(data_path="location", frame=kf)
    cam_target.location = tloc
    cam_target.keyframe_insert(data_path="location", frame=kf)

# Configure MP4 (H.264 + AAC audio) matching exact original video dimensions (864x576 @ 25fps)
scene.render.resolution_x = 864
scene.render.resolution_y = 576
scene.render.resolution_percentage = 100
scene.render.filepath = os.path.join(BASE3D, "subway_trio_dance.mp4")
try:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.audio_codec = "AAC"
    scene.render.ffmpeg.audio_bitrate = 192
except Exception:
    pass

def start_playback():
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "MATERIAL"
                    space.region_3d.view_perspective = "CAMERA"
    bpy.ops.screen.animation_play()
    return None

bpy.app.timers.register(start_playback, first_interval=0.5)
