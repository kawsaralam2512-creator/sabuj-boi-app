"""
🚀 সবুজ বই — Entry Point
=====================================
Development: python run.py
Production : gunicorn -w 4 -b 0.0.0.0:5000 run:app
"""

import os
from dotenv import load_dotenv

# .env লোড করি সবার আগে
load_dotenv()

from app import create_app

# Environment variable থেকে environment নিই
env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)


if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = env == 'development'

    print()
    print("=" * 60)
    print("📘 সবুজ বই — প্রকল্প ব্যবস্থাপনা সহায়ক")
    print("=" * 60)
    print(f"🌍 Environment  : {env}")
    print(f"🔗 Server       : http://{host}:{port}")
    print(f"🐛 Debug Mode   : {debug}")
    print(f"🔐 Admin Pass   : {os.environ.get('ADMIN_PASSWORD', 'kawsar2024')}")
    print("=" * 60)
    print()

    app.run(host=host, port=port, debug=debug)