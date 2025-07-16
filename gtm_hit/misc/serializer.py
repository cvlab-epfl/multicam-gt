from ..models import Annotation2DView

def serialize_annotation2dviews(queryset):
    serialized_data = []
    for atdv in queryset:
        cuboid = None
        if atdv.cuboid_points:
            cuboid = [atdv.cuboid_points[0:2],
                        atdv.cuboid_points[2:4],
                        atdv.cuboid_points[4:6],
                        atdv.cuboid_points[6:8],
                        atdv.cuboid_points[8:10],
                        atdv.cuboid_points[10:12],
                        atdv.cuboid_points[12:14],
                        atdv.cuboid_points[14:16],
                        atdv.cuboid_points[16:18],
                        atdv.cuboid_points[18:20],
                        ]
        ann = atdv.annotation
        serialized_view = {
            'rectangleID': ann.rectangle_id,
            'cameraID': atdv.view.view_id,
            'person_id': ann.person.person_id,  # Include the person_id
            'annotation_complete': ann.person.annotation_complete,
            'validated': ann.validated,
            'creation_method': ann.creation_method,
            'object_size': ann.object_size,
            'rotation_theta': ann.rotation_theta,
            'Xw': ann.Xw,
            'Yw': ann.Yw,
            'Zw': ann.Zw,
            'x1': atdv.x1,
            'y1': atdv.y1,
            'x2': atdv.x2,
            'xMid': atdv.x1+(atdv.x2-atdv.x1)/2,
            'y2': atdv.y2,
            'cuboid': cuboid,
            'frameID': ann.frame.frame_id,
        }
        serialized_data.append(serialized_view)
    return serialized_data


def serialize_frame_annotations(frame):
    annotations = (Annotation2DView.objects
        .filter(annotation__frame=frame)
        # .exclude(cuboid_points=None)
        .select_related('annotation', 'annotation__person', 'view', 'annotation__frame')
        .values(
            'annotation__rectangle_id',
            'view__view_id',
            'annotation__person__person_id',
            'annotation__person__annotation_complete',
            'annotation__validated',
            'annotation__creation_method',
            'annotation__object_size_x',
            'annotation__object_size_y',
            'annotation__object_size_z',
            'annotation__rotation_theta',
            'annotation__Xw',
            'annotation__Yw',
            'annotation__Zw',
            'x1', 'y1', 'x2', 'y2',
            'cuboid_points',
            'annotation__frame__frame_id'
        ))
    
    return [{
        'rectangleID': ann['annotation__rectangle_id'],
        'cameraID': ann['view__view_id'],
        'person_id': ann['annotation__person__person_id'],
        'annotation_complete': ann['annotation__person__annotation_complete'],
        'validated': ann['annotation__validated'],
        'creation_method': ann['annotation__creation_method'],
        'object_size': [ann['annotation__object_size_x'], 
                       ann['annotation__object_size_y'], 
                       ann['annotation__object_size_z']],
        'rotation_theta': ann['annotation__rotation_theta'],
        'Xw': ann['annotation__Xw'],
        'Yw': ann['annotation__Yw'],
        'Zw': ann['annotation__Zw'],
        'x1': ann['x1'],
        'y1': ann['y1'],
        'x2': ann['x2'],
        'xMid': ann['x1'] + (ann['x2'] - ann['x1'])/2,
        'y2': ann['y2'],
        'cuboid': [ann['cuboid_points'][i:i+2] for i in range(0, 20, 2)] if ann['cuboid_points'] else None,
        'frameID': ann['annotation__frame__frame_id'],
    } for ann in annotations]
