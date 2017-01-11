from django.shortcuts import render
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

def index(request):
    context = RequestContext(request)
    return render(request, 'home/index.html',{},context)

def page_not_found(request):
    context = RequestContext(request)
    return render(request, 'home/error.html',{'error': 'Page Not Found'},context,status=404)

def bad_request(request):
    return render(request, 'home/error.html',{'error': 'Bad Request'},status=400)

def permission_denied(request):
    context = RequestContext(request)
    return render(request, 'home/error.html',{'error': 'Permission Denied'},context,status=403)

def server_error(request):
    context = RequestContext(request)
    return render(request, 'home/error.html',{'error': 'Server Error'},context,status=500)

def login(request):
    context = RequestContext(request)
    error = False
    active = True
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)

        if user:
            if user.is_active:
                login(request, user)
                return HttpResponseRedirect('/')
            else:
                active = False
        else:
            error = True

    return render(request,'home/login.html', {'error': error, 'active':active}, context)

@login_required
def logout(request):
    logout(request)
    return HttpResponseRedirect('/')
