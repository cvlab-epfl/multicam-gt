import os
import django
import re
import json
import argparse

from pathlib import Path
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple
from PIL import Image
from django.db.models import Min, Max

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gtmarker.settings')
django.setup()

from django.conf import settings
from django.db.models import Count
from gtm_hit.models import MultiViewFrame, Worker, Annotation, Person, Dataset, Annotation2DView, View
from gtm_hit.misc.utils import get_valid_cameras, get_valid_timestamp

def generate_projections_for_frame_and_track(track, frame_id, timestamp) -> dict:
    from gtm_hit.misc.interpolation import get_frame_timestamp
    from gtm_hit.misc.geometry import Cuboid
    interpolator = track['interpolate']
    world_coord = interpolator(timestamp)
    valid_cams = get_valid_cameras(settings.CALIBS, frame_id, world_coord)
    return_dict = {}
    
    for camera in valid_cams:
        frame_timestamp = get_frame_timestamp(frame_id, camera)
        frame_world_coord = interpolator(frame_timestamp)
        if np.any(np.isnan(np.array(frame_world_coord))):
            continue
        cuboid = Cuboid(
                    calib = settings.CALIBS[camera], 
                    world_point=frame_world_coord, 
                    width = track['object_size_y'], 
                    length = track['object_size_z'], 
                    height = track['object_size_x'])
        return_dict[camera] = cuboid.get_bbox()

    return return_dict
    

def generate_frame_annotation_for_track(
          track:dict, 
          frame_id:int,
          timestamp_global = None
          ) -> dict:

    interpolator = track['interpolate']

    world_coords = interpolator(timestamp_global)

    if np.isnan(world_coords).any():
        return None

    frame_annotation = {
         "track_id": track['person_id'],
         "cuboid_3d": {
            "Xw": world_coords[0], 
            "Yw": world_coords[1], 
            "Zw": world_coords[2],
            "width": track['object_size_x'], #x
            "length" : track['object_size_y'], #y
            "height" : track['object_size_z'], #z
            "rotation_theta": track['rotation']
            },
            "projections_2d": generate_projections_for_frame_and_track(track, frame_id, timestamp_global)
        }
    
    return frame_annotation

def export(dataset:Dataset, worker:Worker, output:str, sequence:str = 'sequence_01', testing:bool = False):
    """
    Returns dict of annotations:
    2d projections are only shown if visible
    ```
        {
        “sequence_id”: “seq01",
        “total_frames”: 12000, // Assuming 20 mins @ 10 FPS for example
        “frames”: [
            {
            “frame_id”: 0,
            “timestamp_ms”: 0,
            “annotations”: [
                {
                “track_id”: 1,
                        “cuboid_3d”: { // Parameters defining the 3D cuboid
                            “center_x”: 1.2, “center_y”: 0.5, “center_z”: 2.0,
                            “size_x”: 0.8, “size_y”: 0.6, “size_z”: 1.5,
                            “rotation_yaw”: 0.78 // radians
                            // Add other necessary parameters like rotation_pitch, rotation_roll if applicable
                        },
                        “projections_2d”: {
                            "cvlabrpi1": [100, 150, 50, 75], # x1, y1, x2, y2
                            "cvlabrpi1": [200, 180, 60, 80]
                            // ... for all 26 cameras
                        }
                        },
                        // ... other tracks in this frame
                    ]
                    },
                    // ... other frames
                ]
                }
    ```
    Not everything is needed for cuboid the center and height should be enough, for bbox visible flag is not needed only include camera is it’s visible
    For performance it might also be useful to have a a json for trajectory so we can look up trajectory instantly instead of having to go through all the annoation something like:
    {
                “sequence_id”: “seq01”,
                “trajectories”: [
                    {
                    “track_id”: 1,
                    “points_3d”: [ // Array of [x, y, z, frame_id]
                        [1.2, 0.5, 2.0, 0],
                        [1.22, 0.51, 2.0, 1],
                        // ...
                    ]
                    },
                    // ... other tracks
                ]
                }
    """
    from gtm_hit.misc.interpolation import load_tracks

    
    if testing:
        frames = MultiViewFrame.objects.filter(worker=worker, dataset=dataset).order_by('frame_id').values('frame_id')[:300]
    else:
        frames = MultiViewFrame.objects.filter(worker=worker, dataset=dataset).order_by('frame_id').values('frame_id')

    # Get min and max frame IDs in one DB query
    frame_range = frames.aggregate(
        min_frame_id=Min('frame_id'),
        max_frame_id=Max('frame_id')
    )
    max_frame = frame_range['max_frame_id']#max([frame['frame_id'] for frame in frames])
    min_frame = frame_range['min_frame_id']#min([frame['frame_id'] for frame in frames])

    frame_ids = range(min_frame, max_frame + 1)

    # filter out if only ~3 annotations
    # people = Person.objects.filter(worker= worker, dataset = dataset, annotation__frame__frame_id__in=frame_ids).order_by('person_id').distinct().values('person_id')

    people = (
    Person.objects.filter(
                            worker=worker,
                            dataset=dataset,
                            annotation__frame__frame_id__in=frame_ids
                        )
                .annotate(num_annotations=Count('annotation', distinct=True))
                .filter(num_annotations__gt=3)
                .order_by('person_id')
                .distinct()
                .values('person_id')
            )

    # Preload valid tracks once
    people_ids = [p["person_id"] for p in people]
    tracks = load_tracks(dataset, worker, person_ids=people_ids)  # Batched version

    valid_tracks = {
        track['person_id']: track
        for track in tracks
        if track is not None
    }

    for id, track in valid_tracks.items():
        print(f"track {id}: start frame: {track['frame_min']} end frame: {track['frame_max']}")

    from tqdm import tqdm

    def make_frame(frame_id):
        ts = get_valid_timestamp(frame_id, settings.CAMS)[1]
        annotations = []
        for pid, track in valid_tracks.items():
            if track['frame_min'] <= frame_id <= track['frame_max']:
                annotations.append(generate_frame_annotation_for_track(track, frame_id, timestamp_global = ts))
        return {
            "frame_id": frame_id, #TODO adjust output frame id by offset
            "timestamp_ms": ts * 1000,
            "annotations": [annotation for annotation in annotations if annotation is not None]
        }

    frames = list(tqdm(map(make_frame, frame_ids), total=max_frame - min_frame, desc="Compiling frames"))


    return_dict = {
        "sequence_id": sequence,
        "total_frames": int(max_frame - min_frame) + 1,
        "frames": frames
    }
    print("Saving Annotation Dictionary")

    if testing:
        sequence = f"{sequence}_testing"

    dirpath = Path(output) / 'annotations'/ str(sequence)


    dirpath = Path(output) / 'annotations' / str(sequence)
    dirpath.mkdir(parents=True, exist_ok=True)  # Creates the directory and any missing parents

    filepath = dirpath / f"{sequence}_annotations.json"

    with open(filepath, 'w') as f:
            json.dump(return_dict, f)
        




"""
single frame file format
frame_id.json = {cam_name:{id:bbox, ...}, ..., "world_coord":{id:3dpoint, ...}}


"""
def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default='SCOUT')
    parser.add_argument('--worker', type=str, default='SCIPIO')
    parser.add_argument('--output', type=str, default='./dataset', help = 'Root directory of target dataset')
    # parser.add_argument('--output', type=str, required=True, help='Output file path')

    args = parser.parse_args()
    print('Exporting data for dataset: {} and worker: {}'.format(args.dataset, args.worker))
    dataset = Dataset.objects.get(name = args.dataset)
    worker = Worker.objects.get(workerID = args.worker)
    export(dataset, worker, args.output, sequence = 'sequence_01', testing=False)

if __name__ == '__main__':
    main()
