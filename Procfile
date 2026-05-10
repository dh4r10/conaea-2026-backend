web: python manage.py collectstatic --noinput && gunicorn congress.wsgi --worker-class gevent --workers 2 --timeout 120
