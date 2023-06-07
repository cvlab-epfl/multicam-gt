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


def index(request):
    context = RequestContext(request).flatten()
    return render(request, 'marker/index.html',context)

def framenb(request,frame_number):
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
    worker_p = "gtm_hit/labels"
    files = os.listdir(worker_p)
    marker_p = "marker/labels"
    files = files + os.listdir(marker_p)
    return files
def click(request):
    if is_ajax(request):
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

def read_save(frameID,fullpath=False):
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

def changeframe(request):
    if is_ajax(request):
        frame = 0
        try:
            order = request.POST['order']
            frame_number = request.POST['frameID']
            increment = request.POST['incr']
            if order == "next":
                frame = int(frame_number) + int(increment)
            elif order == "prev" and (int(frame_number) - int(increment)) >= 0:
                frame = int(frame_number) - int(increment)
            else:
                return HttpResponse("Requested frame not existing")
            frame = "0" * (8 - len(str(frame))) + str(frame)
            return HttpResponse(json.dumps(frame))
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
    fpath = "gtm_hit/labels"
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
