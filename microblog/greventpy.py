#!flask/bin/python
from gevent.wsgi import WSGIServer
from gevent import monkey
from app import app
# key point
monkey.patch_all()

if __name__ == '__main__':
    http_server = WSGIServer(('', 5002), app)
    http_server.serve_forever()
