from django.db import models
from django.core.validators import validate_comma_separated_integer_list
import json

class Worker(models.Model):

    workerID = models.TextField(primary_key=True,max_length=40)
    frameNB = models.IntegerField(default=-1)
    frame_labeled = models.PositiveSmallIntegerField(default=0)
    #validationCode = models.PositiveIntegerField(default=0)
    finished = models.BooleanField(default=False)
    state = models.IntegerField(default=-1)
    tuto = models.BooleanField(default=False)
    time_list = models.TextField(default="")


    def increaseFrame(self,val):
        self.frame_labeled = self.frame_labeled + val

    def decreaseFrame(self,val):
        self.frame_labeled = self.frame_labeled - val

    def setTimeList(self,x):
        self.time_list = json.dumps(x)
    def getTimeList(self):
        return json.loads(self.time_list)
    def __str__(self):
        return 'Worker: ' + self.workerID
class ValidationCode(models.Model):
    validationCode = models.TextField(primary_key=True)
    worker = models.OneToOneField('Worker',on_delete=models.CASCADE)
    def __str__(self):
        return 'Code: ' + self.worker.workerID
