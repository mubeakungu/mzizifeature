# Fixed Procfile - uses gevent worker (actively maintained alternative to eventlet)
# Flask-SocketIO is fully compatible with gevent
web: gunicorn --worker-class geventwebsocket --workers 1 --bind 0.0.0.0:$PORT --timeout 60 run:app
