from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 다른 파일(예: dryer.py)에 작성한 API 라우터 불러오기
# (만약 dryer.py 파일이 있다면 주석을 해제하세요)
# from dryer import router as dryer_router 

app = FastAPI(
    title="Gaia Dryer API",
    description="안드로이드 건조기 제어 앱 전용 백엔드 API",
    version="1.0.0"
)

# 1. CORS 미들웨어 설정 (모든 도메인/앱 요청 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 서버 작동 및 안드로이드 통신 테스트용 기본 엔드포인트
@app.get("/")
def read_root():
    return {"status": "online", "message": "Dryer API Server is Running!"}

@app.get("/test")
def test_api():
    return {"result": "연동 성공!", "data": "클라우드 서버 통신 완료"}

# 3. 다른 py 파일의 비즈니스 로직(건조기 제어 등) 라우터 등록
from dryer import router as dryer_router
app.include_router(dryer_router)

if __name__ == '__main__':
    app.run(host='192.168.0.13', port=5000) # host를 192.168.0.13으로 지정

# main.py

@app.route('/', methods=['GET'])
def home():
    return "Happybot API Server is Running!"  # 서버 작동 여부 확인용

@app.route('/api/calculate', methods=['POST'])
def calculate():
    # 안드로이드 요청 처리 로직
    return jsonify({"result": "success"})