from django.db import models, transaction
import numpy as np
from django.conf import settings
from gtm_hit.misc import geometry
from gtm_hit.models import Annotation, Annotation2DView, MultiViewFrame, Person, View
from django.core.exceptions import ObjectDoesNotExist
from ipdb import set_trace
from django.db.models import Count
from tqdm import tqdm
import os
import json
import time

def find_closest_annotations_to(person:Person, 
                                frame:MultiViewFrame, 
                                bidirectional:bool=True):
    try:
        next_annotation = Annotation.objects.filter(
            person=person, 
            frame__worker_id=frame.worker_id,
            frame__frame_id__gt=frame.frame_id,
            frame__undistorted=settings.UNDISTORTED_FRAMES
            ).order_by('frame__frame_id').first()
        
        last_annotation = Annotation.objects.filter(
            person=person, 
            frame__worker_id=frame.worker_id,
            frame__frame_id__lte=frame.frame_id,
            frame__undistorted=settings.UNDISTORTED_FRAMES
            ).order_by('frame__frame_id').last()
        
        if bidirectional:
            if last_annotation is None or next_annotation is None:
                raise ObjectDoesNotExist
        else:
            if last_annotation is None:
                if next_annotation is None:
                    return ObjectDoesNotExist
                return next_annotation
            return last_annotation
            
    except ObjectDoesNotExist:
        raise ValueError(f"No next annotation found for person {person.person_id} after frame {frame.frame_id}.")

    return last_annotation, next_annotation


@transaction.atomic
def save_2d_views_bulk(annotations, batch_size=1000, annotation2dviews_data=None):
    # Pre-calculate camera calibrations
    camera_calibs = {
        cam_idx: settings.CALIBS[settings.CAMS[cam_idx]]
        for cam_idx in range(settings.NB_CAMS)
    }

    # View creation
    views_to_create = [View(view_id=i) for i in range(settings.NB_CAMS)]
    View.objects.bulk_create(views_to_create, ignore_conflicts=True)
    views = {v.view_id: v for v in View.objects.all()}

    # 2D view processing
    annotation2dviews_to_create = []
    if annotation2dviews_data is None:
    
        for annotation in annotations:
            for cam_idx in range(settings.NB_CAMS):
                cuboid = geometry.get_cuboid2d_from_annotation(
                    annotation,
                    settings.CAMS[cam_idx],
                    settings.UNDISTORTED_FRAMES,
                )
                p1, p2 = ([-1, -1], [-1, -1]) if cuboid is None else geometry.get_bounding_box(cuboid)
                annotation2dview = Annotation2DView(
                    view=views[cam_idx],
                    annotation=annotation,
                    x1=p1[0], y1=p1[1],
                    x2=p2[0], y2=p2[1]
                )
                if cuboid is not None:
                    annotation2dview.set_cuboid_points_2d(cuboid)
                annotation2dviews_to_create.append(annotation2dview)

            # Bulk create when batch size reached
            if len(annotation2dviews_to_create) >= batch_size:
                Annotation2DView.objects.bulk_create(
                    annotation2dviews_to_create,
                    update_conflicts=True,
                    unique_fields=['view', 'annotation'],
                    update_fields=['x1', 'y1', 'x2', 'y2', 'cuboid_points']
                )
                annotation2dviews_to_create = []

    else:
        for annotation in annotations:
            ann_data_2d = annotation2dviews_data[annotation.person.person_id]
            for datapoint in ann_data_2d:
                cuboid = datapoint['cuboid']
                annotation2dview = Annotation2DView(
                    view=views[datapoint['cameraID']],
                    annotation=annotation,
                    x1=datapoint['x1'], y1=datapoint['y1'],
                    x2=datapoint['x2'], y2=datapoint['y2']
                )
                if cuboid is not None:
                    annotation2dview.set_cuboid_points_2d(cuboid)
                annotation2dviews_to_create.append(annotation2dview)

    # Final batch creation
    if annotation2dviews_to_create:
        Annotation2DView.objects.bulk_create(
            annotation2dviews_to_create,
            update_conflicts=True,
            unique_fields=['view', 'annotation'],
            update_fields=['x1', 'y1', 'x2', 'y2', 'cuboid_points']
        )



def save_2d_views(annotation):
    for i, cam in enumerate(settings.CAMS):
        try:
            view, _ = View.objects.get_or_create(view_id=i)
            try:
                print(f"Cuboid for annotation {annotation} is {cuboid}")
                cuboid = geometry.get_cuboid2d_from_annotation(
                    annotation, cam, settings.UNDISTORTED_FRAMES)
                p1, p2 = geometry.get_bounding_box(cuboid)
            except Exception as e:
                cuboid = None
                p1 = [-1, -1]
                p2 = [-1, -1]
            # Set the cuboid points for the annotation2dview object
            try:
                annotation2dview = Annotation2DView.objects.get(
                    view=view,
                    annotation=annotation)
            except Annotation2DView.DoesNotExist:
                annotation2dview = Annotation2DView(
                    view=view,
                    annotation=annotation
                )
            # print('CUBOID: ', cuboid)
            annotation2dview.x1 = p1[0]
            annotation2dview.y1 = p1[1]
            annotation2dview.x2 = p2[0]
            annotation2dview.y2 = p2[1]
            if cuboid is not None:
                annotation2dview.set_cuboid_points_2d(cuboid)
            annotation2dview.save()
        except Exception as e:
            print('Exception', e)
            return False

def interpolate_between_annotations(annotation1, annotation2):
    save_2d_views(annotation1) # Save 2D views for the two annotations
    save_2d_views(annotation2)

    # Check if frame_id1 and frame_id2 are integers
    frame_id1 = annotation1.frame.frame_id
    frame_id2 = annotation2.frame.frame_id

    if not isinstance(frame_id1, int) or not isinstance(frame_id2, int):
        raise ValueError("Frame IDs must be integers.")
    num_interpolations = frame_id2 - frame_id1 -1

    for j in range(settings.INCREMENT, num_interpolations + 1,settings.INCREMENT):
        interpolated_frame_id = frame_id1 + j
        interpolated_frame = MultiViewFrame.objects.get_or_create(frame_id=interpolated_frame_id, undistorted=settings.UNDISTORTED_FRAMES, worker_id=annotation1.frame.worker_id, dataset__name=annotation1.frame.dataset.name)[0]

        # Try to get the existing annotation for the given person and frame
        try:
            interpolated_annotation = Annotation.objects.get(person=annotation1.person, frame=interpolated_frame)
        except Annotation.DoesNotExist:
            # If the annotation does not exist, create a new one
            interpolated_annotation = Annotation()
            interpolated_annotation.frame = interpolated_frame
            interpolated_annotation.person = annotation1.person

        interpolated_annotation.rectangle_id = f"interpolated-{annotation1.rectangle_id}-{annotation2.rectangle_id}-{j}"
        interpolated_annotation.creation_method = "interpolated"
        interpolated_annotation.validated = False
        interpolated_annotation.rotation_theta = np.interp(interpolated_frame_id, [frame_id1, frame_id2], [annotation1.rotation_theta, annotation2.rotation_theta])
        interpolated_annotation.Xw = np.interp(interpolated_frame_id, [frame_id1, frame_id2], [annotation1.Xw, annotation2.Xw])
        interpolated_annotation.Yw = np.interp(interpolated_frame_id, [frame_id1, frame_id2], [annotation1.Yw, annotation2.Yw])
        interpolated_annotation.Zw = np.interp(interpolated_frame_id, [frame_id1, frame_id2], [annotation1.Zw, annotation2.Zw])
        interpolated_annotation.object_size_x = np.interp(interpolated_frame_id, [frame_id1, frame_id2], [annotation1.object_size_x, annotation2.object_size_x])
        interpolated_annotation.object_size_y = np.interp(interpolated_frame_id, [frame_id1, frame_id2], [annotation1.object_size_y, annotation2.object_size_y])
        interpolated_annotation.object_size_z = np.interp(interpolated_frame_id, [frame_id1, frame_id2], [annotation1.object_size_z, annotation2.object_size_z])
        #set_trace()
        try:
            interpolated_annotation.save()
        except Exception as e:
            raise (f"Could not save interpolated annotation for person {annotation1.person_id} for frame {interpolated_frame_id}.")
        save_2d_views(interpolated_annotation)
    return f"Interpolated annotations for person {annotation1.person_id} between frames {frame_id1} and {frame_id2} have been created."

def interpolate_until_next_annotation(person,frame):
    annotation1, annotation2 = find_closest_annotations_to(person,frame)
    return interpolate_between_annotations(annotation1,annotation2)

def propagation_filter(arguments,options,frame_id):
    if options["propagate"] == 'future':
        arguments['frame__frame_id__gte'] = frame_id
    elif options["propagate"] == 'past':
        arguments['frame__frame_id__lte'] = frame_id
    else:
        arguments['frame__frame_id'] = frame_id
    return arguments

def get_next_available_id(worker_id,dataset_name):
    max_id = Person.objects.filter(worker_id=worker_id,dataset__name=dataset_name).aggregate(models.Max('person_id'))['person_id__max']
    return max_id + 1 if max_id is not None else 1

def change_annotation_id_propagate(old_id, new_id, frame, options):
    with transaction.atomic():  # Start a transaction to ensure data consistency
        #set_trace()
        try:
            propagation_history_file = f'propagation_history_{frame.worker_id}.json'

            # Load existing history or create new
            if os.path.exists(propagation_history_file):
                with open(propagation_history_file, 'r') as f:
                    propagation_history = json.load(f)
            else:
                propagation_history = {}
            next_id = get_next_available_id(worker_id=frame.worker_id,dataset_name=frame.dataset.name)
            filterargs={'person__person_id': new_id, 'frame__undistorted':settings.UNDISTORTED_FRAMES, 'frame__worker_id':frame.worker_id}
            filterargs = propagation_filter(filterargs,options,frame.frame_id)
            # Find all conflicting future annotations
            annotation_conflicts = Annotation.objects.filter(**filterargs).order_by('frame__frame_id')
            #set_trace()
            if options["conflicts"] == "assign_new":
                #set_trace()
                for conflict in annotation_conflicts:
                    # Update the conflicting annotation's person with the new unique ID
                    person_to_replace = Person.objects.get_or_create(worker_id=frame.worker_id, person_id=next_id, dataset=frame.dataset)[0]

                    # Update the related Annotation object
                    conflict.person = person_to_replace
                    conflict.save()
            elif options["conflicts"] == "delete":
                
                for conflict in annotation_conflicts:
                    conflict.delete()

            # Find all target future annotations
            filterargs["person__person_id"]=old_id
            target_future_annotations = Annotation.objects.filter(**filterargs).order_by('frame__frame_id')

            for annotation in target_future_annotations:
                target_future_person = Person.objects.get_or_create(worker_id=frame.worker_id, person_id=new_id,dataset=frame.dataset)[0]
                # Update the related Annotation object
                annotation.person = target_future_person
                annotation.save()
            
            # Create new propagation entry
            propagation_entry = {
                'dataset': frame.dataset.name,
                'worker': frame.worker_id,
                'old_id': old_id,
                'new_id': new_id,
                'switch_frame': frame.frame_id,
                'options': options
            }

            # Add to history
            if frame.dataset.name not in propagation_history:
                propagation_history[frame.dataset.name] = []
            propagation_history[frame.dataset.name].append(propagation_entry)

            # Save updated history
            with open(propagation_history_file, 'w') as f:
                json.dump(propagation_history, f, indent=4)

            return True
        except Exception as e:
            print(e)
            return False

def get_annotation2dviews_for_frame_and_person(frame:MultiViewFrame, person:Person):
    # Calculate the range of frame_ids for 5 frames before and 5 frames after the given frame
    frame_id = frame.frame_id
    frame_id_start = max(0, frame_id - settings.TIMEWINDOW)
    frame_id_end = min(frame_id + settings.TIMEWINDOW, settings.NUM_FRAMES)

    # Filter the Annotation2DView objects using the calculated frame range and the Person object
    annotation2dviews = Annotation2DView.objects.filter(
        annotation__frame__frame_id__gte=frame_id_start,
        annotation__frame__frame_id__lte=frame_id_end,
        annotation__frame__worker_id=frame.worker_id,
        annotation__person=person,
        annotation__frame__undistorted = settings.UNDISTORTED_FRAMES
    )


    #set_trace()
    camtrackviews = {}
    for annotation2dview in annotation2dviews:
        vid = annotation2dview.view.view_id
        try:
            base_point = annotation2dview.cuboid_points_2d[8]
        except:
            continue
        if vid not in camtrackviews:
            camtrackviews[vid] = []
        camtrackviews[vid].append(
            (annotation2dview.annotation.frame.frame_id, base_point))
    for view_id in camtrackviews:
        camtrackviews[view_id].sort()
    return camtrackviews


def copy_annotation_to_frame(annotation, current_frame):
    new_annotation = Annotation.objects.create(
        frame=current_frame,
        person=annotation.person,
        creation_method=annotation.creation_method,
        validated=annotation.validated,
        rectangle_id=annotation.rectangle_id,
        rotation_theta=annotation.rotation_theta,
        Xw=annotation.Xw,
        Yw=annotation.Yw,
        Zw=annotation.Zw,
        object_size_x=annotation.object_size_x,
        object_size_y=annotation.object_size_y,
        object_size_z=annotation.object_size_z
    )
    new_annotation.save()

    # save_2d_views(new_annotation)
    # Copy 2D annotations for each view
    for annotation_2d_view in annotation.twod_views.all():
        new_annotation_2d_view = Annotation2DView.objects.create(
            view=annotation_2d_view.view,
            annotation=new_annotation,
            x1=annotation_2d_view.x1,
            y1=annotation_2d_view.y1,
            x2=annotation_2d_view.x2,
            y2=annotation_2d_view.y2,
            cuboid_points=annotation_2d_view.cuboid_points
        )
        new_annotation_2d_view.save()

    return True


def remove_people_with_few_annotations(worker_id:str, 
                                       dataset_name:str, 
                                       less_than:int=3, 
                                       only_uncomplete:bool=True):
    
    person_annotation_counts = Person.objects.annotate(annotation_count=Count('annotation'))

    persons_with_few_annotations = person_annotation_counts.filter(annotation_count__lte=less_than, worker_id=worker_id,dataset__name=dataset_name)

    if only_uncomplete:
        persons_with_few_annotations = person_annotation_counts.filter(annotation_count__lte=less_than, worker_id=worker_id,dataset__name=dataset_name,annotation_complete=False)

    person_ids_with_few_annotations = persons_with_few_annotations.values_list('person_id', flat=True)
    annotations_to_delete = Annotation.objects.filter(person__person_id__in=person_ids_with_few_annotations, person__worker_id=worker_id,person__dataset__name=dataset_name)
    
    return annotations_to_delete.delete()