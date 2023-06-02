import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from collections import namedtuple


Calibration = namedtuple('Calibration', ['K', 'R', 'T', 'dist', 'view_id'])
Bbox = namedtuple('Bbox', ['xc', 'yc', 'w', 'h']) #, 'id', 'frame'])
Annotations = namedtuple('Annotations', ['bbox', 'head', 'feet', 'height', 'id', 
                                         'frame', 'view'])
Homography = namedtuple('Homography', ['H', 'input_size', 'output_size'])

def reproject_to_world_ground(ground_pix, K0, R0, T0, D0):
    """
    Compute world coordinate from pixel coordinate of point on the groundplane
    """
    # print(ground_pix.shape)
    # print(ground_pix)
    # import pdb; pdb.set_trace()
    K0 = np.array(K0).astype(np.float32)
    R0 = np.array(R0).astype(np.float32)
    T0 = np.array(T0).astype(np.float32)
    D0 = np.array(D0).astype(np.float32)
    ground_pix[:2, 0] = cv2.undistortPoints(ground_pix[:2], K0, D0, P = K0)[0]
    # print(ground_pix.shape)

    C0 = -R0.T @ T0
    l = R0.T @ np.linalg.inv(K0) @ ground_pix
    l = l.reshape(3,)
    world_point = C0 - l*(C0[2]/l[2])
    
    return world_point
    
    
def project_world_to_camera(world_point, K1, R1, T1, D1):
    """
    Project 3D point world coordinate to image plane (pixel coordinate)

    :param world_point: (3,) array of world coordinates of the point
    :param K1: (3, 3) camera matrix of the camera
    :param R1: (3, 3) rotation matrix of the camera
    :param T1: (3, 1) translation vector of the camera
    :param D1: (N, 1) distortion coefficients of the camera

    :returns: (2,) array of pixel coordinates of the point
    """
    world_point = np.array(world_point).reshape(3,1).astype(np.float32)
    K1 = np.array(K1).reshape(3,3).astype(np.float32)
    R1 = Rotation.from_matrix(R1).as_rotvec().astype(np.float32)
    T1 = np.array(T1).reshape(3,1).astype(np.float32)
    D1 = np.array(D1).reshape(-1,1).astype(np.float32)
    
    point1, _ = cv2.projectPoints(world_point, R1, T1, K1, D1)

    return point1.squeeze()


def get_bbox_from_ground_world(world_point, calib, height, radius):
    """
    Compute bounding box in pixel coordinates from world coordinates of the 
    center of the bbox

    :param world_point: (3,) array of world coordinates of the center 
                            of the bbox
    :param calib: Calibration object
    :param height: height of the bbox
    :param radius: radius of the bbox

    :returns: (x1, y1, x2, y2) pixel coordinates of the bounding box
    """
    top_left = calib.R.T@((calib.R@(world_point 
                                    + np.array([[0],[0],[height]]).reshape(3,))) 
                                    + np.array([[-radius],[0],[0]]).reshape(3,))
    bottom_right = calib.R.T@((calib.R@world_point) 
                              + np.array([[radius],[0],[0]]).reshape(3,))
    
    x1, y1 = project_world_to_camera(top_left, calib.K, calib.R, 
                                     calib.T, calib.dist)
    
    x2, y2 = project_world_to_camera(bottom_right, calib.K, calib.R, 
                                     calib.T, calib.dist)

    return (x1, y1, x2, y2)

def triangulate_point(points_2d, multi_calib):
    """
    Triangulate 3D point from 2D points in multiple views

    :param points_2d: (N, 2) array of 2D points in multiple views
    :param multi_calib: list of Calibration objects

    :returns: (3,) 3D point
    """
    #Need at least point of view
    assert points_2d.shape[0] > 1
    
    #compute camera position for each view
    camera_positions = [-calib.R.T @ calib.T for calib in multi_calib]
    
    #Compute 3D direction from camera toward point
    point_directions = [-calib.R.T @ np.linalg.inv(calib.K_new) 
                        @ point for point, calib in zip(points_2d, multi_calib)]
    
    point_3d = nearest_intersection(np.array(camera_positions).squeeze(2), 
                                    np.array(point_directions))
    
    return point_3d


def nearest_intersection(points, dirs):
    """
    :param points: (N, 3) array of points on the lines
    :param dirs: (N, 3) array of unit direction vectors
    :returns: (3,) array of intersection point
    
    from https://stackoverflow.com/questions/52088966/nearest-intersection-point-to-many-lines-in-python
    """
    #normalized direction
    dirs = dirs / np.linalg.norm(dirs, axis=1, keepdims=True)
    dirs_mat = dirs[:, :, np.newaxis] @ dirs[:, np.newaxis, :]
    points_mat = points[:, :, np.newaxis]
    I = np.eye(3)
    return np.linalg.lstsq(
        (I - dirs_mat).sum(axis=0),
        ((I - dirs_mat) @ points_mat).sum(axis=0),
        rcond=None
    )[0]


def project_roi_world_to_camera(world_point, K1, R1, T1):
    """
    Project Region of interest 3D points world coordinate to image plane 
    (pixel coordinate)
    A bit Hacky since world coordinate are sometime behind image plane, 
    we interpolate between corner of polygon
    to only keep point in front of the image plane

    :param world_point: (3, N) array of world coordinates of the points
    :param K1: (3, 3) camera matrix of the camera
    :param R1: (3, 3) rotation matrix of the camera
    :param T1: (3, 1) translation vector of the camera

    :returns: (2, N) array of pixel coordinates of the points
    """

    point1 = ((R1 @ world_point) + T1)

    if point1[2].min() < 0:
        #If a corner point of the roi lie behind the image compute 
        # corespondence in the image plane
        x = world_point[0]
        y = world_point[1]

        # Evenly sample point around polygon define by corner point in world_point
        distance = np.cumsum(np.sqrt( np.ediff1d(x, to_begin = 0)**2 
                                     + np.ediff1d(y, to_begin = 0)**2 ))
        
        distance = distance/distance[-1]

        fx, fy = interp1d( distance, x ), interp1d( distance, y )

        alpha = np.linspace(0, 1, 150)
        x_regular, y_regular = fx(alpha), fy(alpha)

        world_point = np.vstack([x_regular, y_regular, 
                                 np.zeros(x_regular.shape)])

        point1 = ((R1 @ world_point) + T1)
        
        #Filter out point behind the camera plane (Z < 0)    
        point1 = np.delete(point1, point1[2] < 0, axis=1)
    point1 = K1 @ point1
    point1 = point1 / point1[2]
    
    return point1[:2]


def update_img_point_boundary(img_points, view_ground_edge):
    """
    Update the img_points to make sure that all the img points are inside the 
    image, if there are not replace them by points on the boundary

    :param img_points: (N, 2) array of pixel coordinates of the points
    :param view_ground_edge: (N, 2) array of pixel coordinates of the points

    :returns: (N, 2) array of pixel coordinates of the points
    """
    #Make sure that all the img point are inside the image, if there are not
    #  replace them by points on the boundary
    img_points = map(Point, img_points)
    # img_corners = map(Point, [(0.0, 0.0), (0.0, img_size[0]), 
    # (img_size[1], img_size[0]), (img_size[1], 0.0)])
    img_corners = map(Point, view_ground_edge)

    poly1 = Polygon(*img_points)
    poly2 = Polygon(*img_corners)
    isIntersection = intersection(poly1, poly2)# poly1.intersection(poly2)
    
    point_inside = list(isIntersection)
    point_inside.extend([p for p in poly1.vertices if poly2.encloses_point(p)])
    point_inside.extend([p for p in poly2.vertices if poly1.encloses_point(p)])
   
    boundary_updated = convex_hull(*point_inside).vertices    
    boundary_updated = [p.coordinates for p in boundary_updated]

    return np.stack(boundary_updated).astype(float)


def update_K_after_resize(K, old_size, new_size):
    """
    Update the camera matrix K after a resize of the image

    :param K: (3, 3) camera matrix of the camera
    :param old_size: (2,) array of the old image size
    :param new_size: (2,) array of the new image size

    :returns: (3, 3) camera matrix of the camera
    """
    assert len(old_size) == 2 and len(new_size) == 2, "Size must be 2D"
    assert np.all(old_size>0) and np.all(new_size>0), "Size must be positive"
    assert K.shape == (3, 3), "K must be a 3x3 matrix"

    fx = 1.0 / (old_size[1] / new_size[1])
    fy = 1.0 / (old_size[0] / new_size[0])

    scaler = np.array([
        [fx, 0, 0],
        [0, fy, 0],
        [0, 0, 1]]
    )

    new_K = scaler @ K

    return new_K

def rescale_keypoints(points, org_img_dim, out_img_dim):

    if len(points) == 0:
        return points
    
    out_img_dim = np.array(out_img_dim)
    org_img_dim = np.array(org_img_dim)
    
    if np.all(org_img_dim == out_img_dim):
        return points
    
    resize_factor = out_img_dim / org_img_dim
    #swap x and y
    resize_factor = resize_factor[::-1]

    resized_points = points*resize_factor

    return resized_points

def distance_point_to_line(lp1, lp2, p3):
    #Both point of the line are the same return distance to that point
    if np.all(lp1 == lp2):
        return np.linalg.norm(p3-lp1)
    else:
        return np.abs(np.cross(lp2-lp1, lp1-p3) / np.linalg.norm(lp2-lp1))