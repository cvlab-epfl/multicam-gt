import time
import os

import cv2
import numpy as np

from pathlib import Path
from django.conf import settings
from rtmlib import RTMPose, draw_skeleton

from .geometry import get_projected_points, project_2d_points_to_mesh, is_visible, find_nearest_using_intersection
from .geometry import Cuboid
from .utils import get_frame_path, get_frame, get_valid_cameras

def get_initial_point(points2d, frame_id, pose_model, camera_id, calibs, mesh):
    image = get_frame(frame_id, camera_id)

    ground_point = project_2d_points_to_mesh(points2d, calibs[camera_id], mesh)

    # Distance to camera
    camera_position = -np.dot(calibs[camera_id].R.T, calibs[camera_id].T).flatten()
    # Project camera position to ground plane (z=0)
    camera_ground_point = np.array([camera_position[0], camera_position[1], 0])
    # Calculate distance from foot point to camera ground position
    distance_to_camera = np.linalg.norm(ground_point - camera_ground_point)

    # Create a bounding box around the 2D points
    x, y = points2d.flatten()
    # Scale padding based on distance to camera
    base_vert_padding = 180
    base_hor_padding = 45
    base_below_feet_padding = 20
    
    # Apply scaling factor based on distance (farther objects need smaller padding)
    distance_scale = min(max(0.2, 1 / ((0.1 * distance_to_camera) + 1)), 1)

    vert_padding = int(base_vert_padding * distance_scale)
    hor_padding = int(base_hor_padding * distance_scale)
    below_feet_padding = int(base_below_feet_padding * distance_scale)
    # Assume point2d is bottom center of bbox, so add more padding above than below
    bbox = np.array([x - hor_padding, y - vert_padding, x + hor_padding, y + below_feet_padding])

    feet, feet_scores, keypoints, scores = get_feet_keypoints(image, [bbox], pose_model, return_all=True)

    feet_3d = np.vstack([project_2d_points_to_mesh([fp], calibs[camera_id], mesh) for fp in feet.squeeze()]).reshape(-1, 3)

    initial_point = np.mean(feet_3d, axis=0)

    return initial_point

def auto_align_bbox(ground_point, frame_id, pose_model, mesh, calibs, debug_visualization=False, kpts_threshold=0.4, points2d=None, camera_id=None, bbox_expansion=-0.05):

    start_time = time.time()
            
    nominal_height = settings.HEIGHT
    width = settings.RADIUS 
    depth = settings.RADIUS 

    init_point_time = 0
    if ground_point is None and points2d is not None and camera_id is not None:
        init_point_start = time.time()
        ground_point = get_initial_point(points2d, frame_id, pose_model, camera_id, calibs, mesh)
        # ground_point = project_2d_points_to_mesh(points2d, calibs[camera_id], mesh)
        init_point_time = time.time() - init_point_start
        print("ground point", ground_point)

    initial_cuboid = Cuboid(None, ground_point.squeeze(), width, depth, nominal_height)

    
    # For each camera view, reproject the cuboid and refine using detections
    all_feet_3d = []
    all_feet_weights = []
    all_feet_keypoints = []
    all_feet_scores = []
    all_calibs = []
    all_images = []

    keypoints_time = 0
    frame_loading_time = 0
    projection_time = 0
    debug_vis_time = 0
    
    # Create debug visualization directory if needed
    if debug_visualization:
        debug_dir = Path("test_visu_autoalign")
        debug_dir.mkdir(exist_ok=True)
    
    # Reproject in all the views and collect feet keypoints
    camera_processing_start = time.time()
    for camera_id in get_valid_cameras(calibs, frame_id, ground_point):
            
        calib = calibs[camera_id]
        
        # Get bounding box from reprojection
        bbox = np.hstack(initial_cuboid.get_bbox(calib=calib))
        # Apply bbox expansion
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        bbox[0] -= width * bbox_expansion
        bbox[1] -= height * bbox_expansion
        bbox[2] += width * bbox_expansion
        bbox[3] += height * bbox_expansion

        if bbox is None:
            continue
        
        frame_start = time.time()
        image = get_frame(frame_id, camera_id)
        frame_loading_time += time.time() - frame_start
        
        if image is None:
            continue
        
        # Get feet keypoints directly using the pose model
        keypoints_start = time.time()
        feet, feet_scores, keypoints, scores = get_feet_keypoints(image, [bbox], pose_model, return_all=True)
        keypoints_time += time.time() - keypoints_start


        filter_keypoints = [keypoints[0][i] for i in range(len(keypoints[0])) if scores[0][i] > kpts_threshold]
        filter_scores = [scores[0][i] for i in range(len(scores[0])) if scores[0][i] > kpts_threshold]


        # Project feet keypoints to 3D
        projection_start = time.time()
        feet_3d = np.vstack([project_2d_points_to_mesh([fp], calib, mesh) for fp in feet.squeeze()]).reshape(-1, 3) #project_2d_points_to_mesh(feet, calib, mesh)
        projection_time += time.time() - projection_start
        
        # Add valid feet points to our collection
        for i, point in enumerate(feet_3d):
            if point is not None and feet_scores[0][i] > kpts_threshold:
                all_feet_3d.append(point)

                # Get camera position from calibration
                # Camera position = -R^T * T (inverse rotation * translation)
                camera_position = -np.dot(calib.R.T, calib.T).flatten()
                # Project camera position to ground plane (z=0)
                camera_ground_point = np.array([camera_position[0], camera_position[1], 0])
                # Calculate distance from foot point to camera ground position
                try:
                    distance_to_camera = np.linalg.norm(point - camera_ground_point)
                    all_feet_weights.append(distance_to_camera)
                except Exception as e:
                    import pdb; pdb.set_trace()

        # Debug visualization
        if debug_visualization:
            debug_vis_start = time.time()
            debug_img = image.copy()
            
            # Draw bounding box
            cv2.rectangle(debug_img, 
                         (int(bbox[0]), int(bbox[1])), 
                         (int(bbox[2]), int(bbox[3])), 
                         (0, 0, 255), 2)  # Red for initial bbox
            
            # Draw filtered keypoints
            for keypoint in filter_keypoints:
                cv2.circle(debug_img, 
                          (int(keypoint[0]), int(keypoint[1])), 
                          3, (0, 255, 255), -1)  # Yellow for keypoints
            
            # Reproject and display all_feet_3d points
            if len(all_feet_3d) > 0:
                # Project 3D feet points back to 2D in this camera view
                feet_3d_reprojected = get_projected_points(np.array(all_feet_3d), calib)
                for foot_2d in feet_3d_reprojected:
                    if foot_2d is not None:
                        cv2.drawMarker(debug_img, 
                                      (int(foot_2d[0]), int(foot_2d[1])), 
                                      (255, 0, 0), cv2.MARKER_CROSS, 10)  # Blue X for reprojected feet
            
            # Add text with camera and frame info
            cv2.putText(debug_img, f"Camera {camera_id} - Frame {frame_id}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Save the debug image
            cv2.imwrite(str(debug_dir / f"debug_initial_{camera_id}_frame_{frame_id}.jpg"), debug_img)
            debug_vis_time += time.time() - debug_vis_start

        if len(filter_keypoints) == 0:
            print("No keypoints found for camera ", camera_id)
            continue
        
        all_calibs.append(calib)
        all_feet_keypoints.append(np.vstack(filter_keypoints))
        all_feet_scores.append(np.vstack(filter_scores))
        all_images.append(image)
    
    camera_processing_time = time.time() - camera_processing_start
    
    search_time = 0
    refinement_debug_time = 0
    
    # If we found feet keypoints across views, refine the cuboid
    if len(all_feet_3d) > 0:        
        search_start = time.time()


        refined_cuboid = search_best_cuboid(all_feet_3d, all_feet_weights, all_feet_scores, all_feet_keypoints, all_calibs, mesh, initial_point=ground_point)
        search_time = time.time() - search_start
        
        # Create debug visualization for refined cuboid
        if debug_visualization:
            refinement_debug_start = time.time()
            for idx, (camera_id, calib, image) in enumerate(zip(get_valid_cameras(calibs, frame_id, ground_point), all_calibs, all_images)):
                if idx >= len(all_images):
                    continue
                    
                debug_img = get_frame(frame_id, camera_id)
                calib = calibs[camera_id]
        
 
                
                # Draw initial bounding box
                initial_bbox = np.hstack(initial_cuboid.get_bbox(calib=calib))
                cv2.rectangle(debug_img, 
                             (int(initial_bbox[0]), int(initial_bbox[1])), 
                             (int(initial_bbox[2]), int(initial_bbox[3])), 
                             (0, 0, 255), 2)  # Red for initial bbox
                
                # Draw refined bounding box
                refined_bbox = np.hstack(refined_cuboid.get_bbox(calib=calib))
                cv2.rectangle(debug_img, 
                             (int(refined_bbox[0]), int(refined_bbox[1])), 
                             (int(refined_bbox[2]), int(refined_bbox[3])), 
                             (0, 255, 0), 2)  # Green for refined bbox
                
                print(initial_cuboid.world_point, refined_cuboid.world_point)
                # Project initial and refined world points to 2D
                initial_point_2d = get_projected_points(np.array([initial_cuboid.world_point]), calib)[0]
                refined_point_2d = get_projected_points(np.array([refined_cuboid.world_point]), calib)[0]

                print(initial_point_2d, refined_point_2d)
                
                # Draw the projected points
                if initial_point_2d is not None:
                    cv2.drawMarker(debug_img, 
                                  (int(initial_point_2d[0]), int(initial_point_2d[1])), 
                                  (0, 0, 255), cv2.MARKER_CROSS, 10)  # Red X for initial point
                
                if refined_point_2d is not None:
                    cv2.drawMarker(debug_img, 
                                  (int(refined_point_2d[0]), int(refined_point_2d[1])), 
                                  (0, 255, 0), cv2.MARKER_CROSS, 10)  # Green X for refined point
                
                # Add legend
                cv2.putText(debug_img, "Initial (Red)", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.putText(debug_img, "Refined (Green)", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(debug_img, f"Camera {camera_id} - Frame {frame_id}", (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Save the debug image
                cv2.imwrite(str(debug_dir / f"debug_refined_{camera_id}_frame_{frame_id}.jpg"), debug_img)
            refinement_debug_time = time.time() - refinement_debug_start
        
        end_time = time.time()
        total_time = end_time - start_time
        
        if debug_visualization:
            print(f"Auto align bbox timing:")
            print(f"  - Initial point calculation: {init_point_time:.3f} seconds")
            print(f"  - Frame loading: {frame_loading_time:.3f} seconds")
            print(f"  - Keypoint detection: {keypoints_time:.3f} seconds")
            print(f"  - 3D projection: {projection_time:.3f} seconds")
            print(f"  - Debug visualization: {debug_vis_time:.3f} seconds")
            print(f"  - Refinement debug visualization: {refinement_debug_time:.3f} seconds")
            print(f"  - Total time: {total_time:.3f} seconds")

        return refined_cuboid.world_point
    else:
        # If no feet keypoints found, return the original cuboid
        print("failed to refine cuboid")
        
        return initial_cuboid.world_point


def get_pose_model(model_type="light", device="cpu"):
    backend = 'onnxruntime'
    openpose_skeleton = False

    if model_type == "light":
        model_path = 'https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-t_simcc-body7_pt-body7-halpe26_700e-256x192-6020f8a6_20230605.zip'
        model_input_size = (192, 256)

    elif model_type == "performance":
        model_path = 'https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-x_simcc-body7_pt-body7-halpe26_700e-384x288-7fb6e239_20230606.zip'
        model_input_size = (288, 384)

    pose_model = RTMPose(model_path,
                        model_input_size=model_input_size,
                        to_openpose=openpose_skeleton,
                        backend=backend,
                        device=device)

    return pose_model

def get_feet_keypoints(img, bboxes, pose_model, return_all=False):
    """
    Extract left and right foot keypoints from an image using pose estimation
    
    Args:
        img: Input image
        bboxes: Bounding boxes for detection
        
    Returns:
        tuple: (feet, feet_scores) where feet has shape (num_people, 4, 2) and 
               feet_scores has shape (num_people, 4)
    """
    keypoints, scores = pose_model(img, bboxes=bboxes)
    
    # Get indices for feet keypoints
    feet_indices = [23, 25, 22, 24]  # right_tip, right_heel, left_tip, left_heel
    
    # Stack the feet keypoints for each person
    # This creates arrays of shape (num_people, 4, 2) for feet and (num_people, 4) for scores
    feet = np.stack([keypoints[:, idx, :] for idx in feet_indices], axis=1)
    feet_scores = np.stack([scores[:, idx] for idx in feet_indices], axis=1)
    
    if return_all:
        return feet, feet_scores, keypoints, scores
    else:
        return feet, feet_scores


def evaluate_bboxes(bboxes, dist_to_camera, keypoints, kpts_scores):
    # Compute metrics to incentivize all keypoints to be inside the bbox and the bbox to be as small as possible
    total_area = 0
    penalty = 0
    centering_penalty = 0

    for bbox, kps, dist, kpts_scores in zip(bboxes, keypoints, dist_to_camera, kpts_scores):
        if bbox is None:
            continue
            
        # Calculate bbox area
        (x1, y1), (x2, y2) = bbox
        area = (x2 - x1) * (y2 - y1)
        total_area += area
        
        # Calculate bbox center
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # Check if keypoints are inside the bbox
        for kp, kpts_score in zip(kps, kpts_scores):

            x, y = kp
            if x < x1 or x > x2 or y < y1 or y > y2:
                # Add penalty for keypoints outside the bbox
                dx = max(0, x1 - x, x - x2) / (x2 - x1)
                dy = max(0, y1 - y, y - y2) / (y2 - y1)
                penalty += (dx**2 + dy**2) #* kpts_score * ((1 / dist) ** 2)
            
            # Add centering penalty - distance from keypoint to center of bbox
            dx = (x - center_x) #/ (x2 - x1)
            # dy = (y - center_y) / (y2 - y1)
            centering_penalty += (dx**2) #* kpts_score * ((1 / dist) ** 2)

        centering_penalty = centering_penalty / len(kps)

        penalty = penalty / len(kps)
    return centering_penalty

def search_best_cuboid(all_feet_3d, all_feet_dist_to_camera, all_feet_scores, all_feet_keypoints, all_calibs, mesh, initial_point=None, grid_interval=0.06, padding=0.35):
       
    # Convert to numpy array if it's not already
    all_feet_3d_array = np.array(all_feet_3d)
    
    if initial_point is None:
        # Use median of feet points
        pass
    else:
        # Add initial_point multiple times to bias the median calculation
        # Add it 5 times to give it significant weight without overwhelming actual data
        for _ in range(3):
            all_feet_3d_array = np.vstack([all_feet_3d_array, initial_point])
    # print(all_feet_3d_array.shape)
    
    # Check if we have any points
    if len(all_feet_3d_array) == 0 or all_feet_3d_array.size == 0:
        return None
    
    # Handle the case where all_feet_3d might contain a single float
    if np.isscalar(all_feet_3d_array) or all_feet_3d_array.ndim < 2:
        return None
    
    # Extract x, y, z coordinates using numpy
    all_x = all_feet_3d_array[:, 0]
    all_y = all_feet_3d_array[:, 1]
    all_z = all_feet_3d_array[:, 2]
    
    # Calculate median for each axis
    median_x = np.median(all_x)
    median_y = np.median(all_y)
    median_z = np.median(all_z)

    
    # Create grid by adding padding around the median points
    min_x, max_x = median_x - padding, median_x + padding
    min_y, max_y = median_y - padding, median_y + padding
    
    # Create a grid of points around the median with the given interval and padding
    x_range = np.arange(min_x, max_x + grid_interval, grid_interval)
    y_range = np.arange(min_y, max_y + grid_interval, grid_interval)
    
    grid_points = []
    for x in x_range:
        for y in y_range:
            grid_points.append([x, y, median_z])
    
    ground_pix = np.array(grid_points)

    # print(ground_pix.shape)
    
    if False:
        print(f"Total number of grid points: {len(grid_points)}")
        # Project the grid points to mesh.
        start_time_nearest = time.time()
        closest_points, _, _ = mesh.nearest.on_surface(ground_pix.reshape(-1, 3))
        nearest_time = time.time() - start_time_nearest
        print(f"  - Mesh nearest.on_surface: {nearest_time:.3f} seconds")
    else:
        closest_points = ground_pix.reshape(-1, 3)
    
    # for each grid point on grid create a cuboid project it to 2d using all calibs
    best_score = float('inf')
    best_cuboid = None
    nominal_height = settings.HEIGHT
    width = settings.RADIUS
    depth = settings.RADIUS 
    
    for i, point in enumerate(closest_points):

        cuboid = Cuboid(None, point.squeeze(), width, depth, nominal_height)
        
        # Project cuboid to all camera views
        bboxes = []
        dist_to_camera = []
        for calib in all_calibs:
            bbox = cuboid.get_bbox(calib=calib)
            bboxes.append(bbox)

            # Calculate distance to camera
            camera_position = -np.dot(calib.R.T, calib.T).flatten()
            distance_to_camera = np.linalg.norm(point - camera_position)
            dist_to_camera.append(distance_to_camera)
        
        # evaluate the reprojection bboxes with respect to keypoints using the function evaluate_bboxes
        score = evaluate_bboxes(np.array(bboxes), dist_to_camera, all_feet_keypoints, all_feet_scores)
        
        if score < best_score:
            best_score = score
            best_cuboid = cuboid

    best_cuboid.world_point = find_nearest_using_intersection(best_cuboid.world_point.squeeze(), mesh).squeeze()

    # return the grid point with the best score
    return best_cuboid



def add_reproj_feet_keypoints(all_feet_3d, all_feet_keypoints, all_calibs):
    """
    Filter 3D feet points to remove outliers and add reprojected 2D keypoints to all_feet_keypoints.
    
    Args:
        all_feet_3d: List of 3D feet points
        all_feet_keypoints: List of 2D keypoints for each camera view
        all_calibs: List of camera calibration objects
        
    Returns:
        Updated all_feet_keypoints with reprojected points added
    """
    if not all_feet_3d or len(all_feet_3d) == 0:
        return all_feet_keypoints
    
    # Convert to numpy array for easier processing
    feet_3d_array = np.array(all_feet_3d).astype(np.float32)
    feet_3d_array = feet_3d_array.reshape(-1, 3)
    
    # Filter outliers using distance from median
    if len(feet_3d_array) > 3:  # Only filter if we have enough points
        median_point = np.median(feet_3d_array, axis=0)
        distances = np.sqrt(np.array(np.sum((feet_3d_array - median_point)**2, axis=1)))
        
        # Use median absolute deviation to determine outliers
        mad = np.median(np.abs(distances - np.median(distances)))
        threshold = 2.5 * mad  # Adjust this threshold as needed
        
        # Keep points within threshold
        filtered_feet_3d = feet_3d_array[distances <= threshold]
    else:
        filtered_feet_3d = feet_3d_array
    
    # Create a copy of the input keypoints list to avoid modifying the original
    updated_keypoints = []
    for kps in all_feet_keypoints:
        if kps is not None:
            # Convert to numpy array if it's not already
            if isinstance(kps, list):
                updated_keypoints.append(np.array(kps))
            else:
                updated_keypoints.append(kps.copy())
        else:
            updated_keypoints.append(np.empty((0, 2)))
    
    # Reproject filtered 3D points to each camera view
    for i, calib in enumerate(all_calibs):
        if i >= len(updated_keypoints):
            continue
            
        # Project each filtered 3D point to 2D in this camera view
        reprojected_points = []
        for point_3d in filtered_feet_3d:
            # Get 2D projection
            point_2d = get_projected_points([point_3d], calib)
            
            # Add to reprojected points if the point is valid
            if point_2d and len(point_2d) > 0:
                reprojected_points.extend(point_2d)
        
        # Convert reprojected points to numpy array and concatenate with existing keypoints
        if reprojected_points:
            reprojected_array = np.array(reprojected_points)
            updated_keypoints[i] = np.vstack([updated_keypoints[i], reprojected_array])
    
    return updated_keypoints