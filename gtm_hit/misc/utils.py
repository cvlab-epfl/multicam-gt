
import os
import json
import numpy as np
from PIL import Image
  

from gtm_hit.misc.geometry import Calibration

def convert_rect_to_dict(rect_tuple, cam_id, rect_id, world_point):
    if rect_tuple[0] is None:
        x1 = x2 = y1 = y2 = ratio = 0
    else:
        x1 = rect_tuple[0]
        y1 = rect_tuple[1]
        x2 = rect_tuple[2]
        y2 = rect_tuple[3]
        ratio = float(((y2-y1)/(x2 - x1))*0.1)
     
    return {'rectangleID': rect_id,
            'x1': int(x1),
            'y1': int(y1),
            'x2': int(x2),
            'y2': int(y2),
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
        frame_path = "./gtm_hit/static/gtm_hit/dset/"+dset+"/frames/" + cam + "/" +str(start_frame).zfill(8) + ".png" 
        img = Image.open(frame_path)
        sizes.append(img.width)
        sizes.append(img.height)

    return sizes