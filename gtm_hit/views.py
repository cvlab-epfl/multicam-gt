"""
GTM Hit Views - Multi-View Annotation System

This module provides Django views for the GTM Hit multi-camera annotation system.
It handles:
- Worker management and state transitions
- Frame navigation and annotation workflows
- 3D-to-2D projection and geometry utilities
- Annotation persistence and database operations
- AJAX endpoints for interactive annotation UI
"""

# Standard library imports
import json
import os
import re
import uuid
from collections import defaultdict

# Third-party imports
import numpy as np
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect, render
from django.template import RequestContext
from django.utils import timezone
from django.templatetags.static import static

# Local app imports
from .models import (
    Worker, ValidationCode, MultiViewFrame, View, Annotation, 
    Annotation2DView, Person, Dataset
)
from gtm_hit.misc import geometry
from gtm_hit.misc.autoalign import auto_align_bbox
from gtm_hit.misc.db import *
from gtm_hit.misc.serializer import *
from gtm_hit.misc.utils import convert_rect_to_dict, request_to_dict, process_action

# =====================
# Worker Management Views
# =====================

def requestID(request):
    """
    Render the worker ID request page and handle worker ID submission.
    Validates worker ID format and redirects to processing initialization if valid.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Rendered requestID page or redirect to processInit.
    """
    context = RequestContext(request).flatten()
    if request.method == "POST":
        if 'wID' in request.POST:
            workerID = request.POST['wID']
            pattern = re.compile("^[A-Z0-9]+$")
            if pattern.match(workerID):
                if 'datasetName' in request.POST:
                    dataset_name = request.POST['datasetName']
                    return redirect(f"/gtm_hit/{dataset_name}/{workerID}/processInit")
    return render(request, 'gtm_hit/requestID.html', context)

def processInit(request, dataset_name, workerID):
    """
    Initialize a worker for a given dataset. If the worker exists and is in reset state, transition to introduction state.
    Args:
        request (HttpRequest): The HTTP request object.
        dataset_name (str): Name of the dataset.
        workerID (str): Worker identifier.
    Returns:
        HttpResponse: Redirect to worker's main page.
    """
    context = RequestContext(request).flatten()
    try:
        w = Worker.objects.get(pk=workerID)
        if w.state == -1:
            w.state = 0
            w.save()
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")
    except Worker.DoesNotExist:
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")

def index(request, workerID, dataset_name):
    """
    Render the index page for a worker and dataset.
    Args:
        request (HttpRequest): The HTTP request object.
        workerID (str): Worker identifier.
        dataset_name (str): Name of the dataset.
    Returns:
        HttpResponse: Rendered index page or redirect.
    """
    
    context = RequestContext(request).flatten()
    try:
        w = Worker.objects.get(pk=workerID)
        if w.state != 0:
            return redirect(f"/gtm_hit/{dataset_name}/{workerID}")
        return render(request, 'gtm_hit/index.html', {'workerID': workerID, **context, 'dset_name': dataset_name})

    except Worker.DoesNotExist:
        
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")

def processIndex(request, workerID, dataset_name):
    """
    Transition worker from introduction to tutorial state if appropriate.
    Args:
        request (HttpRequest): The HTTP request object.
        workerID (str): Worker identifier.
        dataset_name (str): Name of the dataset.
    Returns:
        HttpResponse: Redirect to worker's main page.
    """
    
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk=workerID)
        if w.state == 0:
            w.state = 3
            w.save()
    except Worker.DoesNotExist:
        
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")
    return redirect(f"/gtm_hit/{dataset_name}/{workerID}")

def dispatch(request, dataset_name, workerID):
    """
    Dispatch worker to the correct state page based on their current state.
    Args:
        request (HttpRequest): The HTTP request object.
        dataset_name (str): Name of the dataset.
        workerID (str): Worker identifier.
    Returns:
        HttpResponse: Redirect to the appropriate page for the worker's state.
    """
    
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk=workerID)
        try:
            code = ValidationCode.objects.get(worker_id=w)
            stop = False
            i = 2
            while not stop:
                try:
                    w2 = Worker.objects.get(pk=workerID+str(i))
                    c2 = ValidationCode.objects.get(worker_id=w2)
                    i = i + 1
                except Worker.DoesNotExist:
                    stop = True
                except ValidationCode.DoesNotExist:
                    return redirect(f"/gtm_hit/{dataset_name}/{workerID+str(i)}")
            return redirect(f"/gtm_hit/{dataset_name}/{workerID+str(i)}")
        except ValidationCode.DoesNotExist:
            pass
    except Worker.DoesNotExist:
        w = registerWorker(workerID)
    
    dataset,_ = Dataset.objects.get_or_create(name=dataset_name)

    urlpath = "/gtm_hit/"+dataset_name+"/"+workerID+"/"

    state = w.state

    if state == 0:
        return redirect(urlpath+'index')
    elif state == 1:
        return redirect(urlpath+'frame')
    elif state == 2:
        return redirect(urlpath+'finish')
    elif state == 3:
        return redirect(urlpath+'tuto')
    elif state == -1:
        return redirect(urlpath+'processInit')
    
    return redirect(urlpath+'index')

def frame(request, dataset_name, workerID):
    """
    Render the annotation frame page for a worker and dataset.
    Args:
        request (HttpRequest): The HTTP request object.
        dataset_name (str): Name of the dataset.
        workerID (str): Worker identifier.
    Returns:
        HttpResponse: Rendered frame page or redirect.
    """
    context = RequestContext(request).flatten()

    try:
        w = Worker.objects.get(pk=workerID)
        if w.state != 1:
            return redirect(f"/gtm_hit/{dataset_name}/{workerID}")
        if w.frameNB < 0:
            w.frameNB = settings.STARTFRAME
            w.save()
        frame_number = int(w.frameNB)
        nblabeled = w.frame_labeled
        try:
            dataset,_ = Dataset.objects.get_or_create(name=dataset_name)
        except Dataset.DoesNotExist:
            return HttpResponseNotFound("Dataset not found")

        # frame_strs = {cam:str(settings.FRAMES / cam / f'image_{frame_number}.jpg') for cam in settings.CAMS}
        frame_strs = {
                cam: static(f'gtm_hit/dset/{settings.DSETNAME}/frames/{cam}/image_{frame_number}.jpg')
                for cam in settings.CAMS
            }

        return render(request, 'gtm_hit/frame.html', {
            'dset_name': dataset.name, 
            'frame_number': frame_number,
            'frame_strs': json.dumps(frame_strs),  # Pass as JSON string
            'frame_inc': settings.INCREMENT,
            'workerID': workerID,
            'cams': settings.CAMS,
            'frame_size': settings.FRAME_SIZES,
            'nb_cams': settings.NB_CAMS,
            'nblabeled': nblabeled,
            **context,
            "undistort": settings.UNDISTORTED_FRAMES
        })

    except Worker.DoesNotExist:
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")

def processFrame(request, workerID,dataset_name):
    
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk=workerID)
        if w.state == 1 and w.frame_labeled >= 500:
            w.state = 2
            timelist = w.getTimeList()
            timelist.append(timezone.now().isoformat())
            w.setTimeList(timelist)
            w.save()
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")
    except Worker.DoesNotExist:
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")

def finish(request, workerID,dataset_name):
    
    context = RequestContext(request).flatten()
    try:
        w = Worker.objects.get(pk=workerID)
        if w.state == 2:
            validation_code = generate_code(w)
            startframe = w.frameNB - (w.frame_labeled*5)
            try:
                settings.UNLABELED.remove(startframe)
            except ValueError:
                pass
            return render(request, 'gtm_hit/finish.html', {'workerID': workerID, 'validation_code': validation_code, **context})
    except Worker.DoesNotExist:
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")
    return redirect(f"/gtm_hit/{dataset_name}/{workerID}")

def is_ajax(request):
    """
    Check if the request is an AJAX request.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        bool: True if AJAX, False otherwise.
    """
    """Check if request is an AJAX request."""
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

def get_cuboids_2d(world_point, obj, new=False):
    """
    Generate 2D bounding boxes for all camera views from a 3D world point.
    Args:
        world_point (array-like): 3D world coordinates [x, y, z].
        obj (dict): Object properties including size and rotation.
        new (bool): Unused parameter (kept for compatibility).
    Returns:
        list: List of 2D bounding box dictionaries for each camera.
    """
    rectangles = list()
    rect_id = str(int(world_point[0])) + "_" + str(int(world_point[1])
                                                   ) + "_" + uuid.uuid1().__str__().split("-")[0]

    if "object_size" in obj:
        object_size = obj["object_size"]
    else:
        object_size = [settings.HEIGHT, settings.RADIUS, settings.RADIUS]

    for cam_id in range(settings.NB_CAMS):
        # Check if world point is in the camera FOV
        if geometry.is_visible(world_point, settings.CAMS[cam_id], check_mesh=True):
            calib = settings.CALIBS[settings.CAMS[cam_id]]

            cuboid = geometry.Cuboid(calib, world_point, width = object_size[1], 
                                    length = object_size[2], height = object_size[0])
            cuboid = cuboid.get_cuboid_points_2d(obj.get("rotation_theta", 0))
            p1, p2 = geometry.get_bounding_box(cuboid)
        else:
            cuboid = []
            p1 = [-1, -1]
            p2 = [-1, -1]
        rectangle_as_dict = convert_rect_to_dict(
            (*p1, *p2), cuboid, cam_id, rect_id, world_point, object_size, obj.get("rotation_theta", 0))
        if "person_id" in obj:
            rectangle_as_dict["personID"] = obj["person_id"]
        rectangles.append(rectangle_as_dict)

    return rectangles

def click(request):
    """
    Handle click events for annotation placement. Projects 2D click to 3D world and returns 2D cuboids for all cameras.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with 2D cuboid data or error.
    """
    if is_ajax(request):
        # Extract and validate parameters
        x = int(float(request.POST['x']))
        y = int(float(request.POST['y']))
        frame_id = int(float(request.POST['frameID']))

        worker_id = request.POST['workerID']
        dataset_name = request.POST['datasetName']
        obj = request_to_dict(request)
        cam = request.POST['canv'].replace("canv", "")
        
        if cam in settings.CAMS:
            feet2d_h = np.array([[x], [y]])

            if "autoalign" in request.POST and request.POST['autoalign'] == "true":
                world_point = auto_align_bbox(None, frame_id, settings.POSE_MODEL, settings.MESH, settings.CALIBS, points2d=feet2d_h, camera_id=cam).reshape(-1, 3)
            elif settings.FLAT_GROUND:
                calib = settings.CALIBS[cam]
                K0, R0, T0, dist = calib.K, calib.R, calib.T, calib.dist
                world_point = geometry.reproject_to_world_ground_batched(feet2d_h.T, K0, R0, T0, dist, height=-0.301)
            else:
                world_point = geometry.project_2d_points_to_mesh(
                    feet2d_h, settings.CALIBS[cam], settings.MESH)

            if "person_id" not in obj or obj["person_id"] == "":
                obj["person_id"] = get_next_available_id(worker_id=worker_id,dataset_name=dataset_name)

            rectangles = get_cuboids_2d(world_point[0], obj)
            rect_json = json.dumps(rectangles)
            return HttpResponse(rect_json, content_type="application/json")

def action(request):
    """
    Handle annotation modification actions. Updates 3D annotation and regenerates 2D projections.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with updated 2D cuboid data or error.
    """
    if is_ajax(request):
        try:
            obj = json.loads(request.POST["data"])
            obj = process_action(obj)
            Xw = obj["Xw"]
            Yw = obj["Yw"]
            Zw = obj["Zw"]
            
            world_point = np.array([[Xw], [Yw], [Zw]]).reshape(-1, 3)
            
            if not settings.FLAT_GROUND:
                try:
                    world_point = geometry.move_with_mesh_intersection(world_point)
                except Exception as e:
                    print(f"Warning: Value could not be checked with mesh: {e}")
                    print("Using original value, instead.")

            if world_point is None:
                return HttpResponse("Error")
            
            next_rect = get_cuboids_2d(world_point[0], obj)
            next_rect_json = json.dumps(next_rect)
            return HttpResponse(next_rect_json, content_type="application/json")
        except KeyError:
            return HttpResponse("Error")
    return HttpResponse("Error")

def save(request):
    """
    Save annotation data to the database.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Result of save operation.
    """
    return save_db(request)

def load(request):
    """
    Load annotation data from the database.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with annotation data or error.
    """
    return load_db(request)

def load_previous(request):
    """
    Load the previous frame's annotation data for a worker.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with previous frame annotation data or error.
    """
    if is_ajax(request):
        try:

            frameID = request.POST['ID']
            if not frameID:
                return HttpResponse("No frame ID provided")
            wid = request.POST['workerID']
            current_frame = int(frameID)
            closest = float('inf')
            diff = float('inf')

            for f in os.listdir("./gtm_hit/static/gtm_hit/dset/"+settings.DSETNAME+"/labels/" + wid + "/"):
                if f.endswith(".json"):
                    nb_frame = int((f.split('.')[0]).split('_')[1])
                    if nb_frame < current_frame:
                        if current_frame - nb_frame < diff:
                            diff = current_frame - nb_frame
                            closest = nb_frame
            if closest != float('inf'):
                frame = "0" * (8 - len(str(closest))) + str(closest)
                rect_json = read_save(frame, wid)
                return HttpResponse(rect_json, content_type="application/json")
        except (FileNotFoundError, KeyError):
            return HttpResponse("Error")
    return HttpResponse("Error")

def read_save(frameID, workerID):
    """
    Read saved annotation data from file for a given frame and worker.
    Args:
        frameID (str): Frame identifier.
        workerID (str): Worker identifier.
    Returns:
        str: JSON string of annotation data.
    """
    # 
    filename = "./gtm_hit/static/gtm_hit/dset/"+settings.DSETNAME + \
        "/labels/" + workerID + "/" + workerID + "_" + frameID + '.json'
    with open(filename, 'r') as loadFile:
        annotations = json.load(loadFile)
    return json.dumps(annotations)

def changeframe(request):
    """
    Change the current frame for a worker and update their progress.
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with new frame info or error.
    """
    context = RequestContext(request)
    if is_ajax(request):
        try:
            wID = request.POST['workerID']
            order = request.POST['order']
            frame_number = request.POST['frameID']
            increment = request.POST['incr']

            worker = Worker.objects.get(pk=wID)
            timelist = worker.getTimeList()
            timelist.append(timezone.now().isoformat())
            worker.setTimeList(timelist)
            if order == "next":
                inc = int(increment)
            elif order == "prev":
                inc = -int(increment)
            elif order == 'first':
                inc = 0
            else:
                return HttpResponse(f"Requested frame: {frame_number} doesn't exist")
            
            new_frame_number = min(max(int(frame_number) + inc, 0), settings.NUM_FRAMES - 1)
            if order == 'first':
                new_frame_number = 0
            # frame_strs = {cam:str(settings.FRAMES / f'{cam}' / f'image_{new_frame_number}.jpg') for cam in settings.CAMS}
            frame_strs = {
                            cam: static(f'gtm_hit/dset/{settings.DSETNAME}/frames/{cam}/image_{new_frame_number}.jpg')
                            for cam in settings.CAMS
                        }
            response = {
                'frame': str(new_frame_number),
                'nblabeled': worker.frame_labeled,
                'frame_strs': frame_strs
            }

            worker.frameNB = new_frame_number
            worker.frame_labeled = new_frame_number
            worker.save()

            return HttpResponse(json.dumps(response))

        except KeyError:
            return HttpResponse("Error")
    else:
        return HttpResponse("Error")

def get_rect(closest):
    """
    Get rectangle data for a given rectangle ID across all cameras.
    Args:
        closest (str): Rectangle identifier.
    Returns:
        list: List of rectangle data dictionaries for each camera.
    """
    rects = []
    for i in range(settings.NB_CAMS):
        rdic = {}
        rdic['rectangleID'] = closest
        if closest in settings.RECT[i]:
            a, b, c, d, ratio = settings.RECT[i][closest]
        else:
            a, b, c, d, ratio = 0, 0, 0, 0, 0
        rdic['x1'] = a
        rdic['y1'] = b
        rdic['x2'] = c
        rdic['y2'] = d
        rdic['cameraID'] = i
        rdic['ratio'] = ratio
        rdic['xMid'] = (a + c) // 2
        rects.append(rdic)
    return rects

def registerWorker(workerID):
    """
    Register a new worker and initialize their frame number.
    Args:
        workerID (str): Worker identifier.
    Returns:
        Worker: The created Worker object.
    """
    w = Worker()
    w.workerID = workerID
    w.frameNB = settings.STARTFRAME % settings.NBFRAMES
    settings.STARTFRAME = settings.STARTFRAME + 100*settings.INCREMENT
    w.save()
    return w

def updateWorker(workerID, state):
    """
    Update the state of a worker.
    Args:
        workerID (str): Worker identifier.
        state (int): New state value.
    Returns:
        None
    """
    w = Worker.objects.get(pk=workerID)

def generate_code(worker):
    """
    Generate or retrieve a validation code for a worker.
    Args:
        worker (Worker): Worker object.
    Returns:
        str: Validation code.
    """
    try:
        code = ValidationCode.objects.get(worker_id=worker)
    except ValidationCode.DoesNotExist:
        random_code = int(16777215 * rand.random())
        random_code = "{0:0>8}".format(random_code)
        while(random_code in settings.VALIDATIONCODES):
            random_code = int(16777215 * rand.random())
            random_code = "{0:0>8}".format(random_code)
        settings.VALIDATIONCODES.append(random_code)
        code = ValidationCode()
        code.validationCode = random_code
        code.worker = worker
        code.save()
    return code.validationCode

def tuto(request, workerID,dataset_name):
    """
    Render the tutorial page for a worker.
    Args:
        request (HttpRequest): The HTTP request object.
        workerID (str): Worker identifier.
        dataset_name (str): Name of the dataset.
    Returns:
        HttpResponse: Rendered tutorial page or redirect.
    """
    context = RequestContext(request).flatten()
    
    try:
        w = Worker.objects.get(pk=workerID)
        if w.state != 3:
            return redirect(f"/gtm_hit/{dataset_name}/{workerID}")
        return render(request, 'gtm_hit/tuto.html', {'workerID': workerID, 'dset_name':dataset_name, **context})

    except Worker.DoesNotExist:
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")

def processTuto(request, workerID,dataset_name):
    """
    Process tutorial completion and transition worker to annotation state.
    Args:
        request (HttpRequest): The HTTP request object.
        workerID (str): Worker identifier.
        dataset_name (str): Name of the dataset.
    Returns:
        HttpResponse: Redirect to worker's main page.
    """
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk=workerID)
        if w.state == 3:
            w.state = 1
            timelist = [timezone.now().isoformat()]
            w.setTimeList(timelist)
            w.save()
    except Worker.DoesNotExist:
        return redirect(f"/gtm_hit/{dataset_name}/{workerID}")
    return redirect(f"/gtm_hit/{dataset_name}/{workerID}")

def processFinish(request):
    """
    Handle finish processing for a worker (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Result of finish processing.
    """
    context = RequestContext(request)
    if request.is_ajax():
        try:
            wID = request.POST['workerID']

            w = Worker.objects.get(pk=wID)
            startframe = w.frameNB - w.frame_labeled
            # delete_and_load(startframe)
            return HttpResponse("ok")
        except KeyError:
            return HttpResponse("Error")
    else:
        return HttpResponse("Error")

def delete_and_load(startframe):
    """
    Delete and load frames for annotation (utility function).
    Args:
        startframe (int): Starting frame number.
    Returns:
        None
    """
    toload = settings.LASTLOADED + 10
    # 1. remove frames
    sframe = startframe
    # 2. copy next frames
    for i in range(10):
        rm_frame = "0" * (8 - len(str(sframe))) + str(sframe)
        cp_frame = "0" * (8 - len(str(toload))) + str(toload)
        sframe = sframe + 1
        toload = toload + 1
        for j in range(settings.NB_CAMS):
            command = os.system(
                "rm gtm_hit/static/gtm_hit/frames/" + settings.CAMS[j] + "/" + rm_frame + ".png")
            command = os.system("cp gtm_hit/static/gtm_hit/day_2/annotation_final/" +
                                settings.CAMS[j] + "/begin/" + cp_frame + ".png gtm_hit/static/gtm_hit/frames/" + settings.CAMS[j] + "/")

    settings.LASTLOADED = settings.LASTLOADED + 10

@transaction.atomic
def save_db(request):
    """
    Save annotation data to the database (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Result of save operation.
    """
    if is_ajax(request) and request.method == 'POST':
        try:
            data = json.loads(request.POST['data'])
            frame_id = request.POST['ID']
            worker_id = request.POST['workerID']
            dataset_name = request.POST['datasetName']

            worker, _ = Worker.objects.get_or_create(workerID=worker_id)
            dataset, _ = Dataset.objects.get_or_create(name=dataset_name)
            frame, _ = MultiViewFrame.objects.get_or_create(
                frame_id=frame_id, worker=worker, undistorted=settings.UNDISTORTED_FRAMES, dataset=dataset)

            # Get existing annotations
            existing_annotations = {
                ann.person.person_id: ann 
                for ann in Annotation.objects.filter(frame=frame).select_related('person')
            }

            # Group data by personID since we now have multiple views per person
            data_by_person = {}
            for box_data in data:
                person_id = box_data['personID']
                if person_id not in data_by_person:
                    data_by_person[person_id] = []
                data_by_person[person_id].append(box_data)

            # Create people objects
            people_to_create = [
                Person(person_id=pid, worker=worker, dataset=dataset)
                for pid in data_by_person.keys()
            ]
            Person.objects.bulk_create(people_to_create, ignore_conflicts=True)
            people = {p.person_id: p for p in Person.objects.filter(worker=worker, dataset=dataset)}

            # Track which annotations to create/update/delete
            to_create = []
            to_create_2d = defaultdict(list)
            to_delete_ids = []
            
            # Process each person's data
            for person_id, person_boxes in data_by_person.items():
                # Use first box with 3D data for creating the annotation
                annotation_data = next((box for box in person_boxes if 'Xw' in box and 'Yw' in box and 'Zw' in box), None)
                if not annotation_data:
                    continue
                
                if person_id in existing_annotations:
                    # Update if changed
                    existing = existing_annotations[person_id]
                    if has_changes(existing, annotation_data):
                        to_delete_ids.append(existing.id)
                        to_create.append(create_annotation_obj(annotation_data, people, frame))
                        to_create_2d[person_id].extend(person_boxes)
                    del existing_annotations[person_id]
                else:
                    # Create new
                    to_create.append(create_annotation_obj(annotation_data, people, frame))
                    to_create_2d[person_id].extend(person_boxes)
                
                # Add all boxes for this person to to_create_2d
                

            # Delete remaining old annotations and changed ones
            if to_delete_ids:
                Annotation.objects.filter(id__in=to_delete_ids).delete()
            if existing_annotations:
                Annotation.objects.filter(id__in=[a.id for a in existing_annotations.values()]).delete()

            # Bulk create new/changed annotations
            if to_create:
                Annotation.objects.bulk_create(to_create, batch_size=1000)
                save_2d_views_bulk(Annotation.objects.filter(frame=frame), annotation2dviews_data=to_create_2d)

            return HttpResponse("Saved")

        except KeyError as e:
            print(f"KeyError in save_db: {e}")
            return HttpResponse("Error")
    return HttpResponse("Error")

def has_changes(existing, new_data):
    """
    Compare existing annotation with new data to determine if changes exist.
    Args:
        existing (Annotation): Existing annotation object.
        new_data (dict): New annotation data.
    Returns:
        bool: True if changes exist, False otherwise.
    """
    """Compare existing annotation with new data"""
    return (
        existing.rotation_theta != new_data['rotation_theta'] or
        existing.Xw != new_data['Xw'] or
        existing.Yw != new_data['Yw'] or
        existing.Zw != new_data['Zw'] or
        existing.object_size_x != new_data['object_size'][0] or
        existing.object_size_y != new_data['object_size'][1] or
        existing.object_size_z != new_data['object_size'][2]
    )

def create_annotation_obj(data, people, frame):
    """
    Create a new Annotation object from data.
    Args:
        data (dict): Annotation data.
        people (dict): Mapping of person IDs to Person objects.
        frame (MultiViewFrame): Frame object.
    Returns:
        Annotation: New annotation object.
    """
    """Create new annotation object from data"""
    return Annotation(
        person=people[data['personID']],
        frame=frame,
        rectangle_id=data['rectangleID'],
        rotation_theta=data['rotation_theta'],
        Xw=data['Xw'],
        Yw=data['Yw'],
        Zw=data['Zw'],
        object_size_x=data['object_size'][0],
        object_size_y=data['object_size'][1],
        object_size_z=data['object_size'][2]
    )

def create_annotation_obj_2d(annotation_data, annotation, views):
    """
    Create a new Annotation2DView object from data.
    Args:
        annotation_data (dict): 2D annotation data.
        annotation (Annotation): Annotation object.
        views (dict): Mapping of camera IDs to View objects.
    Returns:
        Annotation2DView: New 2D annotation view object.
    """
    annotation2dview = Annotation2DView(
            view=views[annotation_data['cameraID']],
            annotation=annotation,
            x1=annotation_data['x1'], y1=annotation_data['y1'],
            x2=annotation_data['x2'], y2=annotation_data['y2']
        )
    if annotation_data['cuboid'] is not None:
        annotation2dview.set_cuboid_points_2d(annotation_data['cuboid'])
    return annotation2dview

def load_db(request):
    """
    Load annotation data from the database (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with annotation data or error.
    """
    print("Loading Database")
    if is_ajax(request):
        try:
            frame_id =request.POST['ID']
            if not frame_id:
                return HttpResponse("No frame ID provided")
            frame_id = int(frame_id)
            
            worker_id = request.POST['workerID']
            dataset_name = request.POST['datasetName']
            frame = MultiViewFrame.objects.get(frame_id=frame_id, worker_id=worker_id,undistorted=settings.UNDISTORTED_FRAMES, dataset__name=dataset_name)
            # 
            retjson = []
            camviews = View.objects.all()

            retjson = serialize_frame_annotations(frame)
            def nan_to_none(obj):
                if isinstance(obj, float) and np.isnan(obj):
                    return -1
                return obj
            
            def replace_nan(obj):
                if isinstance(obj, dict):
                    return {k: replace_nan(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [replace_nan(x) for x in obj]
                elif isinstance(obj, float) and np.isnan(obj):
                    return None
                return obj

            retjson = replace_nan(retjson)


            return HttpResponse(json.dumps(retjson, default=nan_to_none), content_type="application/json")


        except (Person.DoesNotExist, MultiViewFrame.DoesNotExist, FileNotFoundError, KeyError):
            return HttpResponse("Error")

    return HttpResponse("Error")

def change_id(request):
    """
    Change the person ID for an annotation and propagate changes (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Result of ID change operation.
    """
    if is_ajax(request):
        try:
            person_id = int(float(request.POST['personID']))
            new_person_id = int(float(request.POST['newPersonID']))
            frame_id = int(float(request.POST['frameID']))
            worker_id = request.POST['workerID']
            dataset_name = request.POST['datasetName']
            change_id_history_file = f'change_id_history_{worker_id}.json'
            split_frame = int(float(request.POST['splitFrame'])) if request.POST.get('splitFrame') else None
            new_person_id = max(Person.objects.all().values_list('person_id', flat=True)) + 1

            frame_id = split_frame if split_frame else frame_id
            # Load existing history or create new
            if os.path.exists(change_id_history_file):
                with open(change_id_history_file, 'r') as f:
                    change_id_history = json.load(f)
            else:
                change_id_history = {}

            frame = MultiViewFrame.objects.get(frame_id=frame_id, worker_id=worker_id,undistorted=settings.UNDISTORTED_FRAMES,dataset__name=dataset_name)

            options = json.loads(request.POST['options'])
            success = change_annotation_id_propagate(person_id, new_person_id, frame, options)

            
            if success:
                change_id_entry = {
                'dataset': frame.dataset.name,
                'worker': worker_id,
                'old_id': person_id,
                'new_id': new_person_id,
                'switch_frame': frame.frame_id,
                'options': options
                }
                # Add to history
                if frame.dataset.name not in change_id_history:
                    change_id_history[frame.dataset.name] = []
                change_id_history[frame.dataset.name].append(change_id_entry)

                # Save updated history
                with open(change_id_history_file, 'w') as f:
                    json.dump(change_id_history, f, indent=4)
                    return HttpResponse(JsonResponse({"message": "ID changed.","options":options}))
            else:
                return HttpResponse("Error")
        except KeyError:
            return HttpResponse("Error")
    return HttpResponse("Error")

def person_action(request):
    """
    Perform actions on a person (mark complete or delete) (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Result of person action.
    """
    
    if is_ajax(request):
        try:
            person_id = int(float(request.POST['personID']))
            worker_id = request.POST['workerID']
            options = json.loads(request.POST['options'])
            dataset_name = request.POST['datasetName']

            person = Person.objects.get(person_id=person_id,worker_id=worker_id,dataset__name=dataset_name)
            #
            try:
                if "mark" in options:
                    person.annotation_complete = options["mark"]
                    person.save()
                    return HttpResponse(JsonResponse({"message": "Person annotation complete."}))
                if "delete" in options:
                    if "delete" in options and options["delete"]:
                        person.delete()
                    return HttpResponse(JsonResponse({"message": "Person deleted."}))
            except Person.DoesNotExist:
                return HttpResponse("Error")
        except KeyError:
            return HttpResponse("Error")
    return HttpResponse("Error")

def tracklet(request):
    """
    Retrieve the tracklet (sequence of 2D views) for a person in a frame (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with tracklet data or error.
    """
    
    if is_ajax(request):
        try:
            person_id = int(float(request.POST['personID']))
            frame_id = int(float(request.POST['frameID']))
            worker_id = request.POST['workerID']
            dataset_name = request.POST['datasetName']
            try:
                frame = MultiViewFrame.objects.get(frame_id=frame_id, worker_id=worker_id,undistorted=settings.UNDISTORTED_FRAMES,dataset__name=dataset_name)
                person = Person.objects.get(person_id=person_id,worker_id=worker_id,dataset__name = dataset_name)
            except ValueError:
                HttpResponse("Error")
            multiview_tracklet = get_annotation2dviews_for_frame_and_person(
                frame, person)
            #
            return HttpResponse(json.dumps(multiview_tracklet), content_type="application/json")
        except Exception as e:
            print('Error', e)
            return HttpResponse("Error")

def interpolate(request):
    """
    Interpolate annotations for a person between frames (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Result of interpolation or error.
    """
    if is_ajax(request):
        return HttpResponse("Interpolation disabled for now", status=500)
        return HttpResponse(json.dumps({"message":message}), content_type="application/json")
        # print(request.POST)
        try:
            #
            person_id = int(float(request.POST['personID']))
            frame_id = int(float(request.POST['frameID']))
            worker_id = request.POST['workerID']
            dataset_name = request.POST['datasetName']
            #
            try:
                frame = MultiViewFrame.objects.get(frame_id=frame_id, worker_id=worker_id,undistorted=settings.UNDISTORTED_FRAMES,dataset__name=dataset_name)
                person = Person.objects.get(person_id=person_id,worker_id=worker_id, dataset__name=dataset_name)
                message = interpolate_until_next_annotation(frame=frame, person=person)
            except ValueError:
                message = "Error while interpolating "
                return HttpResponse("Error", status=500)
            return HttpResponse(json.dumps({"message":message}), content_type="application/json")
        except KeyError:
            return HttpResponse("Error")

def cp_prev_or_next_annotation(request):
    """
    Copy annotation from previous or next frame for a person (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Result of copy operation or error.
    """
    #set_trace()
    if is_ajax(request):
        try:
            print("Copying over person")
            person_id = int(float(request.POST['personID']))
            frame_id = int(float(request.POST['frameID']))
            worker_id = request.POST['workerID']
            dataset_name = request.POST['datasetName']
            try:
                frame = MultiViewFrame.objects.get(frame_id=frame_id, worker_id=worker_id,undistorted=settings.UNDISTORTED_FRAMES,dataset__name=dataset_name)
                person = Person.objects.get(person_id=person_id,worker_id=worker_id, dataset__name=dataset_name)
                #delete person from current frame
                try:
                    annotation = Annotation.objects.get(person=person,frame=frame)
                    annotation.delete()
                except Annotation.DoesNotExist:
                    pass
                annotation = find_closest_annotations_to(person,frame,bidirectional=False)
                success = copy_annotation_to_frame(annotation, frame)
                if success:
                    return HttpResponse(JsonResponse({"message": "Annotation copied."}))
                else:
                    return HttpResponse("Error", status=500)
            except ValueError:
                HttpResponse("Error", status=500)
        except KeyError:
            return HttpResponse("Error",status=500)
        
def timeview(request):
    """
    Retrieve time window of 2D annotation views for a person (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with timeview data or error.
    """
    if is_ajax(request):
        try:
            worker_id = request.POST['workerID']
            person_id = int(float(request.POST['personID']))
            frame_id = int(float(request.POST['frameID']))
            view_id = int(float(request.POST['viewID']))
            dataset_name = request.POST['datasetName']

            # Get first and last frame for this person
            first_last_frames = Annotation2DView.objects.filter(
                annotation__frame__worker__workerID=worker_id,
                annotation__frame__dataset__name=dataset_name,
                annotation__person__person_id=person_id,
                view__view_id=view_id,
                annotation__frame__undistorted=settings.UNDISTORTED_FRAMES
            ).aggregate(
                first_frame=models.Min('annotation__frame__frame_id'),
                last_frame=models.Max('annotation__frame__frame_id')
            )

            # Get the window frames
            frame_id_start = max(0, frame_id - settings.TIMEWINDOW)
            frame_id_end = min(frame_id + settings.TIMEWINDOW, settings.NUM_FRAMES)

            # Get all frames including first and last
            annotation2dviews = Annotation2DView.objects.filter(
                models.Q(annotation__frame__frame_id__gte=frame_id_start,
                        annotation__frame__frame_id__lte=frame_id_end) |
                models.Q(annotation__frame__frame_id__in=[first_last_frames['first_frame'], 
                                                        first_last_frames['last_frame']]),
                annotation__frame__worker__workerID=worker_id,
                annotation__frame__dataset__name=dataset_name,
                annotation__person__person_id=person_id,
                view__view_id=view_id,
                annotation__frame__undistorted=settings.UNDISTORTED_FRAMES
            ).order_by('annotation__frame__frame_id')

            timeviews = serialize_annotation2dviews(annotation2dviews)
            return HttpResponse(json.dumps(timeviews), content_type="application/json")

        except KeyError:
            return HttpResponse("Error")
   
def reset_ac_flag(request):
    """
    Reset the annotation_complete flag for all persons of a worker and dataset (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Result of reset operation or error.
    """
    set_trace()
    if is_ajax(request):
        try:
            worker_id = request.POST['workerID']
            dataset_name = request.POST['datasetName']
            for person in Person.objects.filter(worker_id=worker_id,dataset__name=dataset_name):
                person.annotation_complete = False
                person.save()
            return HttpResponse(json.dumps({"message":"ok"}), content_type="application/json")
        except KeyError:
            return HttpResponse("Error")

def create_video(request):
    """
    (Disabled) Create a video for a worker and dataset (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: Message indicating functionality is removed.
    """
    print("This Functionality is removed for testing purposes")
    return HttpResponse("This Functionality is removed for testing purposes")

def serve_frame(request):
    """
    Serve a frame image path for a given frame number and camera (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with frame string or error.
    """
    if is_ajax(request):
        # try:
        frame_number = int(float(request.POST['frame_number']))
        camera_name = int(request.POST['camera_name'])

        camera_name = settings.CAMS[camera_name]
        filepath = static(f'gtm_hit/dset/{settings.DSETNAME}/frames/{camera_name}/image_{new_frame_number}.jpg')
        # settings.FRAMES / f'{camera_name}' / f'image_{frame_number}.jpg'
        if filepath.is_file():
            response = {
                'frame_string':filepath 
                }
            return HttpResponse(json.dumps(response))
            
        else:
            print(f"No frame found matching pattern for camera {camera_name} and frame {frame_number}")
            return HttpResponse(f"No frame found matching pattern for camera {camera_name} and frame {frame_number}")
    return HttpResponse("Error")

def merge(request):
    """
    Merge two person tracks into one (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        JsonResponse: Result of merge operation or error.
    """
    if is_ajax(request):
        try:
            with transaction.atomic():
                # Get input data; note that the outlier flag is no longer obtained from the request
                person_id1, person_id2 = map(lambda x: int(float(x)), [request.POST['personID1'], request.POST['personID2']])
                dataset_name = request.POST['datasetName']
                worker_id = request.POST['workerID']
                # Outlier flag defined in settings.py

                print(f"Starting merge process for person IDs {person_id1} and {person_id2}")
                # Retrieve required objects in one go
                worker = Worker.objects.get(workerID=worker_id)
                dataset = Dataset.objects.get(name=dataset_name)
                person1, person2 = Person.objects.filter(
                    person_id__in=[person_id1, person_id2],
                    worker=worker,
                    dataset=dataset
                )

                print(f"Retrieved worker {worker_id} and dataset {dataset_name}")
                # Create a lookup of frames
                frames = {
                    frame.frame_id: frame
                    for frame in MultiViewFrame.objects.filter(
                        frame_id__range=(settings.FRAME_START, settings.FRAME_END),
                        dataset=dataset,
                        worker=worker
                    )
                }
                print(f"Created frame lookup with {len(frames)} frames")

                # Get all annotations for both trajectories and group them by frame id
                annotations = Annotation.objects.filter(
                    person__in=[person1, person2],
                    frame__frame_id__range=(settings.FRAME_START, settings.FRAME_END)
                ).select_related('frame', 'person')

                annotations_by_frame = defaultdict(list)
                for ann in annotations:
                    annotations_by_frame[ann.frame.frame_id].append(ann)
                print(f"Retrieved and grouped {len(annotations)} annotations across {len(annotations_by_frame)} frames")

                # Build a list of frame data with status and computed positions.
                # Only "good" frames (with 2 annotations close enough) and "single" frames are valid.
                frame_data = []
                for frame_number in sorted(annotations_by_frame):
                    frame_anns = annotations_by_frame[frame_number]
                    positions = np.array([[ann.Xw, ann.Yw, ann.Zw] for ann in frame_anns])
                    entry = {'frame_number': frame_number, 'anns': frame_anns}
                    if len(positions) == 2:
                        distance = np.linalg.norm(positions[0] - positions[1])
                        if distance <= settings.MERGE_THRESHOLD:
                            entry['status'] = 'good'
                            entry['pos'] = positions.mean(axis=0)
                        else:
                            entry['status'] = 'bad'
                    elif len(positions) == 1:
                        entry['status'] = 'single'
                        entry['pos'] = positions[0]
                    else:
                        continue
                    frame_data.append(entry)
                print(f"Analyzed frame data: {len(frame_data)} total frames processed")

                # Extract only valid entries (good or single)
                valid_entries = [entry for entry in frame_data if entry['status'] in ['good', 'single']]
                if not valid_entries:
                    return JsonResponse({"message": "No mergeable valid frames found"}, status=400)
                print(f"Found {len(valid_entries)} valid frames for merging")

                # Group valid entries into segments allowing small gaps defined by settings.MAX_OUTLIER_GAP
                segments = []
                current_segment = []
                for entry in valid_entries:
                    if not current_segment:
                        current_segment.append(entry)
                    else:
                        gap = entry['frame_number'] - current_segment[-1]['frame_number'] - settings.INCREMENT
                        if gap < settings.MAX_OUTLIER_GAP:
                            current_segment.append(entry)
                        else:
                            segments.append(current_segment)
                            current_segment = [entry]
                if current_segment:
                    segments.append(current_segment)
                print(f"Grouped valid frames into {len(segments)} segments")

                # Select the longest valid segment (which may be a combination of near segments)
                longest_segment = max(segments, key=lambda seg: len(seg))
                print(f"Selected longest segment with {len(longest_segment)} frames")

                # Compute a baseline (average) position from the selected segment.
                baseline_positions = [e['pos'] for e in longest_segment]
                baseline = np.mean(baseline_positions, axis=0) if baseline_positions else None

                merged_annotations = []
                to_delete_ids = set()

                # Process each frame in the longest segment.
                for entry in longest_segment:
                    frame_number = entry['frame_number']
                    # Mark original annotations for deletion.
                    for ann in entry['anns']:
                        to_delete_ids.add(ann.id)

                    # All frames here are valid, so use the computed position.
                    merged_pos = entry['pos']

                    merged_annotations.append(
                        Annotation(
                            person=person1,
                            frame=frames[frame_number],
                            rectangle_id=uuid.uuid4().hex,
                            rotation_theta=0,
                            Xw=merged_pos[0],
                            Yw=merged_pos[1],
                            Zw=merged_pos[2],
                            object_size_x=1.7,
                            object_size_y=0.6,
                            object_size_z=0.6,
                            creation_method="merged_scout_tracks"
                        )
                    )
                print(f"Created {len(merged_annotations)} new merged annotations")

                # Delete original annotations and bulk create the merged annotations in chunks.
                if to_delete_ids:
                    print(f"Deleting {len(to_delete_ids)} original annotations")
                    Annotation.objects.filter(id__in=to_delete_ids).delete()
                for chunk in range(0, len(merged_annotations), 1000):
                    chunk_size = min(1000, len(merged_annotations) - chunk)
                    print(f"Bulk creating chunk of {chunk_size} annotations")
                    Annotation.objects.bulk_create(
                        merged_annotations[chunk:chunk + 1000],
                        update_conflicts=True,
                        unique_fields=['frame', 'person'],
                        update_fields=[
                            'rectangle_id', 'rotation_theta', 'Xw', 'Yw', 'Zw',
                            'object_size_x', 'object_size_y', 'object_size_z'
                        ]
                    )

                print("Saving 2D views for merged annotations")
                save_2d_views_bulk(Annotation.objects.filter(person=person1))
                
                # Log merge summary
                summary_msg = f"Merge complete for person IDs {person_id1} and {person_id2}: created {len(merged_annotations)} merged annotations;"
                print(summary_msg)

                return JsonResponse({"message": "ok"})

        except Exception as e:
            print("Exception:", e)
            return JsonResponse({"message": "Error", "error": str(e)}, status=500)
    return JsonResponse({"message": "Error"}, status=400)



def auto_align_current(request):
    """
    Auto-align the current annotation using 3D pose and mesh (AJAX endpoint).
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        HttpResponse: JSON with refined 2D cuboid data or error.
    """
    if is_ajax(request):
        try:
            obj = json.loads(request.POST["data"])

            obj = process_action(obj)
            Xw = obj["Xw"]
            Yw = obj["Yw"]
            Zw = obj["Zw"]

            frame_id = int(float(obj['frameID']))

            world_point = np.array([[Xw], [Yw], [Zw]]).reshape(-1, 3)
            print("Auto Align World point:", world_point)

            world_point = auto_align_bbox(world_point, frame_id, settings.POSE_MODEL, settings.MESH, settings.CALIBS)
                    

            if world_point is None:
                return HttpResponse("Error")
            
            print("Refined World point:", world_point)
            next_rect = get_cuboids_2d(world_point, obj)

            next_rect_json = json.dumps(next_rect)
            # 
            return HttpResponse(next_rect_json, content_type="application/json")
        except KeyError:
            return HttpResponse("Error")
    return HttpResponse("Error")