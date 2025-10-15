#!/bin/bash

# 임베딩 서비스 로컬 실행 스크립트

echo "🚀 Starting Embedding Service locally..."

cd "$(dirname "$0")"

# 가상환경 활성화
source venv/bin/activate

# 서비스 실행
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

