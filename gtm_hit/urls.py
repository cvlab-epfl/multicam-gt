from django.urls import re_path as url

from . import views

urlpatterns = [
    url(r'^&MID=(?P<workerID>[A-Z0-9]+)$', views.index, name="index"),
    url(r'^$', views.requestID, name="requestID"),
    url(r'^(?P<workerID>[A-Z0-9]+)/processInit$', views.processInit, name="processInit"),
    url(r'^(?P<workerID>[A-Z0-9]+)/processIndex$', views.processIndex, name="processIndex"),
    url(r'^(?P<workerID>[A-Z0-9]+)/processTuto$', views.processTuto, name="processTuto"),
    url(r'^(?P<workerID>[A-Z0-9]+)$', views.dispatch, name="dispatch"),
    url(r'^(?P<workerID>[A-Z0-9]+)/index$', views.index, name="index"),
    url(r'^(?P<workerID>[A-Z0-9]+)/tuto$', views.tuto, name="tuto"),
    url(r'^(?P<workerID>[A-Z0-9]+)/frame$', views.frame, name='frame'),
    url(r'^(?P<workerID>[A-Z0-9]+)/processFrame$', views.processFrame, name="processFrame"),
    url(r'^.*rightclick',views.rightclick,name="rightclick"),
    url(r'^.*click',views.click,name="click"),
    url(r'^.*move',views.move,name="move"),
    url(r'^.*changeframe$', views.changeframe, name='changeframe'),
    url(r'^.*save$',views.save,name='save'),
    url(r'^.*load$',views.load,name='load'),
    url(r'^.*loadprev$',views.load_previous,name='loadprev'),
    url(r'^.*processFinish$',views.processFinish,name='processFinish'),

    url(r'^(?P<workerID>[A-Z0-9]+)/finish$',views.finish,name='finish'),
]
