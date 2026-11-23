"""Reopen both Blender scenes and compare every cached mesh at the six portable poses."""

import argparse
import csv
import io
import json
from pathlib import Path
import sys

import bpy
import numpy as np


def open_scene(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    text = bpy.data.texts["Solver sample times.csv"].as_string()
    return bpy.context.scene, list(csv.DictReader(io.StringIO(text)))


def snapshot(scene, frame, mesh_names):
    scene.frame_set(frame)
    deps = bpy.context.evaluated_depsgraph_get()
    matrices = {
        obj.name: np.array(obj.evaluated_get(deps).matrix_world) for obj in scene.objects
    }
    meshes = {}
    for name in mesh_names:
        mesh = scene.objects[name].evaluated_get(deps).data
        points = np.empty((len(mesh.vertices), 3), dtype=np.float32)
        mesh.vertices.foreach_get("co", points.ravel())
        meshes[name] = (points, len(mesh.polygons))
    return matrices, meshes


def compare(reference, current):
    source_matrices, source_meshes = reference
    matrices, meshes = current
    if matrices.keys() != source_matrices.keys():
        raise ValueError("Scene object sets differ")
    matrix_error = max(
        np.max(np.abs(matrices[name] - matrix)) for name, matrix in source_matrices.items()
    )
    max_mm = 0.0
    vertex_count = 0
    for name, (source_points, source_faces) in source_meshes.items():
        points, faces = meshes[name]
        if faces != source_faces or points.shape != source_points.shape:
            raise ValueError(f"Mesh topology counts differ for {name}")
        if len(points):
            max_mm = max(max_mm, 1000 * float(np.linalg.norm(points - source_points, axis=1).max()))
            vertex_count += len(points)
    if not (matrix_error < 2e-5 and max_mm < 0.01):
        raise ValueError(f"Geometry or transforms differ: {max_mm} mm, matrix error {matrix_error}")
    return {
        "evaluated_vertices": vertex_count,
        "max_local_vertex_error_mm": max_mm,
        "max_world_matrix_error": float(matrix_error),
    }


def check(full_path, portable_path):
    scene, rows = open_scene(full_path)
    names = [obj.name for obj in scene.objects if any(m.type == "MESH_CACHE" for m in obj.modifiers)]
    if not names:
        raise ValueError("Full timeline contains no cached meshes")
    times = np.array([float(row["solver_ms"]) for row in rows])
    references = []
    for target in (0, 20, 40, 60, 100, 140):
        index = int(np.argmin(np.abs(times - target)))
        if abs(times[index] - target) > 0.01:
            raise ValueError(f"Source timeline lacks a sample near {target} ms")
        frame = int(rows[index]["frame"])
        references.append((times[index], snapshot(scene, frame, names)))

    scene, rows = open_scene(portable_path)
    if bpy.utils.blend_paths(absolute=True, packed=False):
        raise ValueError("Portable file depends on an external asset")
    if any(m.type == "MESH_CACHE" for obj in scene.objects for m in obj.modifiers):
        raise ValueError("A portable mesh still uses an external point cache")
    if len(rows) != len(references) or scene.frame_start != 1 or scene.frame_end != len(rows):
        raise ValueError("Portable frame count differs from the requested six poses")
    if any(scene.objects[name].data.shape_keys is None for name in names):
        raise ValueError("A portable deformation mesh has no shape keys")

    records = []
    for pose, (ms, reference) in enumerate(references, 1):
        if float(rows[pose - 1]["solver_ms"]) != ms:
            raise ValueError(f"Solver time differs at pose {pose}")
        differences = compare(reference, snapshot(scene, pose, names))
        records.append({"frame": pose, "solver_ms": float(ms), **differences})
    return {
        "external_assets": 0,
        "shape_key_meshes": len(names),
        "scene_objects": len(scene.objects),
        "file_bytes": portable_path.stat().st_size,
        "compared_frames": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("full", type=Path)
    parser.add_argument("portable", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    report = check(args.full.resolve(), args.portable.resolve())
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
