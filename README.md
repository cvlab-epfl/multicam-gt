

# EPFL MultiCam-GT v2
Updated version of EPFL MultiCam-GT Tool, a multiple view object annotation tool, now with:

- **Elevation model**: Improved ground plane representation through mesh-based elevation modeling, for object annotation in varying terrains.
- **Enhanced Object Transformation**: The new version includes object representation using dimensions and spatial orientation.
- **Tracklet Merging**: Functionality for merging tracklets, providing more streamlined object tracking.
- **Trajectory Visualization**: Features new tools for visualizing trajectories, enhancing understanding and analysis of object movement.
- **Database Integration**: All transformation and tracking data is now stored in the database, enabling more efficient data management and retrieval.

## TODO


## Usage
Define the DATABASES variable in the settings.py file to point to your database. The application is configured to use a PostgreSQL database. You can use the following configuration:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'scout',
        'USER': 'scout',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '',
    }
}
```
You can load the SCOUT data into the database by running the following command:
```bash
python manage.py shell < data_process.py
```
By default, the worker name will be 'SCOUT'. You can change it by editing the data_process.py file.
You can then run the following commands to run the application:
```bash
conda env create -n ENVNAME --file ENV.yml
pip install -r requirements.txt
initdb -D scout   
chmod -R 700 scout
pg_ctl -D scout -l logfile start
createuser scout
createdb --owner=scout scout

python manage.py migrate
python import_annotations.py --dataset SCOUT --worker workerID --input /cvlabdata2/cvlab/scout/annotations/raw/annotations_sequence_1_raw.json
python manage.py runserver 0.0.0.0:4444
```
You can now access the application at http://localhost:4444

Backup via:

```
pg_dump -U scout -h localhost -d scout -F c -f annotation_snapshot_280125.dump
```

```


### Acknowledgements
This project was based on the original [MultiCam-GT Tool](https://github.com/cvlab-epfl/multicam-gt) developed by the Computer Vision Laboratory at EPFL.
