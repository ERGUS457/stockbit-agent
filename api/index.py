import sys
import os
import urllib.parse

# Menambahkan root directory ke sys.path agar modul lokal dapat diimpor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class VercelPathMiddleware:
    """
    Middleware untuk menormalkan PATH_INFO pada Vercel Serverless Function
    berdasarkan parameter __vercel_path atau header asli.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query_string = environ.get('QUERY_STRING', '')
        params = urllib.parse.parse_qs(query_string)

        if '__vercel_path' in params and params['__vercel_path']:
            target_path = params['__vercel_path'][0]
            if not target_path.startswith('/'):
                target_path = '/' + target_path
            environ['PATH_INFO'] = target_path

            # Bersihkan __vercel_path dari QUERY_STRING agar tidak mengganggu parameter lain
            new_params = {k: v for k, v in params.items() if k != '__vercel_path'}
            environ['QUERY_STRING'] = urllib.parse.urlencode(new_params, doseq=True)
        else:
            path = environ.get('PATH_INFO', '')
            if path in ('/api/index', '/api/index.py'):
                environ['PATH_INFO'] = '/'

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)

# Vercel Serverless WSGI Handler
handler = app
