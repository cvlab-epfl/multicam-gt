"""
Geometry utilities for multi-view 3D annotation and camera projection.

This module provides classes and functions for:
- 3D cuboid and bounding box computation
- Camera projection and calibration
- Ray-mesh intersection and ground plane projection
- Visibility checks and geometric utilities for annotation
"""

import numpy as np
import cv2 as cv
from collections import namedtuple
from enum import IntEnum
from django.conf import settings
import trimesh
from .scout_calib import CameraParams
from matplotlib.path import Path as mplpath

Calibration = namedtuple('Calibration', ['K', 'R', 'T', 'view_id'])

class Cuboid:
    """
    Represents a 3D cuboid in world coordinates and provides methods to project
    it into camera/image space.
    Args:
        calib (CameraParams): Camera calibration parameters.
        world_point (np.ndarray): 3D world coordinates of the cuboid center.
        width (float): Width of the cuboid (default: settings.RADIUS).
        length (float): Length of the cuboid (default: settings.RADIUS).
        height (float): Height of the cuboid (default: settings.HEIGHT).
    """
    def __init__(self, calib:CameraParams, 
                 world_point:np.ndarray, 
                 width:float = None, 
                 length:float = None,
                 height:float = None):

        if width is None:
            width = settings.RADIUS
        if length is None:
            length = settings.RADIUS
        if height is None:
            height = settings.HEIGHT

        self.calib = calib

        self.front_top_right = np.array([width / 2, length / 2, height])
        self.front_top_left = np.array([-width / 2, length / 2, height])
        self.rear_top_right = np.array([width / 2, -length / 2, height])
        self.rear_top_left = np.array([-width / 2, -length / 2, height])
        self.front_bottom_right = np.array([width / 2, length / 2, 0])
        self.front_bottom_left = np.array([-width / 2, length / 2, 0])
        self.rear_bottom_right = np.array([width / 2, -length / 2, 0])
        self.rear_bottom_left = np.array([-width / 2, -length / 2, 0])
        self.base = np.array([0, 0, 0])
        self.direction = np.array([0, length / 2, 0])

        self.cuboid_points3d = np.vstack([self.front_top_right,
                                          self.front_top_left,
                                          self.rear_top_right,
                                          self.rear_top_left,
                                          self.front_bottom_right,
                                          self.front_bottom_left,
                                          self.rear_bottom_right,
                                          self.rear_bottom_left,
                                          self.base,
                                          self.direction])
        
        self.world_point = world_point
        
    def get_cuboid_points3d(self):
        """
        Returns the 3D coordinates of the cuboid's corners in local cuboid space.
        Returns:
            np.ndarray: Array of shape (10, 3) with cuboid corner points.
        """
        return self.cuboid_points3d
    
    def get_cuboid_points_3d_rotated(self, theta:float = 0):
        """
        Returns the 3D cuboid points after rotation around the Z axis.
        Args:
            theta (float): Rotation angle in radians.
        Returns:
            np.ndarray: Rotated cuboid points.
        """
        if theta == 0:
            return self.cuboid_points3d
        rotz = np.array([[np.cos(theta),-np.sin(theta),0],
                        [np.sin(theta), np.cos(theta),0],
                        [            0,             0,1]])

        cuboid_points3d_rot = (rotz @ self.cuboid_points3d.T).T
        return cuboid_points3d_rot
    
    def get_cuboid_points_3d_world(self, theta:float = 0):
        """
        Returns the 3D cuboid points in world coordinates after rotation.
        Args:
            theta (float): Rotation angle in radians.
        Returns:
            np.ndarray: Rotated and translated cuboid points in world coordinates.
        """
        cuboid_points3d_rot = self.get_cuboid_points_3d_rotated(theta)
        cuboid_points3d_world = cuboid_points3d_rot + self.world_point.T
        return cuboid_points3d_world

    def get_cuboid_points_2d(self, theta:float = 0, calib=None):
        """
        Projects the cuboid's 3D points into the image plane.
        Args:
            theta (float): Rotation angle in radians.
            calib (CameraParams): Camera calibration (default: self.calib).
        Returns:
            list: List of 2D projected points.
        """
        if calib is None:
            calib = self.calib
        cuboid_points3d_world = self.get_cuboid_points_3d_world(theta)
        cuboid_points2d = get_projected_points(cuboid_points3d_world, calib)

        return cuboid_points2d

    def get_bbox(self, theta:float = 0, calib=None):
        """
        Returns the 2D bounding box of the projected cuboid in image space.
        Args:
            theta (float): Rotation angle in radians.
            calib (CameraParams): Camera calibration (default: self.calib).
        Returns:
            tuple: Top-left and bottom-right coordinates of the bounding box.
        """
        if calib is None:
            calib = self.calib
        cuboid_points2d = self.get_cuboid_points_2d(theta, calib)
        bbox = get_bounding_box(cuboid_points2d)
        return bbox


def get_ray_directions(points_2d:np.ndarray, calib):
    """
    Computes ray origins and directions in world coordinates for given 2D image points.
    Args:
        points_2d (np.ndarray): 2D image points (N, 2).
        calib (CameraParams): Camera calibration parameters.
    Returns:
        tuple: (ray_origins, ray_directions), each of shape (N, 3).
    """
    points_2d = np.array(points_2d, dtype=float).reshape(-1, 1, 2)

    # Vectorized undistortion
    undistorted_points = cv.undistortPoints(points_2d, calib.K, calib.dist, P=calib.K)
    undistorted_points = undistorted_points.reshape(-1, 2)

    # Homogeneous coordinates
    homogenous = np.hstack([undistorted_points, np.ones((len(undistorted_points), 1))])

    # Precompute matrices
    R_T = calib.R.T
    K_inv = np.linalg.inv(calib.K)
    ray_origin = (-R_T @ calib.T).flatten()

    # Compute ray directions
    temp = K_inv @ homogenous.T
    ray_directions = (R_T @ temp).T

    # Expand ray_origin to match number of points
    ray_origins = np.tile(ray_origin, (len(points_2d), 1))

    return ray_origins, ray_directions


def project_2d_points_to_mesh(points_2d, calib, mesh, VERBOSE=False, min_z=-4, max_z=1, min_cam_dist=1, z_plane=0.1):
    """
    Projects 2D image points to 3D mesh surface using ray-mesh intersection.
    If no intersection, projects to ground plane at z=z_plane.
    Args:
        points_2d (np.ndarray): 2D image points (N, 2).
        calib (CameraParams): Camera calibration parameters.
        mesh (trimesh.Trimesh): 3D mesh object.
        VERBOSE (bool): Print debug info.
        min_z (float): Minimum z for valid intersection.
        max_z (float): Maximum z for valid intersection.
        min_cam_dist (float): Minimum camera distance for valid intersection.
        z_plane (float): Fallback ground plane height.
    Returns:
        np.ndarray: 3D world coordinates (N, 3).
    """
    # Get ray origins and directions
    ray_origins, ray_directions = get_ray_directions(points_2d, calib)
    
    # Perform ray-mesh intersections
    locations, index_ray, index_tri = mesh.ray.intersects_location(
        ray_origins=ray_origins,
        ray_directions=ray_directions,
        multiple_hits=True
    )

    num_rays = len(ray_origins)
    ground_points = np.full((num_rays, 3), None)  # Initialize with None to allow filtering

    # Check if there are no intersections
    if len(locations) == 0:
        if VERBOSE:
            print(f"No intersections found for any rays. Projecting to groundplane. (z={z_plane})")
        ground_points = reproject_to_world_ground_batched(points_2d, calib.K, calib.R, calib.T, calib.dist, z_plane)
        
        return ground_points#.tolist()

    # Cache variables to reduce attribute lookups
    R, T = calib.R, calib.T.reshape(3, 1)
    camera_coords = - (R @ locations.T) - T
    depths = np.abs(camera_coords[2, :])

    if VERBOSE:
        print(f"Depths sample: {depths[:5]}")

    # Use NumPy to efficiently process the intersections

    # Filter intersections by depth and z-coordinates in a single pass
    valid_mask = (depths > min_cam_dist) & (locations[:, 2] < max_z) #& (locations[:, 2] > min_z)
    
    if VERBOSE: 
        print(f"ALL points: {locations}")
        print(f"Valid points: {locations[valid_mask]}")

    # Get valid indices per ray
    valid_indices = index_ray[valid_mask]
    valid_depths = depths[valid_mask]
    valid_points = locations[valid_mask]

    # Group and find the closest point for each ray
    if len(valid_indices) > 0:
        unique_rays, inverse_indices = np.unique(valid_indices, return_inverse=True)
        
        # For each unique ray, find the minimum depth and corresponding point
        min_depths_per_ray = np.full(num_rays, np.inf)
        closest_points = np.full((num_rays, 3), None)
        
        for i, ray_idx in enumerate(unique_rays):
            # Get depths and points for the current ray
            ray_depths = valid_depths[inverse_indices == i]
            ray_points = valid_points[inverse_indices == i]

            # Find the closest point based on minimum depth
            closest_idx = np.argmin(ray_depths)
            closest_points[ray_idx] = ray_points[closest_idx]
        
        # Assign only those rays that had valid intersections
        ground_points[unique_rays] = closest_points[unique_rays]
    else:
        if VERBOSE:
            print(f"No valid intersections after filtering. Projecting to groundplane. (z={z_plane})")
        ground_points = reproject_to_world_ground_batched(points_2d, calib.K, calib.R, calib.T, calib.dist, z_plane)

    if VERBOSE:
        print(f"Ground points: {ground_points}")
    
    return ground_points#.tolist()


def find_nearest_using_intersection(point_3d, mesh):
    """
    Finds the nearest intersection of a vertical ray from a 3D point with a mesh.
    Args:
        point_3d (np.ndarray): 3D point (x, y, z).
        mesh (trimesh.Trimesh): 3D mesh object.
    Returns:
        np.ndarray: Intersection point(s) or original point if no intersection.
    """
    #Generate ray assuming vertical ray comming straight down with x,y coordinates of 3d_point
    ray_origin = np.array([[point_3d[0], point_3d[1], 2]])
    ray_direction = np.array([[0, 0, -1]])
    #Find intersection with mesh

    locations, index_ray, index_tri = mesh.ray.intersects_location(
        ray_origins=ray_origin,
        ray_directions=ray_direction,
        multiple_hits=False
    )

    # Check if there are no intersections
    if len(locations) == 0:
        return point_3d.reshape(-1, 3)
    # Return the closest point and distance

    return locations

def move_with_mesh_intersection(ground_pix, use_intersection=True): #reproject to mesh
    """
    Projects a 3D point to the closest point on the mesh surface.
    Args:
        ground_pix (np.ndarray): 3D point(s) to project.
        use_intersection (bool): Use ray intersection or nearest surface.
    Returns:
        np.ndarray: Closest point(s) on the mesh.
    """
    if settings.FLAT_GROUND:
        return ground_pix
    else:
        mesh = settings.MESH
        
        if use_intersection:
            ground_pixel = find_nearest_using_intersection(ground_pix.squeeze(), mesh)
        else:
            # Use the nearest point function of trimesh
            closest_point, distance, _ = mesh.nearest.on_surface(ground_pix.reshape(-1, 3))
            ground_pixel = closest_point
    # Return the closest point and distance
    return ground_pixel


def project_world_to_camera(world_point, K1, R1, T1, dist=None):
    """
    Project a 3D world point to 2D image coordinates using camera parameters.
    Args:
        world_point (np.ndarray): 3D world point.
        K1 (np.ndarray): Camera intrinsic matrix.
        R1 (np.ndarray): Rotation matrix.
        T1 (np.ndarray): Translation vector.
        dist (np.ndarray): Distortion coefficients (optional).
    Returns:
        np.ndarray: 2D projected point in pixel coordinates.
    """
    # Reshape point to 1x3 array
    world_point = np.array(world_point, dtype=np.float32).reshape(1, 3)
    
    # Convert rotation matrix to rodrigues vector
    rvec, _ = cv.Rodrigues(R1)
    
    # Project points using cv2.projectPoints
    projected_points, _ = cv.projectPoints(world_point, rvec, T1, K1, dist)
    
    # Return 2D point
    return projected_points.reshape(-1, 2).T.astype(float)

def get_projected_points(points3d, 
                         calib:CameraParams, 
                         ):
    """
    Projects 3D points into the image plane and filters non-visible points.
    Args:
        points3d (np.ndarray): 3D points (N, 3).
        calib (CameraParams): Camera calibration parameters.
    Returns:
        list: List of 2D projected points.
    """
    undistort = settings.UNDISTORTED_FRAMES
    points3d = np.array(points3d).reshape(-1, 3)
    # Project visible points
    if undistort:
        points2d = [project_world_to_camera(point3d, calib.newCameraMatrix, calib.R, calib.T) for point3d in points3d]
    else:
        points2d = [project_world_to_camera(point3d, calib.K, calib.R, calib.T, calib.dist) for point3d in points3d]
    points2d = np.squeeze(points2d)

    if len(points2d.shape) == 1:
        points2d = points2d.reshape(-1, 2)
    
    points2d = [tuple(p) for p in points2d]
    return points2d


def get_cuboid2d_from_annotation(annotation, cam_name, undistort=False):
    """
    Computes the 2D cuboid projection for an annotation and camera.
    Args:
        annotation: Annotation object with 3D info.
        cam_name (str): Camera name.
        undistort (bool): Use undistorted frames.
    Returns:
        list or None: 2D cuboid points or None if not visible.
    """
    calib = settings.CALIBS[cam_name]
    height= annotation.object_size_x
    width = annotation.object_size_y
    length = annotation.object_size_z
    theta = annotation.rotation_theta
    world_point = annotation.world_point
    if world_point is None or np.any(np.isnan(world_point)):
        return None
    
    # check that world point is in fov
    if not is_visible(world_point, cam_name, check_mesh=True):
        return None
    

    cuboid = Cuboid(calib, world_point, width = width, length = length, height = height)
    cuboid_points2d = cuboid.get_cuboid_points_2d(theta)

    return cuboid_points2d


from shapely.geometry import Point, Polygon


def get_polygon_from_points_3d(points_3d):
    """
    Create a 2D polygon from a list of 3D points (using x, y only).
    Args:
        points_3d (list): List of 3D points.
    Returns:
        Polygon: Shapely 2D polygon.
    """
    polygon_points = [(point[0], point[1]) for point in points_3d]
    return Polygon(polygon_points)


def is_point_in_polygon(polygon, test_point):
    """
    Check if a 2D point is inside or on the boundary of a polygon.
    Args:
        polygon (Polygon): Shapely polygon.
        test_point (np.ndarray): 2D or 3D point.
    Returns:
        bool: True if inside or on boundary, False otherwise.
    """
    test_point = np.array(test_point).flatten()
    test_point_2d = Point(test_point[0], test_point[1])
    # Check if point is inside or on boundary
    return polygon.contains(test_point_2d) or polygon.touches(test_point_2d)

def is_visible(point3d:np.ndarray, cam_name:str, check_mesh:bool = True) -> bool:
    """
    Checks if a 3D point is visible in the camera frame, optionally considering mesh occlusion.
    Args:
        point3d (np.ndarray): 3D point.
        cam_name (str): Camera name.
        check_mesh (bool): Whether to check mesh occlusion.
    Returns:
        bool: True if visible, False otherwise.
    """
    calib = settings.CALIBS[cam_name]
    
    point3d = np.array(point3d).reshape(-1, 3)
    camera_position = (-calib.R.T @ calib.T).flatten()
    ray_to_point = point3d - camera_position

    # check behind camera
    if np.dot(ray_to_point, calib.R[2]) < 0:
        return False
    
    # check if point in ROI
    if settings.ROI:
        polygon = settings.ROI[cam_name]
        if not is_point_in_polygon(polygon, point3d):
            return False
        
    
    # Check if there’s an intersection between the ray and the mesh
    if settings.MESH is not None and check_mesh:
        # Get intersection locations with the mesh
        locations, _, _ = settings.MESH.ray.intersects_location(
            ray_origins=np.array(camera_position), 
            ray_directions=np.array(ray_to_point)
        )
        
        if len(locations) > 0:
            distance_to_point_sq = np.dot(ray_to_point, ray_to_point)
            distance_to_intersection_sq = min(
                np.dot(location - camera_position, location - camera_position) 
                for location in locations
            )

            # If there’s an intersection closer than the point, return False
            if distance_to_intersection_sq < distance_to_point_sq:
                print(f"Point {point3d} is not visible due to mesh intersection.")
                return False

            
    # If no intersection occurs before the point, return True
    return True




def get_bounding_box(points):
    """
    Compute the axis-aligned bounding box for a set of 2D points.
    Args:
        points (array-like): 2D points.
    Returns:
        tuple: Top-left and bottom-right coordinates of the bounding box.
    """
    points = points.copy()
    try:
        points = np.array(points, dtype=np.int64).reshape(-1, 1, 2)
        x, y, w, h = cv.boundingRect(points)
    except OverflowError:
        return points[0], points[4]
    return  (x, y), (x+w, y+h)


def reproject_to_world_ground_batched(ground_pix, K0, R0, T0, dist=None, height=0):
    """
    Compute world coordinates from pixel coordinates of points on a plane at specified height.
    Args:
        ground_pix (array-like): Pixel coordinates (N,2) or (N,3).
        K0 (array-like): Camera intrinsic matrix.
        R0 (array-like): Camera rotation matrix.
        T0 (array-like): Camera translation vector.
        dist (array-like): Distortion coefficients (optional).
        height (float): Height of the plane in world coordinates.
    Returns:
        np.ndarray: 3D world coordinates (N,3).
    """
    # Convert ground_pix to homogeneous coordinates if needed
    if dist is not None:
        undistorted_points = cv.undistortPoints(np.array(ground_pix, dtype=np.float32), K0, dist, P=K0)
        undistorted_points = undistorted_points.reshape(-1, 2)
        ground_pix = undistorted_points

    if ground_pix.shape[1] == 2:
        ground_pix_hom = np.hstack((ground_pix, np.ones((ground_pix.shape[0], 1))))
    else:
        ground_pix_hom = ground_pix
        
    # Transpose to 3xN for matrix operations
    ground_pix_hom = ground_pix_hom.T
        
    C0 = -R0.T @ T0
    
    K0_inv = np.linalg.inv(K0)
    
    l = R0.T @ K0_inv @ ground_pix_hom
    
    # Calculate the scaling factor to reach the specified height
    scale = (height - C0[2]) / l[2,:]
    
    # Reshape scale to broadcast correctly
    scale = scale.reshape(-1)
    
    # Broadcast C0 to match dimensions
    C0_expanded = np.repeat(C0[:,np.newaxis], ground_pix_hom.shape[1], axis=1).reshape(3, -1)
    
    world_points = C0_expanded + l * scale
    
    # Transpose back to Nx3
    return world_points.T


from dataclasses import dataclass
from typing import Union, Tuple, List
@dataclass
class Trajectory:
    coordinates:np.ndarray
    frame_start:int
    frame_end:int
    view_id:Union[int, Tuple[int, int]]
    camera:str
    person_id:int = None
    calibration:Calibration = None


def point_ground_bounding_box(ground_point, height, radius, calibration):
    # Unpack calibration parameters
    K = calibration.K  # Intrinsic matrix
    R = calibration.R  # Rotation matrix 
    T = calibration.T  # Translation vector

    # Get camera position in world coordinates
    camera_pos = -R.T @ T.squeeze()
    
    # Get vector from ground point to camera (projected onto ground plane)
    to_camera = camera_pos[:2] - ground_point[:2]
    to_camera = to_camera / np.linalg.norm(to_camera)
    
    # Get perpendicular vector in ground plane
    perp_vector = np.array([-to_camera[1], to_camera[0]])

    # Define corners that form a rectangle oriented towards camera
    corners_ground = []
    # Front corners (closer to camera)
    front_center = ground_point[:2] + radius * to_camera
    corners_ground.append(np.array([front_center[0] + radius * perp_vector[0], 
                                  front_center[1] + radius * perp_vector[1], 0]))
    corners_ground.append(np.array([front_center[0] - radius * perp_vector[0],
                                  front_center[1] - radius * perp_vector[1], 0]))
    
    # Back corners (farther from camera) 
    back_center = ground_point[:2] - radius * to_camera
    corners_ground.append(np.array([back_center[0] + radius * perp_vector[0],
                                  back_center[1] + radius * perp_vector[1], 0]))
    corners_ground.append(np.array([back_center[0] - radius * perp_vector[0],
                                  back_center[1] - radius * perp_vector[1], 0]))

    # Add top corners
    corners_top = []
    for corner in corners_ground:
        corners_top.append(np.array([corner[0], corner[1], height]))

    all_corners = corners_ground + corners_top

    def project_to_image(world_point, K1, R1, T1):
        """
        Project 3D world coordinate point to image plane (pixel coordinate)
        """
        point1 = ((R1 @ world_point) + T1.squeeze())
        if point1[2] < 0:
            raise ValueError("World point is located behind the camera plane")
        point1 = K1 @ point1
        point1 = point1 / point1[2]
        return point1[:2]

    # Project all corners to image space
    image_points = []
    for corner in all_corners:
        try:
            image_point = project_to_image(corner, K, R, T)
            image_points.append(image_point)
        except ValueError:
            continue

    if not image_points:
        raise ValueError("No corners could be projected to image plane")
        
    image_points = np.array(image_points)

    # Find min/max x and y coordinates to create bounding box
    bbox_x_min = int(np.min(image_points[:,0]))
    bbox_x_max = int(np.max(image_points[:,0]))
    bbox_y_min = int(np.min(image_points[:,1])) 
    bbox_y_max = int(np.max(image_points[:,1]))

    # Bounding box in image coordinates
    bbox = (bbox_x_min, bbox_y_min, bbox_x_max, bbox_y_max)

    return bbox


def merge_trajectory_group(trajectories:List[Trajectory], merging_strategy="mean"):
    """Merge multiple 3D trajectories based on the specified merging strategy.
    
    Args:
        trajectories: List of trajectories to merge
        calibrations: Dictionary mapping camera IDs to calibration objects
        merging_strategy: Strategy to merge overlapping coordinates
    
    Returns:
        Tuple containing:
        - Merged trajectory with combined coordinates
        - Dictionary mapping camera IDs to lists of bounding boxes
    """
    # Get overall frame range
    start_frame = min(traj.frame_start for traj in trajectories)
    end_frame = max(traj.frame_end for traj in trajectories)
    
    # Initialize merged coordinates and bbox dictionary
    merged_coords = []
    bboxes = {traj.camera: [] for traj in trajectories}
    
    for frame in range(start_frame, end_frame + 1):
        # Get coordinates from all trajectories that have this frame
        frame_coords = []
        cam_positions = []
        directions = []
        
        for traj in trajectories:
            idx = frame - traj.frame_start
            if 0 <= idx < len(traj.coordinates):
                coord = traj.coordinates[idx]
                calib = traj.calibration
                cam_pos = -calib.R.T @ calib.T.squeeze()
                
                frame_coords.append(coord)
                cam_positions.append(cam_pos)
                directions.append(coord - cam_pos)
        
        if frame_coords:
            if merging_strategy == "mean":
                merged_coord = np.mean(frame_coords, axis=0)
                
            elif merging_strategy == "camera_mean_top":
                ground_points = []
                for cam_pos, direction in zip(cam_positions, directions):
                    t = -cam_pos[2] / direction[2]
                    ground_points.append(cam_pos + t * direction)
                merged_coord = np.mean(ground_points, axis=0)
                
            else:  # camera_mean
                closest_points = []
                for i, (cam_pos1, dir1) in enumerate(zip(cam_positions, directions)):
                    dir1 = dir1 / np.linalg.norm(dir1)
                    for cam_pos2, dir2 in zip(cam_positions[i+1:], directions[i+1:]):
                        dir2 = dir2 / np.linalg.norm(dir2)
                        
                        n = np.cross(dir1, dir2)
                        n1 = np.cross(dir1, n)
                        n2 = np.cross(dir2, n)
                        
                        c1 = cam_pos1 + (np.dot((cam_pos2 - cam_pos1), n2) / np.dot(dir1, n2)) * dir1
                        c2 = cam_pos2 + (np.dot((cam_pos1 - cam_pos2), n1) / np.dot(dir2, n1)) * dir2
                        
                        closest_points.extend([c1, c2])
                
                merged_coord = np.mean(closest_points, axis=0) if closest_points else np.mean(frame_coords, axis=0)
            
            merged_coords.append(merged_coord)
            
            # # Calculate bounding boxes for all cameras
            # for camera_id, calib in calibrations.items():
            #     bbox = point_ground_bounding_box(merged_coord, 1.6, 0.25, calib)
            #     bboxes[camera_id].append(bbox)
    
    # Create merged trajectory
    merged_trajectory = Trajectory(
        coordinates=np.array(merged_coords),
        frame_start=start_frame,
        frame_end=end_frame,
        view_id=tuple(traj.view_id for traj in trajectories),
        camera=trajectories[0].camera,
        person_id=next((traj.person_id for traj in trajectories if traj.person_id is not None), None),
        calibration=trajectories[0].calibration
    )
    
    return merged_trajectory#, bboxes
