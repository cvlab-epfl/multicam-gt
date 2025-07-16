"""
Spline interpolation and visualization utilities for annotated tracks.

This module provides functions to:
- Load and interpolate 3D annotation tracks using cubic splines
- Visualize tracks and cuboids on video frames
- Draw cuboid edges for annotation visualization
"""

import os
from pathlib import Path
import argparse
import json
import re
from datetime import datetime, timedelta
from typing import Union, List
from collections import defaultdict

import numpy as np
from tqdm import tqdm
import cv2
from django.conf import settings
from scipy.interpolate import CubicSpline
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Circle
from itertools import combinations

from .utils import get_frame_timestamp, return_consensus_cams_and_time, static_path_to_absolute, get_frame
from ..models import Worker, Dataset
    


def load_tracks(dataset, worker, person_ids: List[int], basepath: str = None, frame_timestamps: bool = False) -> List[dict]:
    """
    Load and interpolate tracks for multiple person_ids using cubic splines.
    Args:
        dataset (Dataset): The dataset object.
        worker (Worker): The worker object.
        person_ids (List[int]): List of person IDs to load tracks for.
        basepath (str, optional): Base path for data (unused).
        frame_timestamps (bool, optional): Whether to use frame timestamps.
    Returns:
        List[dict]: List of track dictionaries (one per person_id), or None if not found.
    """
    from django.db.models import Min, Max
    from .geometry import get_projected_points, is_visible
    from ..models import Annotation, Worker, Dataset
    # Prefetch all annotations in one query
    all_annotations = Annotation.objects.filter(
        person__dataset=dataset,
        person__worker=worker,
        person__person_id__in=person_ids
    ).values(
        'person__person_id', 'Xw', 'Yw', 'Zw', 'frame__frame_id',
        'object_size_x', 'object_size_y', 'object_size_z', 'rotation_theta'
    )

    # Group annotations by person_id
    
    grouped = defaultdict(list)
    for row in all_annotations:
        grouped[row['person__person_id']].append(row)

    # Prefetch frame ranges
    frame_bounds = Annotation.objects.filter(
        person__dataset=dataset,
        person__worker=worker,
        person__person_id__in=person_ids
    ).values('person__person_id').annotate(
        frame_min=Min('frame__frame_id'),
        frame_max=Max('frame__frame_id')
    )
    frame_bounds_dict = {row['person__person_id']: row for row in frame_bounds}

    # Process each person_id
    tracks = []
    for person_id in tqdm(person_ids, desc="Generating Interpolated Tracks"):
        view_data = grouped.get(person_id, [])
        if not view_data:
            tracks.append(None)
            continue

        timestamps_and_coords = []
        for row in view_data:
            try:
                ground_point = [row['Xw'], row['Yw'], row['Zw']]
                _, timestamp = return_consensus_cams_and_time(settings.CALIBS, row['frame__frame_id'], ground_point)
                timestamps_and_coords.append([timestamp, *ground_point])
            except Exception as e:
                print(f"Error processing frame {row['frame__frame_id']}: {e}")
                print(ground_point)
                print(return_consensus_cams_and_time(settings.CALIBS, row['frame__frame_id'], ground_point))
                continue

        if len(timestamps_and_coords) < 2:
            tracks.append(None)
            continue

        data = np.array(timestamps_and_coords, dtype=float)
        data = data[np.argsort(data[:, 0])]
        unique_indices = np.concatenate(([True], np.diff(data[:, 0]) > 0))
        data = data[unique_indices]

        if data.shape[0] < 2:
            tracks.append(None)
            continue

        times = data[:, 0]
        coords = data[:, 1:]
        eps = 1e-10
        for i in range(1, len(times)):
            if times[i] <= times[i-1]:
                times[i] = times[i-1] + eps

        try:
            spline_x = CubicSpline(times, coords[:, 0], extrapolate = False)
            spline_y = CubicSpline(times, coords[:, 1], extrapolate = False)
            spline_z = CubicSpline(times, coords[:, 2], extrapolate = False)
            def make_interpolator(sx, sy, sz):
                return lambda t_query: np.stack([
                    sx(t_query), sy(t_query), sz(t_query)
                ], axis=-1)
            
            interpolate = make_interpolator(spline_x, spline_y, spline_z)

            bounds = frame_bounds_dict[person_id]
            sample_row = view_data[0]  # Use first row for object size + rotation
            # print("t_min", times[0], "t_max", times[-1])
            # print("world points start: ", interpolate(times[0]), " end ", interpolate(times[-1]))
            tracks.append({
                'spline_x': spline_x,
                'spline_y': spline_y,
                'spline_z': spline_z,
                'interpolate': interpolate,
                't_min': times[0],
                't_max': times[-1],
                'person_id': person_id,
                'frame_min': bounds['frame_min'],
                'frame_max': bounds['frame_max'],
                'object_size_x': sample_row['object_size_x'],
                'object_size_y': sample_row['object_size_y'],
                'object_size_z': sample_row['object_size_z'],
                'rotation': sample_row['rotation_theta']
            })
        except Exception as e:
            print(f"Error creating spline for person {person_id}: {e}")
            tracks.append(None)

    return tracks



def draw_cuboid_edges(img, projected_pts, color=(0, 255, 0), thickness=2):
    """
    Draw cuboid edges on an image given projected 2D points.
    Args:
        img (np.ndarray): Image to draw on.
        projected_pts (array-like): 2D projected cuboid points (8 corners).
        color (tuple): RGB color for edges.
        thickness (int): Line thickness.
    Returns:
        np.ndarray: Image with cuboid edges drawn.
    """
    # Define edges by indices into the projected 2D point array
    edges = [
        (0, 1), (1, 3), (3, 2), (2, 0),  # top face
        (4, 5), (5, 7), (7, 6), (6, 4),  # bottom face
        (0, 4), (1, 5), (2, 6), (3, 7)   # vertical edges
    ]
    for i, j in edges:
        pt1 = tuple(map(int, projected_pts[i]))
        pt2 = tuple(map(int, projected_pts[j]))
        cv2.line(img, pt1, pt2, color, thickness)
    return img


def visualize_track_on_video(track, camera, output_path="output_track.mp4", fps=10):
    """
    Visualize a 3D track by drawing its cuboid and center on video frames and saving as a video.
    Args:
        track (dict): Track dictionary with interpolation and metadata.
        camera (str): Camera name.
        output_path (str): Path to save the output video.
        fps (int): Frames per second for output video.
    Returns:
        None
    """
    from .geometry import Cuboid
    from .geometry import get_projected_points, is_visible
    frame_range = range(track['frame_min'], track['frame_max'] + 1)
    frame_shape = None
    video_writer = None

    for frame_id in tqdm(frame_range, desc=f"Rendering {camera} track"):
        img = get_frame(frame_id, camera)
        if img is None:
            continue

        world_point = track['interpolate'](get_frame_timestamp(frame_id, camera))
        if world_point is None or not is_visible(world_point, camera):
            continue

        print("world point: ", world_point, " timestamp ", get_frame_timestamp(frame_id, camera))
        calib = settings.CALIBS[camera]

        # --- Draw projected center point ---
        uv = get_projected_points(world_point, calib)[0]
        if uv is None:
            continue
        u, v = map(int, uv)
        img = cv2.circle(img, (u, v), radius=5, color=(0, 0, 255), thickness=-1)

        # --- Create and draw cuboid ---
        cuboid = Cuboid(calib, world_point)
        cuboid_2d = cuboid.get_cuboid_points_2d(theta=0, calib=calib)[:8]  # 8 corners only
        img = draw_cuboid_edges(img, cuboid_2d)

        # --- Initialize video writer ---
        if frame_shape is None:
            h, w = img.shape[:2]
            frame_shape = (w, h)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            video_writer = cv2.VideoWriter(
                str(output_path),
                cv2.VideoWriter_fourcc(*'mp4v'),
                fps,
                frame_shape
            )

        video_writer.write(img)

    if video_writer:
        video_writer.release()
        print(f"Video saved to {output_path}")
    else:
        print("No frames were written.")


