#!flask/bin/python
from gevent.wsgi import WSGIServer
from gevent import monkey
from app import app
# key point
monkey.patch_all()

if __name__ == '__main__':
    http_server = WSGIServer(('0.0.0.0', 5000), app)
    http_server.serve_forever()