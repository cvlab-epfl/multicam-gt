import os
import django
import numpy as np
import uuid
from pathlib import Path
import pickle
from tqdm import tqdm
import time
import argparse
import json
from typing import List, Tuple, Dict, Union, Optional
from collections import namedtuple
from dataclasses import dataclass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gtmarker.settings')
django.setup()
from gtm_hit.models import MultiViewFrame, Worker, Annotation, Person, Dataset, Annotation2DView, View
from django.conf import settings
from gtm_hit.misc.db import save_2d_views_bulk, save_2d_views
from django.db import transaction
from gtm_hit.misc.geometry import Cuboid, get_cuboid2d_from_annotation


Calibration = namedtuple('Calibration', ['K', 'R', 'T', 'dist', 'view_id'])

def create_dataset_for_worker(tracks_path: Path, 
                          worker_id: str, 
                          dataset_name: str,
                          range_start: int = 0, 
                          range_end: int = 12000, 
                          testing:bool = False,
                          interval:int = 10
                          ):
    
    # Load tracks data
    with open(tracks_path, 'rb') as f:
        tracks_data = json.load(f)

    # Filter frames by interval
    tracks_data['frames'] = [
        frame for frame in tracks_data['frames']
        if frame['frame_id'] % interval == 0
    ]

    # Create worker and dataset
    worker, _ = Worker.objects.get_or_create(workerID=worker_id)
    dataset, _ = Dataset.objects.get_or_create(name=dataset_name)

    if testing:
        tracks_data['frames'] = tracks_data['frames'][:10]
    unique_person_keys = set()
    people_to_create = []

    for frame in tqdm(tracks_data['frames'], desc='creating people'):
        for annotation in frame['annotations']:
            key = (annotation['track_id'], worker.workerID, dataset.name)
            if key not in unique_person_keys:
                unique_person_keys.add(key)
                people_to_create.append(
                    Person(person_id=annotation['track_id'], worker=worker, dataset=dataset)
                )


    unique_frame_keys = set()
    frames_to_create = []

    for frame in tqdm(tracks_data['frames'], desc='generating frames'):
        key = (frame['frame_id'], worker.workerID, dataset.name)
        if key not in unique_frame_keys:
            unique_frame_keys.add(key)
            frames_to_create.append(
                MultiViewFrame(
                    frame_id=frame['frame_id'],
                    worker=worker,
                    undistorted=settings.UNDISTORTED_FRAMES,
                    dataset=dataset
                )
            )

    Person.objects.bulk_create(people_to_create, 
                               update_conflicts=True, 
                               update_fields=['person_id', 'worker', 'dataset'], 
                               unique_fields=['person_id', 'worker', 'dataset'])

    MultiViewFrame.objects.bulk_create(frames_to_create, ignore_conflicts=True)

    frames_dict = {frame.frame_id: frame for frame in 
                MultiViewFrame.objects.filter(
                    worker=worker, 
                    dataset=dataset#,
                    # frame_id__in=list(range(range_start, range_end))
                )}

    people = {p.person_id: p for p in Person.objects.filter(worker=worker, dataset=dataset)}

    views_to_create = [View(view_id=i) for i in range(settings.NB_CAMS)]
    View.objects.bulk_create(views_to_create, ignore_conflicts=True)
    views = {v.view_id: v for v in View.objects.all()}

    # Create all annotations in one go
    all_annotations = []
    for frame in tqdm(tracks_data['frames'], desc='generating 3d annotations'):
        for annotation in frame['annotations']:
            person = people[annotation['track_id']]
            cuboid = annotation['cuboid_3d']
            all_annotations.append(
            Annotation(
                person=person,
                frame=frames_dict[frame['frame_id']],
                rectangle_id=uuid.uuid4().__str__().split("-")[-1],
                rotation_theta=0,
                Xw=cuboid['Xw'],
                Yw=cuboid['Yw'],
                Zw=cuboid['Zw'],
                object_size_x=cuboid['width'],
                object_size_y=cuboid['length'],
                object_size_z=cuboid['height'],
                creation_method="imported_scout_tracks"
            ) )
    

    Annotation.objects.bulk_create(
        all_annotations,
        update_conflicts=True,
        unique_fields=['frame', 'person'],
        update_fields=['rectangle_id', 'rotation_theta', 'Xw', 'Yw', 'Zw', 
                    'object_size_x', 'object_size_y', 'object_size_z', 'creation_method']
    )

    annotations = Annotation.objects.filter(
        frame__worker=worker,
        frame__dataset=dataset
    ).select_related('frame', 'person')  # avoid additional queries

    annotation_lookup = {
        (a.frame.frame_id, a.person.person_id): a
        for a in annotations
    }
    annotations_2d_batch = []
    existing_annotation2d_keys = set()

    for frame in tqdm(tracks_data['frames'], desc="generating 2d annotations"):
        for annotation_dict in frame['annotations']:
            person = people[annotation_dict['track_id']]
            annotation = annotation_lookup[(frame['frame_id'], annotation_dict['track_id'])]
            for cam, bbox in annotation_dict['projections_2d'].items():
                view_id = int(cam.split('_')[1])
                key = (view_id, annotation.id)
                if key not in existing_annotation2d_keys:
                    existing_annotation2d_keys.add(key)
                    x1, y1, x2, y2 = *bbox[0], *bbox[1]
                    new_annotation = Annotation2DView(
                            view=views[settings.CAMS.index(cam)],
                            annotation=annotation,
                            x1=x1, y1=y1,
                            x2=x2, y2=y2
                        )

                    ann_cuboid = get_cuboid2d_from_annotation(
                        annotation,
                        cam,
                        settings.UNDISTORTED_FRAMES,
                    )
                    if ann_cuboid is not None:
                        new_annotation.set_cuboid_points_2d(ann_cuboid)
                    annotations_2d_batch.append(
                        new_annotation
                    )

            if len(annotations_2d_batch) > 1000:

                Annotation2DView.objects.bulk_create(
                    annotations_2d_batch,
                    update_conflicts=True,
                    unique_fields=['view', 'annotation'],
                    update_fields=['x1', 'y1', 'x2', 'y2', 'cuboid_points']
                )
                annotations_2d_batch = []

    # Final flush
    if annotations_2d_batch:
        Annotation2DView.objects.bulk_create(
            annotations_2d_batch,
            update_conflicts=True,
            unique_fields=['view', 'annotation'],
            update_fields=['x1', 'y1', 'x2', 'y2', 'cuboid_points']
        )



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default='SCOUT')
    parser.add_argument('--worker', type=str, default='CVLAB')
    parser.add_argument('--input', type=str, required=True, help = 'Root directory of target dataset json to import')

    args = parser.parse_args()
    print('Creating dataset: {} for worker: {}'.format(args.dataset, args.worker))
    create_dataset_for_worker(args.input, args.worker, args.dataset,   testing=False)

if __name__ == '__main__':
    main()
