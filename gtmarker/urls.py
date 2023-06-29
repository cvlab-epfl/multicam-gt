"""gtmarker URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.urls import re_path
from django.conf.urls import include, handler404, handler403, handler400,handler500
from django.contrib import admin
from home import views as v

urlpatterns = [
    re_path(r'^$', v.index),
    re_path(r'^marker/', include('marker.urls')),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^gtm_hit/', include('gtm_hit.urls')),
    re_path(r'^login/$', v.login),
]

handler400 = 'home.views.bad_request'
handler403 = 'home.views.permission_denied'
handler404 = 'home.views.page_not_found'
handler500 = 'home.views.server_error'
