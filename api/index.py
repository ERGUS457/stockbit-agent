import sys
import os

# Menambahkan root directory ke sys.path agar modul lokal dapat diimpor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel Serverless WSGI Handler
handler = app
