from django.core.management.base import BaseCommand, CommandError
from marker.models import Rectangle
import json
import os
class Command(BaseCommand):
    help = 'Populate database'

    def handle(self, *args, **options):
        rect = open('../data/rectangles480x1280.pom', 'r')
        lines = rect.readlines()
        rect.close()
        total = len(lines)
        i = 0
        j = 1
        for line in lines:
            box = Rectangle()
            l = line.split()
            box.cameraID = int(l[1])
            box.rectangleID = int(l[2])
            if l[3] != "notvisible":
                a, b, c, d = l[3:]
            else:
                a = b = c = d = 0
            box.x1 = int(a)
            box.y1 = int(b)
            box.x2 = int(c)
            box.y2 = int(d)
            box.xMid = (int(a)+int(c))//2
            box.save()
            i = i + 1
            if i % round(total/10) == 0:
                print(j*10,'%')
                j = j + 1
        print("Done")
