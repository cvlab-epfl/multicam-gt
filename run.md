conda install postgresql  
initdb -D scout   
chmod -R 700 scout
pg_ctl -D scout -l logfile start
createuser scout
createdb --owner=scout scout

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

python manage.py migrate
python manage.py runserver 0.0.0.0:4444