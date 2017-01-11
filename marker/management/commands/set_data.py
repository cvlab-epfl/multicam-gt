from django.core.management.base import BaseCommand, CommandError
from marker.models import Rectangle

class Command(BaseCommand):
    help = 'Populate database'

    def handle(self, *args, **options):
        candidates = Rectangle.objects.all()
        total = len(candidates)
        i = 0
        j = 1
        for c in candidates:
            c.xMid = (c.x1 + c.x2) // 2
            c.save()
            i = i + 1
            if i % round(total/10) == 0:
                print(j*10,'%')
                j = j + 1
        print("Done")
