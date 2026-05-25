이 프로젝트의 폴더는 ~/projects/financial_statement/ 

프로젝트 체크리스트:

1. 코스피와 코스닥에 상장된 기업 정보와 섹터 추출
   - krx_sector/get_krx_sector_data_final.py 사용
   - data/krx_sector_data.csv 저장
2. 데이터 소스 식별 (KOSPI/KOSDAQ 분기별 재무제표)
   - OpenDart API 사용
3. 재무 데이터 추출 및 수집 자동화 스크립트 개발
   - dart/fetch_initial_data.py (이전 데이터 추출 / one time only)
   - dart/get_financial_statements.py
4. 데이터 정제 및 저장
   - data/financial_data.db
5. 저평가 기업 선정 기준 정의 (예: P/E, P/B, ROE, 현금 흐름, 성장성)
   - undervalued_standard.md
6. 재무 분석 및 저평가 기업 식별 모델/스크립트 개발
   - analyze_and_identify_undervalued.py 개발중
7. 거시 경제 데이터 및 산업 리포트 수집
8. 미래 유망 섹터 분석 및 선정 방법론 정의
9. 보고서 템플릿 디자인 (추천 기업, 이전 추천 기업 평가, 유망 섹터)
10. 분기별 보고서 생성 및 출력 자동화 스크립트 개발
11. 자동화된 프로세스 검증 및 모니터링 계획 수립
12. 분기별 자동 보고서 생성을 위한 cronjob 설정
