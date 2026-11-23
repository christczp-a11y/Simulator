"""Pack six solved cabin poses into a self-contained Blender inspection file."""

import argparse
import csv
import io
from pathlib import Path
import struct
import sys
import tempfile

import bpy
import numpy as np


def source_samples(scene):
    text = bpy.data.texts["Solver sample times.csv"].as_string()
    rows = list(csv.DictReader(io.StringIO(text)))
    times = np.array([float(row["solver_ms"]) for row in rows])
    if len(rows) != scene.frame_end or np.any(np.diff(times) <= 0):
        raise ValueError("Blender timeline and solver sample table disagree")

    targets = (0, 20, 40, 60, 100, 140)
    selected = [rows[int(np.argmin(abs(times - ms)))] for ms in targets]
    if any(abs(float(row["solver_ms"]) - ms) > 0.01 for row, ms in zip(selected, targets)):
        raise ValueError("Timeline lacks the six required solver samples")
    return selected


def retime_actions(frames):
    # Read all source values before replacing the mount, camera, dial or erosion curve.
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        values = [curve.evaluate(frame) for frame in frames]
                        keys = curve.keyframe_points
                        keys.clear()
                        keys.add(len(values))
                        for pose, (key, value) in enumerate(zip(keys, values), 1):
                            key.co = (pose, value)
                            key.interpolation = "CONSTANT"
                        curve.update()


def pack_mesh(obj, cache, rows, source_frame_count):
    if cache != obj.modifiers[0] or cache.cache_format != "PC2" or obj.data.shape_keys:
        raise ValueError(f"Unexpected cache setup on {obj.name}")
    point_count = len(obj.data.vertices)
    expected_header = (b"POINTCACHE2\0", 1, point_count, 1.0, 1.0, source_frame_count)
    with Path(bpy.path.abspath(cache.filepath)).open("rb") as stream:
        if struct.unpack("<12s i i f f i", stream.read(32)) != expected_header:
            raise ValueError(f"Invalid cache on {obj.name}")
        obj.modifiers.remove(cache)
        for pose, row in enumerate(rows, 1):
            source_frame = int(row["frame"])
            stream.seek(32 + (source_frame - 1) * point_count * 12)
            coords = np.frombuffer(stream.read(point_count * 12), dtype="<f4")
            if pose == 1:
                obj.data.vertices.foreach_set("co", coords)
                obj.shape_key_add(name="Rest | solver 0 ms", from_mix=False)
                continue

            key = obj.shape_key_add(name=f"{float(row['solver_ms']):.3f} ms", from_mix=False)
            key.data.foreach_set("co", coords)
            # Only one measured shape is active at each stop.
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=pose - 1)
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=pose)
            if pose < len(rows):
                key.value = 0.0
                key.keyframe_insert(data_path="value", frame=pose + 1)


def pack(output):
    scene = bpy.context.scene
    rows = source_samples(scene)
    scene.frame_set(1)
    retime_actions([int(row["frame"]) for row in rows])
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "CONSTANT"

    baked = 0
    for obj in scene.objects:
        cache = next((mod for mod in obj.modifiers if mod.type == "MESH_CACHE"), None)
        if cache is not None:
            pack_mesh(obj, cache, rows, scene.frame_end)
            baked += 1
    if not baked:
        raise ValueError("The source scene has no point caches")

    scene.frame_start, scene.frame_end = 1, len(rows)
    scene.timeline_markers.clear()
    table = bpy.data.texts["Solver sample times.csv"]
    table.clear()
    table.write("frame,solver_ms,cg_kmh\n")
    for pose, row in enumerate(rows, 1):
        scene.timeline_markers.new(f"{float(row['solver_ms']):.2f} ms", frame=pose)
        table.write(f"{pose},{row['solver_ms']},{row['cg_kmh']}\n")

    note = bpy.data.texts["About this cabin"]
    note.clear()
    note.write(
        "EP02 | Portable cabin inspection\n"
        "CCSA / FHWA. Frames 1–6 hold solver states at approximately 0, 20, 40, 60, 100 and 140 ms.\n"
        "Use the left/right arrow keys to inspect adjacent poses. The five cameras and editable trim are included.\n"
        "Detailed surfaces and fittings follow the v1l solution. The 56 km/h energy drift exceeds the 5% acceptance limit.\n"
    )
    scene["source"] = "Six measured states from the 56 km/h diagnostic timeline; CCSA/FHWA."
    scene.frame_set(2)
    scene.frame_set(1)
    if bpy.utils.blend_paths(absolute=True, packed=False):
        raise ValueError("External assets remain in the portable cabin")

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        temporary_file = Path(folder) / output.name
        bpy.ops.wm.save_as_mainfile(filepath=str(temporary_file), compress=True)
        temporary_file.replace(output)
    print(f"Packed {baked} meshes at {len(rows)} solver poses into {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    output = args.output.resolve()
    if output == Path(bpy.data.filepath).resolve():
        parser.error("Keep the full timeline and portable inspection file at distinct paths")
    pack(output)
