
import os
import json
import numpy as np
from PIL import Image
from ipdb import set_trace
import re
from gtm_hit.misc.geometry import Calibration
from django.conf import settings
import cv2
from pathlib import Path

def static_path_to_absolute(static_path: str) -> str:
    """
    Converts a Django /static/... path to an absolute path on the filesystem.
    """
    relative = static_path.lstrip("/").replace("static/", "", 1)
    project_root = os.path.abspath(os.path.join(__file__, ".."))  # or hardcode base path
    return os.path.join(project_root, "gtm_hit", "static", relative)

def get_frame_path(frame_id, cam_id) -> Path:
    static = settings.FRAMES / cam_id / f'image_{frame_id}.jpg'
    frame_path = Path(static_path_to_absolute(static))
    
    # Path(static_path_to_absolute(settings.FRAME_PATH_DICT.get(frame_id, {}).get(cam_id, '')))

    return frame_path

def get_frame(frame_id, cam_id):
    img_path = get_frame_path(frame_id, cam_id)
    if img_path is None:
        print(f"Frame {frame_id} missing for camera {camera}")

    img = cv2.imread(str(img_path))
    if img is None:
        print(f"Failed to load image: {img_path}")

    return frame

def get_frame_timestamp(frame_id, cam_id):
    frame_path = get_frame_path(frame_id=frame_id, cam_id=cam_id)
    filename = frame_path.name
    parts = filename.split('_')
    if len(parts) >= 4:
        # Parse the timestamp part (12h40m29s994)
        time_part = parts[3]
        if 'h' in time_part and 'm' in time_part and 's' in time_part:
            hours = int(time_part.split('h')[0])
            minutes = int(time_part.split('h')[1].split('m')[0])
            seconds_parts = time_part.split('m')[1].split('s')
            seconds = int(seconds_parts[0])
            milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
            
            # Convert to total seconds for comparison
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

        return total_seconds
    else:
        return None

def get_valid_timestamp(frame_id, cameras):
    camera_timestamps = {
        camera_id: ts
        for camera_id in cameras
        if (ts := get_frame_timestamp(frame_id, camera_id)) is not None
    }


    consensus_cameras = []
    resulting_timestamp = 0
    timestamps = list(camera_timestamps.values())
    # print(timestamps)
    try:
        min_time = min(timestamps)
        max_time = max(timestamps)
    except:
        print(f"times: {timestamps}, cameras: {camera_timestamps}")
    
    # Check if all cameras are within 0.5 seconds of each other
    if max_time - min_time <= 0.5:
        consensus_cameras = list(camera_timestamps.keys())
        resulting_timestamp = np.mean(list(camera_timestamps.values()))
    else:
        # Find the largest group of cameras within 0.5 seconds of each other
        for camera_id, timestamp in camera_timestamps.items():
            group = [cam for cam, time in camera_timestamps.items() 
                        if abs(time - timestamp) <= 0.5]
            times = [time for cam, time in camera_timestamps.items() 
                        if abs(time - timestamp) <= 0.5]
            if len(group) > len(consensus_cameras):
                consensus_cameras = group
                if times:
                    resulting_timestamp = np.mean(times)
                else:
                    raise ValueError("No consensus timestamps found.")

    return consensus_cameras, resulting_timestamp


def get_valid_cameras(calibs, frame_id, ground_point, max_distance=1000):
    from .geometry import is_visible
    valid_cameras = [camera_id for camera_id in calibs if np.linalg.norm(ground_point + np.dot(calibs[camera_id].R.T, calibs[camera_id].T).flatten()) < max_distance]
    valid_cameras = [camera_id for camera_id in valid_cameras if is_visible(ground_point, camera_id)]
    return valid_cameras

def return_consensus_cams_and_time(calibs, frame_id, ground_point, max_distance=1000):
    
    consensus_cameras, resulting_timestamp = get_valid_timestamp(frame_id, settings.CAMS)

    
    return consensus_cameras, resulting_timestamp

def request_to_dict(request):
    #set_trace()
    retdict = {}
    pattern = r"\[([^\]]*)\]|(\w+)"
    #set_trace()
    for k in request.POST.keys():
        matches = re.findall(pattern, k)
        nested_dict = retdict
        if matches[-1][0]==matches[-1][1]=="":
            matches = matches[:-1]
            #set_trace()
        for i,match in enumerate(matches[:-1]):
            if match[0]==match[1]=="": continue
            p = 1 if i==0 else 0
            if match[p] not in nested_dict:
                nested_dict[match[p]] = {}
            nested_dict = nested_dict[match[p]]
        val = request.POST.getlist(k)
        p = 1 if len(matches) == 1 else 0
        last_match = matches[-1]

        if len(val)==1:
            try:
                nested_dict[last_match[p]]= float(val[0])
            except ValueError:
                nested_dict[last_match[p]]= val[0]
        else:
            nested_dict[last_match[p]]= [float(v) for v in val]
    return retdict

def str2bool(v):
  return v.lower() in ("yes", "true", "t", "1")

def process_action(obj):
    if "action" in obj:
        action_dict = obj["action"]
        if "changeSize" in action_dict:
            size_dict = action_dict["changeSize"]
            for param,val in size_dict.items():
                if val=="increase":
                    sign =1
                elif val=="decrease":
                    sign =-1
                else:
                    continue
                if param=="height":
                    obj["object_size"][0] += settings.SIZE_CHANGE_STEP*sign
                if param=="width":
                    obj["object_size"][1] += settings.SIZE_CHANGE_STEP*sign
                if param=="length":
                    obj["object_size"][2] += settings.SIZE_CHANGE_STEP*sign
        if "rotate" in action_dict:
            rotation_direction = action_dict["rotate"]

            rotation_theta = obj.get("rotation_theta",0)
            if rotation_direction=="cw":
                rotation_theta+= settings.ROTATION_THETA
            elif rotation_direction=="ccw":
                rotation_theta-= settings.ROTATION_THETA
            obj["rotation_theta"] = rotation_theta

        if "move" in action_dict:
            move_direction = action_dict["move"]
            step = settings.MOVE_STEP
            if "stepMultiplier" in action_dict:
                step*=action_dict["stepMultiplier"]
            if move_direction=="left":
                obj["Xw"] -= step
            elif move_direction=="right":
                obj["Xw"] += step
            elif move_direction=="up":
                obj["Yw"] += step
            elif move_direction=="down":
                obj["Yw"] -= step
            elif move_direction=="forward":
                obj["Zw"] += step
            elif move_direction=="backward":
                obj["Zw"] -= step
    return obj

def convert_rect_to_dict(rect_tuple,cuboid, cam_id, rect_id, world_point,object_size,rotation_theta):
    # if cam_id=="7" or cam_id==7:
    #      set_trace()
    #set_trace()
    if rect_tuple[0] is None:
        x1 = x2 = y1 = y2 = ratio = 0
    else:
        x1 = rect_tuple[0]
        y1 = rect_tuple[1]
        x2 = rect_tuple[2]
        y2 = rect_tuple[3]
        ratio = float(((y2-y1)/(x2 - x1 +1e-6))*0.1)
        if ratio==np.inf:
            ratio=0
    return {'rectangleID': rect_id,
            'x1': int(x1),
            'y1': int(y1),
            'x2': int(x2),
            'y2': int(y2),
            'cuboid': cuboid,
            'object_size': object_size,
            'rotation_theta': rotation_theta,
            'cameraID': cam_id,
            'ratio': ratio,
            'xMid': int((x1 + x2) / 2),
            "Xw":float(world_point[0]),
            "Yw":float(world_point[1]),
            "Zw":float(world_point[2])
            }


def read_calibs(calib_filepath, camera_names):

        # log.debug(calib_filepath)
        with open(os.path.abspath(calib_filepath)) as f:    
            calibration_json = json.load(f)

        calibs = list()
        dists = list()

        for i, cname in enumerate(camera_names):
            curr_calib = Calibration(K=np.array(calibration_json[cname]["K"]), R=np.array(calibration_json[cname]["R"]), T=np.array(calibration_json[cname]["t"])[..., np.newaxis], view_id=i)
            curr_dist = np.array(calibration_json[cname]["dist"])

            calibs.append(curr_calib)
            dists.append(curr_dist)

        return calibs 
    

def get_frame_size(dset, cams, start_frame):
    sizes = list()
    for cam in cams:
        frame_pattern = f"image_{start_frame}.jpg"
        frame_path = Path("./gtm_hit/static/gtm_hit/dset") / dset / "frames" / cam
        matching_frames = list(frame_path.glob(frame_pattern))
        
        if matching_frames:
            img = Image.open(matching_frames[0])
            sizes.append(img.width)
            sizes.append(img.height)
    
    return sizes