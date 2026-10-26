import sys
import os

# Menambahkan root directory ke sys.path agar modul lokal dapat diimpor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class VercelPathMiddleware:
    """
    Middleware untuk menormalkan PATH_INFO pada Vercel Serverless Function
    agar semua route Flask (/, /api/portfolio, /api/sr-radar, dll) cocok sempurna.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        original_path = environ.get('HTTP_X_MATCHED_PATH') or environ.get('HTTP_X_FORWARDED_URI')
        if original_path:
            environ['PATH_INFO'] = original_path
        else:
            path = environ.get('PATH_INFO', '')
            if path.startswith('/api/index.py'):
                environ['PATH_INFO'] = path[len('/api/index.py'):] or '/'
            elif path.startswith('/api/index'):
                environ['PATH_INFO'] = path[len('/api/index'):] or '/'
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)

# Vercel Serverless WSGI Handler
handler = app
