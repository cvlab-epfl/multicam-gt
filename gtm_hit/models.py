"""
GTM Hit Models - Database Models for Multi-View Annotation System

This module defines the database models for the GTM Hit annotation system,
including workers, datasets, frames, annotations, and validation codes.
"""

import json
import numpy as np
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

class Worker(models.Model):
    """
    Represents an annotation worker.
    
    Tracks worker progress through the annotation workflow with states:
    -1: Initial/Reset, 0: Introduction, 1: Annotation, 2: Completion, 3: Tutorial
    """
    workerID = models.TextField(primary_key=True, max_length=40)
    frameNB = models.IntegerField(default=-1)
    frame_labeled = models.PositiveSmallIntegerField(default=0)
    finished = models.BooleanField(default=False)
    state = models.IntegerField(default=-1)
    tuto = models.BooleanField(default=False)
    time_list = models.TextField(default="")
    
    def increaseFrame(self, val):
        """Increase the number of labeled frames."""
        self.frame_labeled = self.frame_labeled + val
        
    def decreaseFrame(self, val):
        """Decrease the number of labeled frames."""
        self.frame_labeled = self.frame_labeled - val
        
    def setTimeList(self, x):
        """Set the time list as JSON string."""
        self.time_list = json.dumps(x)
        
    def getTimeList(self):
        """Get the time list from JSON string."""
        return json.loads(self.time_list)
        
    def __str__(self):
        return 'Worker: ' + self.workerID
    
class ValidationCode(models.Model):
    validationCode = models.TextField(primary_key=True)
    worker = models.OneToOneField('Worker',on_delete=models.CASCADE)
    
    def __str__(self):
        return 'Code: ' + self.worker.workerID
    
class Dataset(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Dataset: {self.name}"

class Person(models.Model):
    person_id = models.IntegerField(verbose_name="PersonID")
    annotation_complete = models.BooleanField(default=False)
    worker = models.ForeignKey(Worker,on_delete=models.CASCADE)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE,default=1)
    class Meta:
        unique_together = ('person_id', 'worker', 'dataset')
    def __str__(self):
        return f"pID:{self.person_id} wID:{self.worker.workerID} ds:{self.dataset.name}"
    def __repr__(self):
        return f"pID:{self.person_id} wID:{self.worker.workerID} ds:{self.dataset.name}"
    
class MultiViewFrame(models.Model):
    frame_id = models.IntegerField(verbose_name="MultiView ID")
    timestamp = models.DateTimeField(default=timezone.now)
    undistorted = models.BooleanField(default=False)
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE,default="IVAN")
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE,default=1)

    class Meta:
        unique_together = ('frame_id', 'undistorted', 'worker', 'dataset')
    def __str__(self):
        return f"{'UN' if self.undistorted else ''}DMVF{self.frame_id} wID:{self.worker.workerID} ds:{self.dataset.name}"
    
class View(models.Model):
    view_id = models.IntegerField(primary_key=True,verbose_name="View ID")
    def __str__(self):
        return f"CAM{self.view_id+1}"
        # return f"CAM{self.view_id}"
    
class Annotation(models.Model):
    frame = models.ForeignKey(MultiViewFrame, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    creation_method = models.TextField(default="existing_annotation")
    validated = models.BooleanField(default=True)
    locked = models.BooleanField(default=False)  # New field to lock the annotation
    class Meta:
        unique_together = ('frame', 'person')
    rectangle_id = models.CharField(max_length=100)
    
    rotation_theta = models.FloatField()
    Xw = models.FloatField(verbose_name="X World Coordinate")
    Yw = models.FloatField(verbose_name="Y World Coordinate")
    Zw = models.FloatField(verbose_name="Z World Coordinate")

    object_size_x = models.FloatField()
    object_size_y = models.FloatField()
    object_size_z = models.FloatField()
    
    @property
    def object_size(self):
        return [self.object_size_x, self.object_size_y, self.object_size_z]

    @property
    def world_point(self):
        return np.array([self.Xw, self.Yw, self.Zw]).reshape(-1,1)

    def __str__(self):
        assert self.person.worker.workerID == self.frame.worker.workerID
        assert self.person.dataset.name == self.frame.dataset.name
        return f"{'UN' if self.frame.undistorted else ''}DMVF{self.frame.frame_id} pID{self.person.person_id} wID:{self.person.worker.workerID} ds:{self.person.dataset.name}"
    
class Annotation2DView(models.Model):
    view = models.ForeignKey(View, on_delete=models.CASCADE)
    annotation = models.ForeignKey(Annotation, related_name="twod_views", on_delete=models.CASCADE)
    locked = models.BooleanField(default=False)  # New field to lock the 2D annotation
    class Meta:
        unique_together = ('view', 'annotation')
    x1 = models.FloatField(null=True)
    y1 = models.FloatField(null=True)
    x2 = models.FloatField(null=True)
    y2 = models.FloatField(null=True)
    cuboid_points = ArrayField(models.FloatField(), size=20, null=True)

    @property
    def cuboid_points_2d(self):
        return [
            self.cuboid_points[0:2],
            self.cuboid_points[2:4],
            self.cuboid_points[4:6],
            self.cuboid_points[6:8],
            self.cuboid_points[8:10],
            self.cuboid_points[10:12],
            self.cuboid_points[12:14],
            self.cuboid_points[14:16],
            self.cuboid_points[16:18],
            self.cuboid_points[18:20],
        ]

    def set_cuboid_points_2d(self, points):
        self.cuboid_points = [point for sublist in points for point in sublist]

    def __str__(self):
        return f"{'UN' if self.annotation.frame.undistorted else ''}DF{self.annotation.frame.frame_id} CAM{self.view.view_id+1} pID{self.annotation.person.person_id} rID{self.annotation.rectangle_id}"

class SingleViewFrame(models.Model):
    frame_id = models.IntegerField(verbose_name="SingleView ID")
    timestamp = models.DateTimeField(default=timezone.now)
    view = models.ForeignKey(View, on_delete=models.CASCADE)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, default=1)
    def __str__(self):
        return f"CAM{self.view_id+1} SVFRAME{self.frame_id} {self.timestamp}" 