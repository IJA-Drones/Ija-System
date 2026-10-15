"""Keep legacy uploads behind authenticated media routes, ahead of WhiteNoise."""

import posixpath

from werkzeug.wrappers import Response


class PrivateUploadsMiddleware:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        path = posixpath.normpath('/' + environ.get('PATH_INFO', '').lstrip('/')).lower()
        if any(path == prefix or path.startswith(prefix + '/')
               for prefix in ('/uploads', '/static/uploads')):
            return Response('Arquivo indisponível neste endereço.', status=404,
                            headers={'Cache-Control': 'private, no-store'})(environ, start_response)
        return self.application(environ, start_response)
