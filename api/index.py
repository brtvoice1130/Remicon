import sys
import os

# 백엔드 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app

# Vercel용 앱 export
application = app