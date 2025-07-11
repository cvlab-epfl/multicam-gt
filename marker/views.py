# -*- coding: utf-8 -*-
from django.shortcuts import get_object_or_404,render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.core import serializers
from django.views import generic
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.template import RequestContext
import re
import json
import os
import zipfile
from io import BytesIO
import numpy as np
from gtm_hit.misc.geometry import project_2d_points_to_mesh#reproject_to_world_ground


def index(request):
    context = RequestContext(request).flatten()
    return render(request, 'marker/index.html',context)

def framenb(request, frame_number):
    context = RequestContext(request).flatten()
    files = list_files()
    return render(request, 'marker/frame.html',{'frame_number': frame_number,'cams': settings.CAMS, 'files':files,**context})

def frame(request):
    context = RequestContext(request).flatten()
    frame_number = 0
    files = list_files()
    return render(request, 'marker/frame.html',{'frame_number': frame_number,'cams': settings.CAMS,'files':files, **context})

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

def list_files():
    worker_p = "./gtm_hit/labels"
    files = os.listdir(worker_p)
    marker_p = "./marker/labels"
    files = files + os.listdir(marker_p)
    return files


def click(request):
    #set_trace()
    print('clicked')
    if is_ajax(request):
        print('clicked')
        # try:
        x = int(float(request.POST['x']))
        y = int(float(request.POST['y']))
        cam = request.POST['canv']
        cam = int(re.findall(r'\d+',cam)[0]) - 1
        if 0 <= cam < settings.NB_CAMS:
            feet2d_h = np.array([[x], [y], [1]])             
            world_point = project_2d_points_to_mesh(
                feet2d_h, settings.CALIBS[cam], settings.MESH)
            # reproject_to_world_ground(feet2d_h, settings.CALIBS[cam].K, settings.CALIBS[cam].R, settings.CALIBS[cam].T)
            print(world_point)
            rectangles = {}#get_rect_calib(world_point)
            rect_json = json.dumps(rectangles)
            return HttpResponse(rect_json, content_type="application/json")

        return HttpResponse("OK")
    
    
# def click(request):
#     if is_ajax(request):
#         try:
#             x = int(request.POST['x'])
#             y = int(request.POST['y'])
#             cam = request.POST['canv']
#             cam = int(re.findall('\d+',cam)[0]) - 1
#             if 0 <= cam < settings.NB_CAMS:
#                 closest = -1
#                 vbest = 1000
#                 for y_temp in range(y - settings.DELTA_SEARCH, y + settings.DELTA_SEARCH):
#                     if 0 <= y_temp < 1080:
#                         for x_temp in settings.FIND_RECT[cam][y_temp]:
#                             vtemp = abs(y - y_temp) + abs(x - x_temp)
#                             if vtemp < vbest:
#                                 vbest, closest = vtemp, settings.FIND_RECT[cam][y_temp][x_temp]
#                 if closest != -1:
#                     rects = get_rect(closest)
#                     rect_json = json.dumps(rects)
#                     return HttpResponse(rect_json,content_type="application/json")

#             return HttpResponse("OK")
#         except KeyError:
#             return HttpResponse("Error")
#     return HttpResponse("No")


def move(request):
    if is_ajax(request):
        try:
            if request.POST['data'] == "down":
                rectID = request.POST['ID']
                if int(rectID) // settings.NB_WIDTH > 0:
                    nextID = int(rectID) - settings.NB_WIDTH
                else:
                    return HttpResponse(json.dumps([]),content_type="application/json")

            elif request.POST['data'] == "up":
                rectID = request.POST['ID']
                if int(rectID) // settings.NB_WIDTH < settings.NB_HEIGHT - 1:
                    nextID = int(rectID) + settings.NB_WIDTH
                else:
                    return HttpResponse(json.dumps([]),content_type="application/json")

            elif request.POST['data'] == "right":
                rectID = request.POST['ID']
                if int(rectID) % settings.NB_WIDTH < settings.NB_WIDTH - 1:
                    nextID = int(rectID) + 1
                else:
                    return HttpResponse(json.dumps([]),content_type="application/json")

            elif request.POST['data'] == "left":
                rectID = request.POST['ID']
                if int(rectID) % settings.NB_WIDTH > 0:
                    nextID = int(rectID) - 1
                else:
                    return HttpResponse(json.dumps([]),content_type="application/json")

            else:
                return HttpResponse("Error")
            next_rect = get_rect(nextID)
            next_rect_json = json.dumps(next_rect)
            return HttpResponse(next_rect_json,content_type="application/json")

        except KeyError:
            return HttpResponse("Error")
    return HttpResponse("Error")

def save(request):
    if is_ajax(request):
        try:
            data = json.loads(request.POST['data'])
            frameID = request.POST['ID']
            annotations = []
            cols = ["rectID","personID","modified","a1","b1","c1","d1","a2","b2","c2","d2","a3","b3","c3","d3","a4","b4","c4","d4","a5","b5","c5","d5","a6","b6","c6","d6","a7","b7","c7","d7"]
            annotations.append(cols)
            for r in data:
                row = data[r]
                row.insert(0,int(r))
                annotations.append(row)
            with open("marker/labels/"+frameID + '.json', 'w') as outFile:
                json.dump(annotations, outFile, sort_keys=True, indent=4, separators=(',', ': '))
            return HttpResponse("Saved")
        except KeyError:
            return HttpResponse("Error")
    else:
        return("Error")

def load(request):
    if is_ajax(request):
        try:
            frameID = request.POST['ID']
            rect_json = read_save(frameID)
            return HttpResponse(rect_json,content_type="application/json")
        except (FileNotFoundError, KeyError):
            return HttpResponse("Error")
    return HttpResponse("Error")

def load_previous(request):
    if is_ajax(request):
        try:
            frameID = request.POST['ID']
            current_frame = int(frameID)
            closest = float('inf')
            diff = float('inf')

            for f in os.listdir("marker/labels/"):
                if f.endswith(".json"):
                    nb_frame = int(f.split('.')[0])

                    if nb_frame < current_frame:
                        if current_frame - nb_frame < diff:
                            diff = current_frame - nb_frame
                            closest = nb_frame
            if closest != float('inf'):
                frame = "0" * (8 - len(str(closest))) + str(closest)
                rect_json = read_save(frame)
                return HttpResponse(rect_json,content_type="application/json")
        except (FileNotFoundError, KeyError):
            return HttpResponse("Error")
    return HttpResponse("Error")

def read_save(frameID, fullpath=False):
    if(fullpath):
        if frameID[0].isdecimal():
            filename = "marker/labels/" + frameID
        else:
            filename = "gtm_hit/labels/" + frameID
    else:
        filename = "marker/labels/"+ frameID + '.json'
    with open(filename,'r') as loadFile:
        annotations = json.load(loadFile)
    rects = []
    for i in annotations[1:]:
        r = get_rect(i[0])
        for j in range(settings.NB_CAMS):
            r[j]['x1'] = i[j*4+3]
            r[j]['y1'] = i[j*4+4]
            r[j]['x2'] = i[j*4+5]
            r[j]['y2'] = i[j*4+6]
        r.append(i[1])
        r.append(i[2])
        rects.append(r)
    return json.dumps(rects)

# def changeframe(request):
#     if is_ajax(request):
#         frame = 0
#         try:
#             order = request.POST['order']
#             frame_number = request.POST['frameID']
#             increment = request.POST['incr']
#             if order == "next":
#                 frame = int(frame_number) + int(increment)
#             elif order == "prev" and (int(frame_number) - int(increment)) >= 0:
#                 frame = int(frame_number) - int(increment)
#             else:
#                 return HttpResponse("Requested frame not existing")
#             frame = "0" * (8 - len(str(frame))) + str(frame)
#             return HttpResponse(json.dumps(frame))
#         except KeyError:
#             return HttpResponse("Error")
#     else:
#         return HttpResponse("Error")

def get_rect(closest):
    rects = []
    for i in range(settings.NB_CAMS):
        rdic = {}
        rdic['rectangleID'] = closest
        if closest in settings.RECT[i]:
            a,b,c,d,ratio = settings.RECT[i][closest]
        else:
            a,b,c,d,ratio = 0,0,0,0,0
        rdic['x1'] = a
        rdic['y1'] = b
        rdic['x2'] = c
        rdic['y2'] = d
        rdic['cameraID'] = i
        rdic['ratio'] = ratio
        rdic['xMid'] = (a + c) // 2
        rects.append(rdic)
    return rects

def download(request):
    context = RequestContext(request).flatten()
    fpath = "marker/labels"
    files = os.listdir(fpath)
    todl = []
    if request.method == "POST":

        zip_dir = "annotations"
        zip_name = zip_dir + ".zip"
        s = BytesIO()
        zf = zipfile.ZipFile(s,"w")

        if 'dlselect' in request.POST:
            for r in request.POST:
                if r in files:
                    zipath = os.path.join(zip_dir,r)
                    zf.write(fpath + "/" + r,zipath)
            zf.close()
            resp = HttpResponse(s.getvalue(), content_type = "application/x-zip-compressed")
            resp['Content-Disposition'] = 'attachment; filename=' + zip_name
            return resp

        elif 'dlall' in request.POST:
            for r in files:
                zipath = os.path.join(zip_dir,r)
                zf.write(fpath + "/" + r,zipath)
            zf.close()
            resp = HttpResponse(s.getvalue(), content_type = "application/x-zip-compressed")
            resp['Content-Disposition'] = 'attachment; filename=' + zip_name
            return resp

    return render(request, 'marker/download.html',{'files': files, **context})

def download_worker(request):
    context = RequestContext(request).flatten()
    fpath = "./gtm_hit/labels"
    files = os.listdir(fpath)
    todl = []
    if request.method == "POST":

        zip_dir = "annotations"
        zip_name = zip_dir + ".zip"
        s = BytesIO()
        zf = zipfile.ZipFile(s,"w")

        if 'dlselect' in request.POST:
            for r in request.POST:
                if r in files:
                    zipath = os.path.join(zip_dir,r)
                    zf.write(fpath + "/" + r,zipath)
            zf.close()
            resp = HttpResponse(s.getvalue(), content_type = "application/x-zip-compressed")
            resp['Content-Disposition'] = 'attachment; filename=' + zip_name
            return resp

        elif 'dlall' in request.POST:
            for r in files:
                zipath = os.path.join(zip_dir,r)
                zf.write(fpath + "/" + r,zipath)
            zf.close()
            resp = HttpResponse(s.getvalue(), content_type = "application/x-zip-compressed")
            resp['Content-Disposition'] = 'attachment; filename=' + zip_name
            return resp

    return render(request, 'marker/download.html',{'files': files,**context})


def user_login(request):
    context = RequestContext(request).flatten()
    error = False
    active = True
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)

        if user:
            if user.is_active:
                login(request, user)
                return HttpResponseRedirect('/marker/')
            else:
                active = False
        else:
            error = True

    return render(request,'marker/login.html', {'error': error, 'active':active, **context})

@login_required
def user_logout(request):
    logout(request)
    return HttpResponseRedirect('/')


def loadfile(request):
    if is_ajax(request):
        try:
            fileID = request.POST['ID']
            rect_json = read_save(fileID,True)
            return HttpResponse(rect_json,content_type="application/json")
        except (FileNotFoundError, KeyError):
            return HttpResponse("Error")
    return HttpResponse("Error")


#video writer
# import os
# from django.db import models, transaction
# import numpy as np
# from django.conf import settings
# from gtm_hit.misc import geometry
# from gtm_hit.models import Annotation, Annotation2DView, MultiViewFrame, Person, View
# from django.core.exceptions import ObjectDoesNotExist
# from ipdb import set_trace
# from gtm_hit.misc.invision.camera_frame import CameraFrame
# import cv2 as cv

# def create_image_grid(images, grid_size=None):
#     assert images.ndim == 3 or images.ndim == 4
#     num, img_w, img_h = images.shape[0], images.shape[-2], images.shape[-3]

#     if grid_size is not None:
#         grid_h, grid_w = tuple(grid_size)
#     else:
#         grid_w = max(int(np.ceil(np.sqrt(num))), 1)
#         grid_h = max((num - 1) // grid_w + 1, 1)

#     grid = np.zeros([grid_h * img_h, grid_w * img_w] + list(images.shape[-1:]), dtype=images.dtype)
#     for idx in range(num):
#         x = (idx % grid_w) * img_w
#         y = (idx // grid_w) * img_h
#         grid[y : y + img_h, x : x + img_w, ...] = images[idx]
#     return grid

# def create_video(video_out, fps, dataset_name, worker_id):
#     set_trace()
#     video_writer = None
#     break_flag = False
#     cam_id_mat = np.mgrid[1:3,1:5].reshape(2,-1).T
#     for i, cam_id in enumerate(cam_id_mat):
#         cam_id_key = f"cam_{cam_id[0]}_{cam_id[1]}"
#         with open(f'motmetrics/gt_{cam_id_key}_output.txt', 'w') as f:
        
#             for frame_id in range(3150, 4415,7):
#                 frame_list = []
#                 try:
#                     frame = MultiViewFrame.objects.get(frame_id=frame_id, dataset__name=dataset_name,worker_id=worker_id)
#                 except ObjectDoesNotExist:
#                     continue
#                 print(f'[{cam_id_key}] Processing frame {frame_id} ...', end='\r')

#                 annotations2d_cam = Annotation2DView.objects.filter(annotation__frame=frame, view__view_id=i)#annotation__person__annotation_complete=True)
                
#                 for det in annotations2d_cam:
#                     if det.cuboid_points==None:
#                         continue

#                     track_id = det.annotation.person.person_id

#                     bb_left = det.x1
#                     bb_top = det.y1
#                     bb_width = det.x2 - det.x1
#                     bb_height = det.y2 - det.y1

#                     confidence = 1

#                     x,y,z = det.annotation.Xw, det.annotation.Yw, det.annotation.Zw

                    
#                     annotation_complete = det.annotation.person.annotation_complete
#                     if annotation_complete:
#                         line = f"{frame_id},{track_id},{bb_left:.2f},{bb_top:.2f},{bb_width:.2f},{bb_height:.2f},{confidence},{x:.2f},{y:.2f},{z:.2f}\n"

#                         f.write(line)
#             print(f'[{cam_id_key}] OK ...')
#         print(f'Done!')
        

# def create_video2(video_out, fps, dataset_name, worker_id):
#     video_writer = None
#     break_flag = False
#     cam_id_mat = np.mgrid[1:3,1:5].reshape(2,-1).T
#     for frame_id in range(3150, 5000,7):
#         frame_list = []
#         try:
#             frame = MultiViewFrame.objects.get(frame_id=frame_id, dataset__name=dataset_name,worker_id=worker_id)
#         except ObjectDoesNotExist:
#             continue
#         print(f'Processing frame {frame_id}...')

#         for i, cam_id in enumerate(cam_id_mat):
#             annotations2d_cam = Annotation2DView.objects.filter(annotation__frame=frame, view__view_id=i)#annotation__person__annotation_complete=True)
#             cam_id = tuple(cam_id)

#             framepath = f"gtm_hit/static/gtm_hit/dset/13apr/undistorted_frames/cam{i+1}/{frame_id:08d}.jpg"
#             camera_frame = CameraFrame(framepath, None, None, is_distorted=False)
#             framesave = camera_frame.get_frame_with_db_annotations(annotations2d_cam)
#             if not os.path.exists(f"13apr/undistorted_frames/cam{i+1}/"):
#                 os.makedirs(f"13apr/undistorted_frames/cam{i+1}/")
#             # ret = cv.imwrite(
#             #     f"13apr/undistorted_frames/cam{i+1}/{frame_id:08d}.jpg", framesave)
#             frame_list.append(framesave)
            
        
#         frame_list = np.array(frame_list)
#         frames_grid = create_image_grid(frame_list, grid_size=(3, 3))
#         out_size = frames_grid.shape[0:2]
#         out_size = out_size[::-1]
#         if video_writer is None:
#             video_writer = cv.VideoWriter(video_out,
#                                     cv.VideoWriter_fourcc(*'XVID'),
#                                     fps,
#                                     out_size)
        
#         video_writer.write(frames_grid)

#         if break_flag:
#             break
#     video_writer.release()