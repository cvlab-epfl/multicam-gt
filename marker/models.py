from django.db import models
from django.core.validators import validate_comma_separated_integer_list

# class Annotation(models.Model):
#
#     frame_number = models.PositiveIntegerField(default=0)
#     rectangleID = models.PositiveIntegerField(default=0)
#     personID = models.PositiveSmallIntegerField(default=0)
#     modified_flag = models.BooleanField(default=False)
#     coordinates = models.CharField(max_length=180,validators=[validate_comma_separated_integer_list])
#
# # class Rectangle(models.Model):
# #     cameraID = models.PositiveSmallIntegerField(default=0)
# #     rectangleID = models.PositiveIntegerField(default=0)
# #     x1 = models.PositiveSmallIntegerField(default=0)
# #     y1 = models.PositiveSmallIntegerField(default=0)
# #     x2 = models.PositiveSmallIntegerField(default=0)
# #     y2 = models.PositiveSmallIntegerField(default=0)
# #     xMid = models.PositiveSmallIntegerField(default=0)
#
#
# class Worker(models.Model):
#
#     workerID = models.PositiveIntegerField(primary_key=True)
#     frameNB = models.PositiveSmallIntegerField(default=0)
#     #validationoCode = models.PositiveIntegerField(default=0)
#     finished = models.BooleanField(default=False)
#     state = models.IntegerField(default=-1)
#
#     def increaseFrame(self,val):
#         frameNB = frameNB + val
#
#     def decreaseFrame(self,val):
#         frameNB = frameNB - val
#
# class ValidationCode(models.Model):
#     validationCode = models.PositiveIntegerField(primary_key=True)
#     workerID = models.ForeignKey('Worker', on_delete=models.CASCADE)
