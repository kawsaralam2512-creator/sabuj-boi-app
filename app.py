# ============================================
# সবুজ বই — Flask Application (Main Entry)
# ============================================
# এই ফাইলটি app_routes.py থেকে সব routes load করে।
# সব ডেটা JSON থেকে লোড হয় (DB দরকার নেই)।
# ============================================

import json
import os
import re
from pathlib import Path
from datetime import timedelta, datetime

from dotenv import load_dotenv
from flask import Flask, session, flash, redirect, url_for

# .env ফাইল লোড করি
load_dotenv()


# ============================================
# 🔧 Path Setup
# ============================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
STATIC_DIR = BASE_DIR / 'static'
TEMPLATE_DIR = BASE_DIR / 'templates'


# ============================================
# 📖 JSON Loader Utilities
# ============================================
def load_json(filepath):
    """JSON ফাইল লোড করে dict রিটার্ন করে। ফাইল না থাকলে {} দেয়।"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON Error in {filepath}: {e}")
        return {}


def save_json(filepath, data):
    """JSON ফাইলে ডেটা সংরক্ষণ করে। সফল হলে True, নাহলে False।"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Save Error: {e}")
        return False


# ============================================
# 🔢 বাংলা ↔ ইংরেজি সংখ্যা রূপান্তর
# ============================================
BN_TO_EN_MAP = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')
EN_TO_BN_MAP = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')


def bn_to_en(text):
    """বাংলা সংখ্যা → ইংরেজি"""
    if not text:
        return ""
    return str(text).translate(BN_TO_EN_MAP)


def en_to_bn(text):
    """ইংরেজি সংখ্যা → বাংলা"""
    if not text:
        return ""
    return str(text).translate(EN_TO_BN_MAP)


# ============================================
# 🔍 Search Text Normalization
# ============================================
def normalize_for_search(text):
    """সার্চের জন্য টেক্সট নরমালাইজ করে।"""
    if not text:
        return ""
    text = str(text).lower()
    # বাংলা সংখ্যা → ইংরেজি
    text = bn_to_en(text)
    # Extra spaces সরানো
    text = re.sub(r'\s+', ' ', text)
    # Punctuation মুছে ফেলা
    text = re.sub(r'[।,!?;:\(\)\[\]\{\}"\'`~@#$%^&*+=|\\/<>]', ' ', text)
    return text.strip()


# ============================================
# 🔗 Cross-Reference Clickable
# ============================================
# অনুচ্ছেদ নম্বর খুঁজে বের করে লিংক তৈরি করে
# যেমন: "অনুচ্ছেদ ৪.২.৩" → "<a href='/lookup/৪.২.৩'>অনুচ্ছেদ ৪.২.৩</a>"
REF_PATTERN = re.compile(
    r'(অনুচ্ছেদ|উপানুচ্ছেদ)\s*[-–—]?\s*([০-৯\d]+(?:\.[০-৯\d]+)*)',
    re.UNICODE
)

import re
from flask import url_for

def make_cross_references_clickable(text):
    if not text:
        return ""

    # ১, ২ বা ৩ লেভেলের বাংলা/ইংরেজি সংখ্যা ধরার রেগুলার এক্সপ্রেশন
    pattern = re.compile(r'(?<![\d\.])((?:[০-৯]+|[0-9]+)(?:\.(?:[০-৯]+|[0-9]+))+)(?![\d\.])')

    def replace_match(match):
        ref = match.group(1)
        url = url_for('lookup_reference', ref_number=ref)
        return f'<a href="{url}" class="cross-ref-link" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">{ref}</a>'

    return pattern.sub(replace_match, text)

# ============================================
# 🔐 Login Required Decorator
# ============================================
from functools import wraps


def login_required(f):
    """শুধু admin users দের জন্য protected route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('🔒 এই পেজ দেখতে লগইন করুন', 'error')
            return redirect(url_for('login', next=url_for(f.__name__, **kwargs)))
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# 🏭 Application Factory
# ============================================
def create_app(env='development'):
    app = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
        static_url_path='/static'
    )

    # ==================== Configuration ====================
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY',
        'dev-secret-change-in-production-xyz123'
    )
    app.config['ADMIN_PASSWORD'] = os.environ.get(
        'ADMIN_PASSWORD',
        'kawsar2024'
    )
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
        seconds=int(os.environ.get('SESSION_LIFETIME', 86400))
    )
    app.config['JSON_AS_ASCII'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

    # ==================== Data File Paths ====================
    app.config['DATA_DIR'] = str(DATA_DIR)
    app.config['STATIC_DIR'] = str(STATIC_DIR)
    app.config['BOOK_FILE'] = str(DATA_DIR / 'book_data.json')
    app.config['PPR_FILE'] = str(DATA_DIR / 'ppr2025_problems.json')
    app.config['CHALLENGES_FILE'] = str(DATA_DIR / 'challenges.json')
    app.config['DECISION_FILE'] = str(DATA_DIR / 'decision_tree.json')
    app.config['FUNDS_FILE'] = str(DATA_DIR / 'funds.json')
    app.config['MILESTONES_FILE'] = str(DATA_DIR / 'milestones.json')
    app.config['SYSTEMS_FILE'] = str(DATA_DIR / 'systems.json')
    app.config['MISC_FILE'] = str(DATA_DIR / 'miscellaneous.json')
    app.config['PPR_PDF'] = 'ppr2025.pdf'
    app.config['APPENDIX_FILE'] = str(DATA_DIR / 'appendices.json')
    app.config['SABUJ_BOI_PDF'] = 'sabuj_boi_2022.pdf'

    # ==================== Register Routes ====================
    from app_routes import register_routes
    register_routes(app)

    # ==================== Template Globals ====================
    @app.context_processor
    def inject_globals():
        """সব template-এ common variables inject করি"""
        return {
            'now': datetime.now(),
            'year': datetime.now().year,
            'is_admin': session.get('is_admin', False),
        }

    # ==================== Custom Jinja Filters ====================
    @app.template_filter('bn')
    def to_bangla_filter(value):
        """ইংরেজি সংখ্যা → বাংলা সংখ্যা"""
        return en_to_bn(str(value))

    @app.template_filter('en')
    def to_english_filter(value):
        """বাংলা সংখ্যা → ইংরেজি সংখ্যা"""
        return bn_to_en(str(value))

    @app.template_filter('truncate_bn')
    def truncate_bangla(text, length=200):
        """টেক্সট ছোট করে... দেখায়"""
        if not text:
            return ""
        text = str(text)
        if len(text) <= length:
            return text
        return text[:length].rsplit(' ', 1)[0] + '...'

    # ==================== Session Config ====================
    @app.before_request
    def make_session_permanent():
        session.permanent = True

    # ==================== Logging ====================
    app.logger.info(f"✅ সবুজ বই — {env} environment")
    app.logger.info(f"📁 Data: {DATA_DIR}")

    return app


# ============================================
# 🚀 Run (Development only)
# ============================================
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)