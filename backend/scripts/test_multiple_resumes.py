#!/usr/bin/env python3
"""
여러 이력서로 매칭 정확도 테스트 및 동적 임계값 개선
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append('/app')

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.models.resume import Resume
from app.models.job_posting import JobPosting
from app.services.matching_service import MatchingService
from app.core.config import settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/test_results.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_resume_matching(resume_id: str, db_session) -> Dict[str, Any]:
    """단일 이력서 매칭 테스트"""
    logger.info(f"Testing resume: {resume_id}")
    
    try:
        # 이력서 조회
        resume = db_session.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            logger.error(f"Resume not found: {resume_id}")
            return None
        
        logger.info(f"Resume found: {resume.file_name}")
        
        # 매칭 서비스 실행
        matching_service = MatchingService(db_session)
        result = matching_service.search_jobs_for_resume(resume_id)
        
        # 결과 분석
        analysis = {
            'resume_id': resume_id,
            'resume_file': resume.file_name,
            'total_matches': result['total_count'],
            'processing_time': result['processing_time_ms'],
            'matches': []
        }
        
        for match in result['matches'][:5]:  # 상위 5개만 분석
            match_analysis = {
                'job_title': match['job_title'],
                'company': match['company_name'],
                'overall_score': match['overall_score'],
                'grade': match['grade'],
                'required_score': match['category_scores']['required_match']['score'],
                'preferred_score': match['category_scores']['preferred_match']['score'],
                'threshold_issues': []
            }
            
            # 임계값 문제 분석
            required_evidence = match['matching_evidence'].get('required_skills', {})
            if required_evidence.get('detailed_analysis'):
                for detail in required_evidence['detailed_analysis']:
                    if detail['similarity_score'] > 0.5 and not detail['matched']:
                        match_analysis['threshold_issues'].append({
                            'condition': detail['condition'][:50] + '...',
                            'score': detail['similarity_score'],
                            'threshold': detail.get('threshold_used', 'unknown'),
                            'issue': 'High similarity but not matched - consider lowering threshold'
                        })
            
            analysis['matches'].append(match_analysis)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error testing resume {resume_id}: {e}")
        return None

def analyze_threshold_issues(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """모든 결과를 분석하여 임계값 개선사항 도출"""
    logger.info("Analyzing threshold issues across all resumes...")
    
    threshold_issues = {
        'common_tech_issues': {},
        'recommendations': [],
        'summary': {
            'total_resumes': len(all_results),
            'total_issues': 0,
            'common_patterns': []
        }
    }
    
    # 기술별 문제 수집
    tech_issues = {}
    
    for result in all_results:
        if not result:
            continue
            
        for match in result['matches']:
            for issue in match['threshold_issues']:
                condition = issue['condition'].lower()
                score = issue['score']
                threshold = issue['threshold']
                
                # 기술 키워드 추출
                techs = ['java', 'python', 'react', 'flutter', 'spring', 'fastapi', 'typescript', 'android']
                for tech in techs:
                    if tech in condition:
                        if tech not in tech_issues:
                            tech_issues[tech] = []
                        tech_issues[tech].append({
                            'score': score,
                            'threshold': threshold,
                            'condition': issue['condition']
                        })
                        break
    
    # 기술별 분석
    for tech, issues in tech_issues.items():
        if len(issues) >= 2:  # 2번 이상 발생한 문제
            avg_score = sum(issue['score'] for issue in issues) / len(issues)
            avg_threshold = sum(issue['threshold'] for issue in issues) / len(issues)
            
            if avg_score > avg_threshold * 0.9:  # 임계값의 90% 이상인 경우
                threshold_issues['recommendations'].append({
                    'tech': tech,
                    'current_threshold': avg_threshold,
                    'suggested_threshold': avg_score + 0.02,
                    'reason': f'Average score {avg_score:.3f} is close to threshold {avg_threshold:.3f}',
                    'occurrences': len(issues)
                })
    
    threshold_issues['common_tech_issues'] = tech_issues
    threshold_issues['summary']['total_issues'] = sum(len(issues) for issues in tech_issues.values())
    
    return threshold_issues

def main():
    """메인 실행 함수"""
    logger.info("Starting multiple resume matching test...")
    
    # 데이터베이스 연결
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 모든 이력서 조회
        resumes = db.query(Resume).limit(10).all()  # 최대 10개 테스트
        
        if not resumes:
            logger.error("No resumes found in database")
            return
        
        logger.info(f"Found {len(resumes)} resumes to test")
        
        # 각 이력서 테스트
        all_results = []
        for resume in resumes:
            result = test_resume_matching(str(resume.id), db)
            if result:
                all_results.append(result)
        
        # 결과 분석
        analysis = analyze_threshold_issues(all_results)
        
        # 결과 출력
        logger.info("=" * 80)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 80)
        
        for result in all_results:
            logger.info(f"Resume: {result['resume_file']}")
            logger.info(f"  Total matches: {result['total_matches']}")
            logger.info(f"  Processing time: {result['processing_time']}ms")
            for match in result['matches']:
                logger.info(f"    - {match['job_title']}: {match['overall_score']:.1f}% ({match['grade']})")
                if match['threshold_issues']:
                    logger.info(f"      Threshold issues: {len(match['threshold_issues'])}")
        
        logger.info("\n" + "=" * 80)
        logger.info("THRESHOLD IMPROVEMENT RECOMMENDATIONS")
        logger.info("=" * 80)
        
        for rec in analysis['recommendations']:
            logger.info(f"Tech: {rec['tech']}")
            logger.info(f"  Current threshold: {rec['current_threshold']:.3f}")
            logger.info(f"  Suggested threshold: {rec['suggested_threshold']:.3f}")
            logger.info(f"  Reason: {rec['reason']}")
            logger.info(f"  Occurrences: {rec['occurrences']}")
            logger.info("")
        
        # 결과를 JSON 파일로 저장
        with open('/app/test_analysis_results.json', 'w', encoding='utf-8') as f:
            json.dump({
                'test_results': all_results,
                'threshold_analysis': analysis
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Detailed results saved to: test_analysis_results.json")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
