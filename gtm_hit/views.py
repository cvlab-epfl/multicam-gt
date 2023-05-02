# -*- coding: utf-8 -*-
from curses.textpad import rectangle
from django.shortcuts import get_object_or_404,render, redirect
from django.contrib.auth import authenticate, login, logout
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.core import serializers
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from django.conf import settings
from .models import Worker, ValidationCode
from django.template import RequestContext
import re
import json
import os
import random as rand
from threading import Thread

import random
import numpy as np
from gtm_hit.misc import geometry
from gtm_hit.misc.utils import convert_rect_to_dict

def requestID(request):
    context = RequestContext(request).flatten()
    if request.method == "POST":
        if 'wID' in request.POST:
            workerID = request.POST['wID']
            pattern = re.compile("^[A-Z0-9]+$")
            if pattern.match(workerID):
                return redirect("/gtm_hit/"+workerID+"/processInit")
    return render(request, 'gtm_hit/requestID.html',context)

def processInit(request, workerID):
    context = RequestContext(request).flatten()
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state == -1:
            w.state = 0
            w.save()
        return redirect("/gtm_hit/"+workerID)
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)

def index(request,workerID):
    context = RequestContext(request).flatten()
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state != 0:
            return redirect("/gtm_hit/"+workerID)
        return render(request, 'gtm_hit/index.html',{'workerID' : workerID, **context})

    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)

def processIndex(request, workerID):
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state == 0:
            w.state = 3
            w.save()
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)
    return redirect("/gtm_hit/"+workerID)

def dispatch(request,workerID):
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        try:
            code = ValidationCode.objects.get(worker_id = w)
            stop = False
            i = 2
            while not stop:
                try:
                    w2 = Worker.objects.get(pk = workerID+str(i))
                    c2 = ValidationCode.objects.get(worker_id = w2)
                    i = i + 1
                except Worker.DoesNotExist:
                    stop = True
                except ValidationCode.DoesNotExist:
                    return redirect("/gtm_hit/"+workerID+str(i))
            return redirect("/gtm_hit/"+workerID+str(i))
        except ValidationCode.DoesNotExist:
            pass
    except Worker.DoesNotExist:
        w = registerWorker(workerID)

    state = w.state
    if state == 0:
        return redirect(workerID+'/index')
        #return render(request, 'gtm_hit/frame.html',{'frame_number': frame_number, 'workerID' : workerID},context)
    elif state == 1:
        return redirect(workerID+'/frame')
#        return render(request, 'gtm_hit/finish.html',{'workerID' : workerID, 'validation_code' : validation_code},context)
    elif state == 2:
        return redirect(workerID+'/finish')
#        return render(request, 'gtm_hit/finish.html',{'workerID' : workerID, 'validation_code' : validation_code},context)
    elif state == 3:
        return redirect(workerID+'/tuto')
    elif state == -1:
        return redirect(workerID+'/processInit')
        #return render(request, 'gtm_hit/index.html',{'workerID' : workerID},context)
    else:
        return redirect(workerID+'/index')
        #return render(request, 'gtm_hit/index.html',{'workerID' : workerID},context)

def frame(request,workerID):
    context = RequestContext(request).flatten()
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state != 1:
            return redirect("/gtm_hit/"+workerID)
        if w.frameNB < 0:
            w.frameNB = settings.STARTFRAME
            w.save()
        frame_number = str(int(w.frameNB))
        print(frame_number)
        nblabeled = w.frame_labeled
        return render(request, 'gtm_hit/frame.html',{'dset_name':settings.DSETNAME, 'frame_number': frame_number, 'frame_inc':settings.INCREMENT, 'workerID': workerID,'cams': settings.CAMS, 'frame_size':settings.FRAME_SIZES, 'nb_cams':settings.NB_CAMS, 'nblabeled' : nblabeled, **context})
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)

def processFrame(request,workerID):
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state == 1 and w.frame_labeled >= 500:
            w.state = 2
            timelist = w.getTimeList()
            timelist.append(timezone.now().isoformat())
            w.setTimeList(timelist)
            w.save()
        return redirect("/gtm_hit/"+workerID)
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)

def finish(request,workerID):
    context = RequestContext(request).flatten()
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state == 2:
            validation_code = generate_code(w)
            startframe = w.frameNB - (w.frame_labeled*5)
            try:
                settings.UNLABELED.remove(startframe)
            except ValueError:
                pass
            return render(request, 'gtm_hit/finish.html',{'workerID': workerID, 'validation_code': validation_code, **context})
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)
    return redirect("/gtm_hit/"+workerID)

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

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
#                     print(rects)
#                     rect_json = json.dumps(rects)
#                     return HttpResponse(rect_json,content_type="application/json")

#             return HttpResponse("OK")
#         except KeyError:
#             return HttpResponse("Error")
#     return HttpResponse("No")

def get_rect_calib(world_point):
    rectangles = list()
    rect_id = str(int(world_point[0])) + "_" + str(int(world_point[1])) #random.randint(0,100000)
    for cam_id in range(settings.NB_CAMS):
        rectangle = geometry.get_bbox_from_ground_world(world_point, settings.CALIBS[cam_id], settings.HEIGHT, settings.RADIUS)
        rectangle_as_dict = convert_rect_to_dict(rectangle, cam_id, rect_id, world_point)
        rectangles.append(rectangle_as_dict)    

    return rectangles

def click(request):
    # print("click")
    if is_ajax(request):
        # try:
        x = int(request.POST['x'])
        y = int(request.POST['y'])
        cam = request.POST['canv']
        cam = int(re.findall('\d+',cam)[0]) - 1
        if 0 <= cam < settings.NB_CAMS:
            feet2d_h = np.array([[x], [y], [1]]).astype(np.float32)             
            world_point = geometry.reproject_to_world_ground(feet2d_h, settings.CALIBS[cam].K, settings.CALIBS[cam].R, settings.CALIBS[cam].T, settings.CALIBS[cam].dist)
            rectangles = get_rect_calib(world_point)
            rect_json = json.dumps(rectangles)
            return HttpResponse(rect_json,content_type="application/json")

        return HttpResponse("OK")
    #     except KeyError:
    #         return HttpResponse("Error")
    # return HttpResponse("No")

#[{'rectangleID': 0, 'x1': 702, 'y1': 330, 'x2': 934, 'y2': 855, 'cameraID': 0, 'ratio': array([0.22625544]), 'xMid': 818}, {'rectangleID': 0, 'x1': 1544, 'y1': -17, 'x2': 1465, 'y2': 113, 'cameraID': 1, 'ratio': array([-0.16592601]), 'xMid': 1505}, {'rectangleID': 0, 'x1': 444, 'y1': 143, 'x2': 366, 'y2': 328, 'cameraID': 2, 'ratio': array([-0.23407506]), 'xMid': 405}, {'rectangleID': 0, 'x1': 1758, 'y1': 320, 'x2': 1952, 'y2': 942, 'cameraID': 3, 'ratio': array([0.31964897]), 'xMid': 1855}, {'rectangleID': 0, 'x1': 2173, 'y1': 192, 'x2': 2019, 'y2': 447, 'cameraID': 4, 'ratio': array([-0.1661232]), 'xMid': 2096}, {'rectangleID': 0, 'x1': 1271, 'y1': 162, 'x2': 1376, 'y2': 411, 'cameraID': 5, 'ratio': array([0.23706647]), 'xMid': 1323}, {'rectangleID': 0, 'x1': -828, 'y1': 328, 'x2': -805, 'y2': 1078, 'cameraID': 6, 'ratio': array([3.178409]), 'xMid': -817}]

#[{'rectangleID': 161180, 'x1': 915, 'y1': 343, 'x2': 1053, 'y2': 840, 'cameraID': 0, 'ratio': 0.36217303822937624, 'xMid': 984}, {'rectangleID': 161180, 'x1': 1442, 'y1': -16, 'x2': 1478, 'y2': 113, 'cameraID': 1, 'ratio': 1.3953488372093024, 'xMid': 1460}, {'rectangleID': 161180, 'x1': 322, 'y1': 150, 'x2': 381, 'y2': 330, 'cameraID': 2, 'ratio': 1.0, 'xMid': 3
#51}, {'rectangleID': 161180, 'x1': 0, 'y1': 0, 'x2': 0, 'y2': 0, 'cameraID': 3, 'ratio': 0, 'xMid': 0}, {'rectangleID': 161180, 'x1': 0, 'y1': 0, 'x2': 0, 'y2': 0, 'cameraID': 4, 'ratio': 0, 'xMid': 0}, {'rectangleID': 161180, 'x1': 1336, 'y1': 159, 'x2': 1410, 'y2': 406, 'cameraID': 5, 'ratio': 0.728744939271255, 'xMid': 1373}, {'rectangleID': 161180, 'x1': 0,
#'y1': 0, 'x2': 0, 'y2': 0, 'cameraID': 6, 'ratio': 0, 'xMid': 0}]

def rightclick(request):
    # print("rightclick")
    if is_ajax(request):
        # try:
        x = int(request.POST['data[newx]'])
        y = int(request.POST['data[newy]'])
        cam = request.POST['data[canv]']
        cam = int(re.findall('\d+',cam)[0]) - 1
        if 0 <= cam < settings.NB_CAMS:
            feet2d_h = np.array([[x], [y], [1]]).astype(np.float32)            
            world_point = geometry.reproject_to_world_ground(feet2d_h, settings.CALIBS[cam].K, settings.CALIBS[cam].R, settings.CALIBS[cam].T, settings.CALIBS[cam].dist)
            rectangles = get_rect_calib(world_point)
            rect_json = json.dumps(rectangles)

            return HttpResponse(rect_json,content_type="application/json")

        # except KeyError:
        #     return HttpResponse("Error")
        
    return HttpResponse("Error")

def move(request):
    if is_ajax(request):
        try:
            Xw = float(request.POST['data[Xw]'])
            Yw = float(request.POST['data[Yw]'])
            Zw = float(request.POST['data[Zw]'])

            world_point = np.array([[Xw], [Yw], [Zw]])  

            if request.POST['data[dir]'] == "down":
                world_point = world_point + np.array([[0], [-settings.STEPL], [0]])
                
            elif request.POST['data[dir]'] == "up":
                world_point = world_point + np.array([[0], [settings.STEPL], [0]])
                
            elif request.POST['data[dir]'] == "right":
                world_point = world_point + np.array([[settings.STEPL], [0], [0]])

            elif request.POST['data[dir]'] == "left":
                world_point = world_point + np.array([[-settings.STEPL], [0], [0]])

            else:
                return HttpResponse("Error")
            

            next_rect = get_rect_calib(world_point)

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
            wid = request.POST['workerID']
            annotations = []
            cols = ["rectID","personID","modified","Xw","Yw","Zw"]#,"a1","b1","c1","d1","a2","b2","c2","d2","a3","b3","c3","d3","a4","b4","c4","d4","a5","b5","c5","d5","a6","b6","c6","d6","a7","b7","c7","d7"]
            for i in range(settings.NB_CAMS):
                cols += [f"a{i+1}", f"b{i+1}", f"c{i+1}", f"d{i+1}"]
            annotations.append(cols)
            for r in data:
                row = data[r]
                row.insert(0,r)
                annotations.append(row)
            # with open("gtm_hit/labels/"+ wid + "_" + frameID + '.json', 'w') as outFile:
            #     json.dump(annotations, outFile, sort_keys=True, indent=4, separators=(',', ': '))
            with open(settings.LABEL_PATH / (wid + "_" + frameID + '.json'), 'w') as outFile:
                json.dump(annotations, outFile, sort_keys=True, indent=4, separators=(',', ': '))
            with open(settings.SECOND_LABEL_PATH / (wid + "_" + frameID + '.json'), 'w') as outFile:
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
            wid = request.POST['workerID']
            rect_json = read_save(frameID,wid)
            return HttpResponse(rect_json,content_type="application/json")
        except (FileNotFoundError, KeyError):
            return HttpResponse("Error")
    return HttpResponse("Error")

def load_previous(request):
    if is_ajax(request):
        if settings.NOID:
            return HttpResponse("{}",content_type="application/json")
        try:

            frameID = request.POST['ID']
            wid = request.POST['workerID']
            current_frame = int(frameID)
            closest = float('inf')
            diff = float('inf')

            for f in os.listdir("gtm_hit/static/gtm_hit/dset/"+settings.DSETNAME+"/labels/"):
                if f.endswith(".json"):
                    nb_frame = int((f.split('.')[0]).split('_')[1])
                    if nb_frame < current_frame:
                        if current_frame - nb_frame < diff:
                            diff = current_frame - nb_frame
                            closest = nb_frame
            if closest != float('inf'):
                # frame = "0" * (8 - len(str(closest))) + str(closest)
                frame = str(closest)
                rect_json = read_save(frame,wid)
                return HttpResponse(rect_json,content_type="application/json")
        except (FileNotFoundError, KeyError):
            return HttpResponse("Error")
    return HttpResponse("Error")

def read_save(frameID,workerID):
    with open(settings.LABEL_PATH + (workerID + "_" + frameID + '.json'), 'w') as loadFile:
        annotations = json.load(loadFile)
    rects = []
    for i in annotations[1:]:
        world_point = np.array([[i[3]], [i[4]], [i[5]]])  
        r = get_rect_calib(world_point)
        r.append(i[1])
        r.append(i[2])

        rects.append(r)

    return json.dumps(rects)

def changeframe(request):
    context = RequestContext(request)
    if is_ajax(request):
        frame = 0
        try:
            wID = request.POST['workerID']
            order = request.POST['order']
            frame_number = request.POST['frameID']
            increment = request.POST['incr']

            worker = Worker.objects.get(pk = wID)
            worker.increaseFrame(1)
            worker.save()
            timelist = worker.getTimeList()
            timelist.append(timezone.now().isoformat())
            worker.setTimeList(timelist)
            #validation_code = generate_code()
            #return render(request, 'gtm_hit/finish.html',{'workerID' : wID, 'validation_code': validation_code},context)
            if order == "next":
                frame = int(frame_number) + int(increment)
            elif order == "prev" and (int(frame_number) - int(increment)) >= 0:
                frame = int(frame_number) - int(increment)
            else:
                return HttpResponse("Requested frame not existing")
            # frame = "0" * (8 - len(str(frame))) + str(frame)
            frame = str(frame)

            response = {}
            response['frame'] = frame
            response['nblabeled'] = worker.frame_labeled
            worker.frameNB = frame
            worker.save()
            return HttpResponse(json.dumps(response))
        except KeyError:
            return HttpResponse("Error")
    else:
        return HttpResponse("Error")

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

def registerWorker(workerID):
    w = Worker()
    w.workerID = workerID
    w.frameNB = settings.STARTFRAME % settings.NBFRAMES
    settings.STARTFRAME = settings.STARTFRAME + 10000*settings.INCREMENT 
    w.save()
    return w

def updateWorker(workerID, state):
    w = Worker.objects.get(pk = workerID)

def generate_code(worker):
    try:
        code = ValidationCode.objects.get(worker_id = worker)
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

def tuto(request,workerID):
    context = RequestContext(request).flatten()
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state != 3:
            return redirect("/gtm_hit/"+workerID)
        return render(request, 'gtm_hit/tuto.html',{'workerID' : workerID, **context})

    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)

def processTuto(request, workerID):
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state == 3:
            w.state = 1
            timelist = [timezone.now().isoformat()]
            w.setTimeList(timelist)
            w.save()
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)
    return redirect("/gtm_hit/"+workerID)

def processFinish(request):
    context = RequestContext(request)
    if request.is_ajax():
        try:
            wID = request.POST['workerID']

            w = Worker.objects.get(pk = wID)
            startframe = w.frameNB - w.frame_labeled
            #delete_and_load(startframe)
            return HttpResponse("ok")
        except KeyError:
            return HttpResponse("Error")
    else:
        return HttpResponse("Error")



def delete_and_load(startframe):
    toload = settings.LASTLOADED + 10
     #1. remove frames
    sframe = startframe
     #2. copy next frames
    for i in range(10):
        rm_frame = "0" * (8 - len(str(sframe))) + str(sframe)
        cp_frame = "0" * (8 - len(str(toload))) + str(toload)
        sframe = sframe + 1
        toload = toload + 1
        for j in range(settings.NB_CAMS):
            command = os.system("rm gtm_hit/static/gtm_hit/frames/"+ settings.CAMS[j] + "/" + rm_frame + ".png")
            command = os.system("cp gtm_hit/static/gtm_hit/day_2/annotation_final/"+ settings.CAMS[j] + "/begin/" + cp_frame + ".png gtm_hit/static/gtm_hit/frames/"+ settings.CAMS[j] + "/")

    settings.LASTLOADED = settings.LASTLOADED + 10
