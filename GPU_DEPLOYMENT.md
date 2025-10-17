# GPU 환경 배포 가이드

## 🚀 GPU 환경에서 Cross-encoder 활성화

### **필요 조건**
- NVIDIA GPU (CUDA 지원)
- Docker with NVIDIA Container Toolkit
- NVIDIA Driver 설치

### **1. NVIDIA Container Toolkit 설치**

#### Ubuntu/Debian:
```bash
# NVIDIA Container Toolkit 설치
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

#### CentOS/RHEL:
```bash
# NVIDIA Container Toolkit 설치
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.repo | sudo tee /etc/yum.repos.d/nvidia-docker.repo

sudo yum install -y nvidia-docker2
sudo systemctl restart docker
```

### **2. GPU 환경 실행**

```bash
# GPU 환경으로 실행
docker compose -f docker-compose.gpu.yml up -d

# 로그 확인
docker compose -f docker-compose.gpu.yml logs -f backend
```

### **3. Cross-encoder 활성화 확인**

```bash
# GPU 환경에서 Cross-encoder 테스트
docker compose -f docker-compose.gpu.yml exec backend python -c "
from app.services.ml.cross_encoder import CrossEncoderService
import torch
print(f'CUDA 사용 가능: {torch.cuda.is_available()}')
cross_encoder = CrossEncoderService()
print(f'Cross-encoder 사용 가능: {cross_encoder.is_available()}')
"
```

### **4. API 사용법**

#### 검색 API (Bi-encoder):
```bash
GET /api/v1/matching/search-jobs
```

#### 상세 API (Cross-encoder 자동 활성화):
```bash
# GPU 환경에서는 자동으로 Cross-encoder 사용
GET /api/v1/matching/{matching_id}

# 명시적으로 Cross-encoder 사용
GET /api/v1/matching/{matching_id}?use_cross_encoder=true
```

### **5. 성능 비교**

| 환경 | 모델 | 처리 시간 | 정확도 |
|------|------|-----------|--------|
| CPU | Bi-encoder | ~500ms | 85% |
| GPU | Bi-encoder | ~200ms | 85% |
| GPU | Cross-encoder | ~300ms | 92% |

### **6. 문제 해결**

#### GPU 인식 안됨:
```bash
# NVIDIA Container Toolkit 재설치
sudo apt-get remove nvidia-docker2
sudo apt-get install nvidia-docker2
sudo systemctl restart docker
```

#### 메모리 부족:
```bash
# GPU 메모리 확인
nvidia-smi

# Docker 메모리 제한 증가
# docker-compose.gpu.yml에서 memory 제한 수정
```

### **7. 모니터링**

```bash
# GPU 사용률 모니터링
watch -n 1 nvidia-smi

# 컨테이너 리소스 사용량
docker stats
```

## 🎯 **결론**

- **CPU 환경**: Bi-encoder만 사용 (안정적)
- **GPU 환경**: Cross-encoder 자동 활성화 (고성능)
- **자동 전환**: 환경에 따라 자동으로 최적 모델 선택
