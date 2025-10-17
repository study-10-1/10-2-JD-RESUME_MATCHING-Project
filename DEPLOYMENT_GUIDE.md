# 배포 가이드

## 🚀 **Cross-encoder 배포 설정**

### **1. 환경별 Cross-encoder 설정**

#### **CPU 환경 (기본)**
```bash
# Bi-encoder만 사용 (안정적, 빠름)
docker compose up -d
```

#### **GPU 환경 (고성능)**
```bash
# Cross-encoder 자동 활성화
docker compose -f docker-compose.gpu.yml up -d
```

#### **CPU 환경에서 Cross-encoder 강제 사용 (테스트용)**
```bash
# 메모리 주의! 테스트용으로만 사용
FORCE_CROSS_ENCODER=true docker compose up -d
```

### **2. 환경 변수 설정**

#### **.env 파일 생성**
```bash
# 기본 설정
ENVIRONMENT=production
DEBUG=false
JWT_SECRET_KEY=your-secret-key-here

# Cross-encoder 설정
FORCE_CROSS_ENCODER=false  # CPU 환경에서는 false
# FORCE_CROSS_ENCODER=true  # GPU 환경에서는 true

# 데이터베이스 설정
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_DB=auto_match

# OpenAI 설정
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o-mini
```

### **3. 배포 환경별 권장 설정**

#### **개발 환경**
```yaml
# docker-compose.dev.yml
services:
  backend:
    environment:
      - FORCE_CROSS_ENCODER=false  # Bi-encoder만 사용
      - DEBUG=true
```

#### **스테이징 환경**
```yaml
# docker-compose.staging.yml
services:
  backend:
    environment:
      - FORCE_CROSS_ENCODER=true  # Cross-encoder 테스트
      - DEBUG=false
```

#### **프로덕션 환경 (GPU)**
```yaml
# docker-compose.prod.yml
services:
  backend:
    environment:
      - FORCE_CROSS_ENCODER=false  # GPU 환경에서 자동 활성화
      - DEBUG=false
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### **4. 성능 모니터링**

#### **Cross-encoder 상태 확인**
```bash
# API를 통한 상태 확인
curl "http://localhost:8000/api/v1/matching/status" | jq '.cross_encoder_available'

# Docker 로그 확인
docker compose logs backend | grep "Cross-encoder"
```

#### **메모리 사용량 모니터링**
```bash
# 컨테이너 리소스 사용량
docker stats

# Cross-encoder 메모리 사용량
docker compose exec backend python -c "
from app.services.ml.cross_encoder import CrossEncoderService
import torch
print(f'CUDA 사용 가능: {torch.cuda.is_available()}')
cross_encoder = CrossEncoderService()
print(f'Cross-encoder 사용 가능: {cross_encoder.is_available()}')
"
```

### **5. 문제 해결**

#### **Cross-encoder 로드 실패**
```bash
# 메모리 부족 시
docker compose down
docker system prune -f
docker compose up -d

# 환경 변수 확인
docker compose exec backend env | grep FORCE_CROSS_ENCODER
```

#### **GPU 환경에서 Cross-encoder 비활성화**
```bash
# NVIDIA Container Toolkit 설치 확인
nvidia-smi
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# Docker Compose GPU 설정 확인
docker compose -f docker-compose.gpu.yml config
```

### **6. 성능 최적화**

#### **CPU 환경 최적화**
- Bi-encoder만 사용
- 메모리 사용량 최소화
- 빠른 응답 시간

#### **GPU 환경 최적화**
- Cross-encoder 자동 활성화
- 높은 정확도
- 처리 시간 증가 (1.5-2배)

### **7. 배포 체크리스트**

- [ ] 환경 변수 설정 완료
- [ ] 데이터베이스 연결 확인
- [ ] Cross-encoder 상태 확인
- [ ] API 엔드포인트 테스트
- [ ] 메모리 사용량 모니터링
- [ ] 로그 설정 확인

## 🎯 **권장 배포 전략**

1. **개발**: Bi-encoder만 사용 (안정성)
2. **스테이징**: Cross-encoder 테스트 (정확도 검증)
3. **프로덕션**: GPU 환경에서 Cross-encoder 자동 활성화 (최고 성능)
