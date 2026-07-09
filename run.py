#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("  Mr.Check — Local Application")
    print("  Open http://127.0.0.1:5000 in your browser")
    print("=" * 50)
    app.run(host='127.0.0.1', port=5000, debug=False)