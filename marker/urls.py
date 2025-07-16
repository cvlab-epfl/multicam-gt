from django.urls import re_path as url

from . import views

urlpatterns = [
    url(r'^$', views.index, name="index"),
    url(r'^frame$', views.frame, name='frame'),
    url(r'^frame/(?P<frame_number>[0-9]+)$', views.framenb, name='framenb'),
    url(r'^download$',views.download,name='download'),
    url(r'^downloadwk$',views.download_worker,name='downloadwk'),
    url(r'^.*click',views.click,name="click"),
    url(r'^.*move',views.move,name="move"),
    # url(r'^.*changeframe$', views.changeframe, name='changeframe'),
    url(r'^.*save$',views.save,name='save'),
    url(r'^.*load$',views.load,name='load'),
    url(r'^.*loadfile$',views.loadfile,name='loadfile'),
    url(r'^.*loadprev$',views.load_previous,name='loadprev'),
    url(r'^login/$', views.user_login, name='login'),
    url(r'^logout/$', views.user_logout, name='logout'),
]
