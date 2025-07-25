"""
Django settings for gtmarker project.

Generated by 'django-admin startproject' using Django 1.10.2.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import os
from pathlib import Path
import numpy as np
import shutil
from gtm_hit.misc.utils import read_calibs, get_frame_size
from gtm_hit.misc.scout_calib import load_scout_calib
from gtm_hit.misc.autoalign import get_pose_model
import re
import cv2 as cv2
from tqdm import tqdm
import json
from shapely.geometry import Polygon
from gtm_hit.misc.geometry import get_polygon_from_points_3d, reproject_to_world_ground_batched

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '%z1g%^3%nf-k3sf$i^qra_d*0m4745c57f&(su(2=&nuwt#=z1'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

#ALLOWED_HOSTS = ['127.0.0.1']
ALLOWED_HOSTS = ['10.90.43.13', 'pedestriantag.epfl.ch','localhost','127.0.0.1', '0.0.0.0',"192.168.100.23", "iccvlabsrv15.iccluster.epfl.ch"]

# Application definition

INSTALLED_APPS = [
    'marker.apps.MarkerConfig',
    'gtm_hit.apps.Gtm_hitConfig',
    'home',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bootstrapform',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'marker.middleware.RequireLoginMiddleware',
]
LOGIN_REQUIRED_URLS = (
    r'/marker/(.*)$',
)
LOGIN_REQUIRED_URLS_EXCEPTIONS = (
    r'/marker/login(.*)$',
    r'/marker/logout(.*)$',
)

LOGIN_URL = '/login/'

ROOT_URLCONF = 'gtmarker.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gtmarker.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'scout',
        'USER': 'scout',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '',
    }
}
DATA_UPLOAD_MAX_NUMBER_FIELDS = None

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = Path('gtm_hit/static')
SAVES = '/labels/'

# Constants
DELTA_SEARCH = 5

DSETNAME = "SCOUT"

# Enable mesh
USE_MESH = True
# Paths
DSETPATH = STATIC_ROOT / "gtm_hit" / "dset" / DSETNAME
FRAMES = DSETPATH / "frames"
CALIBPATH = DSETPATH / "calibrations"
MESHPATH = DSETPATH / "meshes" / "mesh_ground_only.ply"
ROIPATH = DSETPATH / "roi" / "roi.json"

FPS = 1 # framerate of input video (note, assumes 10fps base)
NUM_FRAMES = 12000
FRAME_START = 0
FRAME_END = FRAME_START + NUM_FRAMES
HEIGHT = 1.8
RADIUS = 0.5 # person radius
FLAT_GROUND = False # Whether or not to use the mesh for dataset generation and annotation
FRAME_SKIP = int(float(10 / FPS))
TIMEWINDOW = 5 * FRAME_SKIP # cropped frames loaded when selecting a bounding box (on either side)

VALIDATIONCODES = []
STARTFRAME = 2
NBFRAMES = NUM_FRAMES + 10
LASTLOADED = 0
INCREMENT = FRAME_SKIP
UNLABELED = list(range(0,NBFRAMES,INCREMENT))

STEPL = 0.02
MOVE_STEP = 0.02 #same as stepl vidis ovoDA
SIZE_CHANGE_STEP=0.03

# CAMS = [Path(cam).name.replace('.json', '') for cam in CALIBPATH.iterdir()]
CAMS = sorted(
    [Path(cam).name.replace('.json', '') for cam in CALIBPATH.iterdir()],
    key=lambda x: int(x.split('_')[1])
)

FRAME_SIZES = get_frame_size(DSETNAME, CAMS, STARTFRAME)
NB_CAMS = len(CAMS)
CALIBS= load_scout_calib(CALIBPATH, cameras=CAMS)
ROTATION_THETA = np.pi/24
UNDISTORTED_FRAMES=False
MERGE_THRESHOLD = 1.0
MAX_OUTLIER_GAP = 4
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


import trimesh
try:
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    print("Fast ray intersection active.")
except:
    print("Install pyembree for faster mesh intersections.")

MESH = trimesh.load(MESHPATH, process=False, maintain_order=True, ignore_missing_files=True)
if hasattr(MESH, 'visual'):
    MESH.visual = trimesh.visual.ColorVisuals(MESH)


ROIjson = json.load(open(ROIPATH))

ROI = {}
for cam_name, polygon in ROIjson['points_2d'].items():
    if not cam_name in CALIBS.keys():
        continue
    # project 2d points to 3d
    ground_pix = np.array(polygon)
    K0, R0, T0, dist = CALIBS[cam_name].K, CALIBS[cam_name].R, CALIBS[cam_name].T, CALIBS[cam_name].dist
    polygon_3d = reproject_to_world_ground_batched(ground_pix, K0, R0, T0, dist)
    ROI[cam_name] = get_polygon_from_points_3d(polygon_3d)




POSE_MODEL = get_pose_model(model_type="light") #performance