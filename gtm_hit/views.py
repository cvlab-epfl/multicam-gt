# -*- coding: utf-8 -*-
from django.shortcuts import get_object_or_404,render, redirect
from django.contrib.auth import authenticate, login, logout
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.core import serializers
from django.core.urlresolvers import reverse
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

def requestID(request):
    context = RequestContext(request)
    if request.method == "POST":
        if 'wID' in request.POST:
            workerID = request.POST['wID']
            pattern = re.compile("^[A-Z0-9]+$")
            if pattern.match(workerID):
                return redirect("/gtm_hit/"+workerID+"/processInit")
    return render(request, 'gtm_hit/requestID.html',{},context)

def processInit(request, workerID):
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state == -1:
            w.state = 0
            w.save()
        return redirect("/gtm_hit/"+workerID)
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)

def index(request,workerID):
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state != 0:
            return redirect("/gtm_hit/"+workerID)
        return render(request, 'gtm_hit/index.html',{'workerID' : workerID},context)

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
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state != 1:
            return redirect("/gtm_hit/"+workerID)
        if w.frameNB < 0:
            w.frameNB = settings.STARTFRAME
            w.save()
        frame_number = w.frameNB
        nblabeled = w.frame_labeled
        return render(request, 'gtm_hit/frame.html',{'frame_number': frame_number, 'workerID': workerID,'cams': settings.CAMS, 'path': settings.SERVER_PATH, 'nblabeled' : nblabeled},context)
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)

def processFrame(request,workerID):
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state == 1 and w.frame_labeled >= 9:
            w.state = 2
            timelist = w.getTimeList()
            timelist.append(timezone.now().isoformat())
            w.setTimeList(timelist)
            w.save()
        return redirect("/gtm_hit/"+workerID)
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)

def finish(request,workerID):
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state == 2:
            validation_code = generate_code(w)
            startframe = w.frameNB - (w.frame_labeled*5)
            try:
                settings.UNLABELED.remove(startframe)
            except ValueError:
                pass
            return render(request, 'gtm_hit/finish.html',{'workerID': workerID, 'validation_code': validation_code},context)
    except Worker.DoesNotExist:
        return redirect("/gtm_hit/"+workerID)
    return redirect("/gtm_hit/"+workerID)

def click(request):
    if request.is_ajax():
        try:
            x = int(request.POST['x'])
            y = int(request.POST['y'])
            cam = request.POST['canv']
            cam = int(re.findall('\d+',cam)[0]) - 1
            if 0 <= cam < settings.NB_CAMS:
                closest = -1
                vbest = 1000
                for y_temp in range(y - settings.DELTA_SEARCH, y + settings.DELTA_SEARCH):
                    if 0 <= y_temp < 1080:
                        for x_temp in settings.FIND_RECT[cam][y_temp]:
                            vtemp = abs(y - y_temp) + abs(x - x_temp)
                            if vtemp < vbest:
                                vbest, closest = vtemp, settings.FIND_RECT[cam][y_temp][x_temp]
                if closest != -1:
                    rects = get_rect(closest)
                    rect_json = json.dumps(rects)
                    return HttpResponse(rect_json,content_type="application/json")

            return HttpResponse("OK")
        except KeyError:
            return HttpResponse("Error")
    return HttpResponse("No")

def move(request):
    if request.is_ajax():
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
    if request.is_ajax():
        try:
            data = json.loads(request.POST['data'])
            frameID = request.POST['ID']
            wid = request.POST['workerID']
            annotations = []
            cols = ["rectID","personID","modified","a1","b1","c1","d1","a2","b2","c2","d2","a3","b3","c3","d3","a4","b4","c4","d4","a5","b5","c5","d5","a6","b6","c6","d6","a7","b7","c7","d7"]
            annotations.append(cols)
            for r in data:
                row = data[r]
                row.insert(0,int(r))
                annotations.append(row)
            with open("gtm_hit/labels/"+ wid + "_" + frameID + '.json', 'w') as outFile:
                json.dump(annotations, outFile, sort_keys=True, indent=4, separators=(',', ': '))
            with open("gtm_hit/static/gtm_hit/day_2/annotation_final/labels/"+ wid + "_" + frameID + '.json', 'w') as outFile:
                json.dump(annotations, outFile, sort_keys=True, indent=4, separators=(',', ': '))
            return HttpResponse("Saved")
        except KeyError:
            return HttpResponse("Error")
    else:
        return("Error")

def load(request):
    if request.is_ajax():
        try:
            frameID = request.POST['ID']
            wid = request.POST['workerID']
            rect_json = read_save(frameID,wid)
            return HttpResponse(rect_json,content_type="application/json")
        except (FileNotFoundError, KeyError):
            return HttpResponse("Error")
    return HttpResponse("Error")

def load_previous(request):
    if request.is_ajax():
        try:

            frameID = request.POST['ID']
            wid = request.POST['workerID']
            current_frame = int(frameID)
            closest = float('inf')
            diff = float('inf')

            for f in os.listdir("gtm_hit/labels/"):
                if f.endswith(".json"):
                    nb_frame = int((f.split('.')[0]).split('_')[1])
                    if nb_frame < current_frame:
                        if current_frame - nb_frame < diff:
                            diff = current_frame - nb_frame
                            closest = nb_frame
            if closest != float('inf'):
                frame = "0" * (8 - len(str(closest))) + str(closest)
                rect_json = read_save(frame,wid)
                return HttpResponse(rect_json,content_type="application/json")
        except (FileNotFoundError, KeyError):
            return HttpResponse("Error")
    return HttpResponse("Error")

def read_save(frameID,workerID):
    with open("gtm_hit/labels/"+ workerID + "_" + frameID + '.json','r') as loadFile:
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

def changeframe(request):
    context = RequestContext(request)
    if request.is_ajax():
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
            frame = "0" * (8 - len(str(frame))) + str(frame)
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
    settings.STARTFRAME = settings.STARTFRAME + 50
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
    context = RequestContext(request)
    try:
        w = Worker.objects.get(pk = workerID)
        if w.state != 3:
            return redirect("/gtm_hit/"+workerID)
        return render(request, 'gtm_hit/tuto.html',{'workerID' : workerID},context)

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
