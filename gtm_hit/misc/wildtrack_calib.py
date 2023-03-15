import os
import cv2
import numpy as np

import xml.etree.ElementTree as ElementTree
from xml.dom import minidom
from gtm_hit.misc.geometry import Calibration

def load_opencv_xml(filename, element_name, dtype='float32'):
    """
    Loads particular element from a given OpenCV XML file.
    Raises:
        FileNotFoundError: the given file cannot be read/found
        UnicodeDecodeError: if error occurs while decoding the file
    :param filename: [str] name of the OpenCV XML file
    :param element_name: [str] element in the file
    :param dtype: [str] type of element, default: 'float32'
    :return: [numpy.ndarray] the value of the element_name
    """
    if not os.path.isfile(filename):
        raise FileNotFoundError("File %s not found." % filename)
    try:
        tree = ElementTree.parse(filename)
        rows = int(tree.find(element_name).find('rows').text)
        cols = int(tree.find(element_name).find('cols').text)
        return np.fromstring(tree.find(element_name).find('data').text,
                             dtype, count=rows*cols, sep=' ').reshape((rows, cols))
    except Exception as e:
        print(e)
        raise UnicodeDecodeError('Error while decoding file %s.' % filename)
        

def load_all_extrinsics(_lst_files):
    """
    Loads all the extrinsic files, listed in _lst_files.
    Raises:
        FileNotFoundError: see _load_content_lines
        ValueError: see _load_content_lines
    :param _lst_files: [str] path of a file listing all the extrinsic calibration files
    :return: tuple of ([2D array], [2D array]) where the first and the second integers
             are indexing the camera/file and the element of the corresponding vector,
             respectively. E.g. rvec[i][j], refers to the rvec for the i-th camera,
             and the j-th element of it (out of total 3)
    """
#     extrinsic_files = _load_content_lines(_lst_files)
    rvec, tvec = [], []
    for _file in _lst_files:
        xmldoc = minidom.parse(_file)
        rvec.append([float(number)
                     for number in xmldoc.getElementsByTagName('rvec')[0].childNodes[0].nodeValue.strip().split()])
        tvec.append([float(number)
                     for number in xmldoc.getElementsByTagName('tvec')[0].childNodes[0].nodeValue.strip().split()])
    return rvec, tvec


def load_all_intrinsics(_lst_files):

    _cameraMatrices, _distCoeffs = [], []
    for _file in _lst_files:
        _cameraMatrices.append(load_opencv_xml(_file, 'camera_matrix'))
        _distCoeffs.append(load_opencv_xml(_file, 'distortion_coefficients'))
    return _cameraMatrices, _distCoeffs



# Calibration = namedtuple('Calibration', ['K', 'R', 'T', 'dist', 'view_id'])
def load_calibrations(root_path):

    intrinsic_path_format = "calibrations/intrinsic_zero/intr_{}.xml"
    extrinsic_path_format = "calibrations/extrinsic/extr_{}.xml"

    camera_id_to_name = ["CVLab1", "CVLab2", "CVLab3", "CVLab4", "IDIAP1", "IDIAP2", "IDIAP3"]

    intrinsic_pathes = [str(root_path / intrinsic_path_format.format(camera)) for camera in camera_id_to_name]
    extrinsic_pathes = [str(root_path / extrinsic_path_format.format(camera)) for camera in camera_id_to_name]

    rotationxyz, T = load_all_extrinsics(extrinsic_pathes)
    K, dist = load_all_intrinsics(intrinsic_pathes)
    
    calib_multi = list()
    for view_id in range(len(intrinsic_pathes)):
#         R = Rotation.from_euler('xyz', rotationxyz[view_id], degrees=False).as_matrix()
        R, _ = cv2.Rodrigues(np.array(rotationxyz[view_id]))

        # dist=dist[view_id]
        calib_multi.append(Calibration(K=K[view_id], R=R, T=np.array(T[view_id])[..., np.newaxis], view_id=view_id))

    return calib_multi