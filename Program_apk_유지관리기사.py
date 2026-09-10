import os
import sys
from datetime import date
import requests

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.text import LabelBase
from kivy.utils import platform

# ------------------
# 0. 안드로이드 한글 폰트 및 권한 처리
# ------------------
def setup_korean_font():
    """안드로이드 및 PC 환경에서 한글 깨짐/튕김 방지를 위해 기본 폰트 재지정"""
    font_path = None
    if platform == 'android':
        # 안드로이드 시스템 내 대표적인 한글 폰트 경로 확인
        possible_fonts = [
            "/system/fonts/NanumGothic.ttf",
            "/system/fonts/NotoSansCJK-Regular.ttc",
            "/system/fonts/NotoSansKR-Regular.otf",
            "/system/fonts/DroidSansFallback.ttf"
        ]
        for f in possible_fonts:
            if os.path.exists(f):
                font_path = f
                break
    else:
        # PC 환경 테스트 시 프로젝트 폴더 내 폰트 파일이 있는 경우
        if os.path.exists("NanumGothic.ttf"):
            font_path = "NanumGothic.ttf"

    if font_path:
        # Kivy 기본 폰트 이름을 시스템 한글 폰트로 대체 덮어쓰기
        LabelBase.register(name='Roboto', fn_regular=font_path)

setup_korean_font()

# 카메라 모듈 안전 로드
try:
    from plyer import camera
except ImportError:
    camera = None

# ------------------
# 1. API 통신 모듈
# ------------------
SERVER_URL = "http://192.168.0.100:8000"  # 실제 백엔드 IP 주소
TOKEN = None

def api_login(username, password):
    global TOKEN
    try:
        r = requests.post(
            f"{SERVER_URL}/token", 
            data={"username": username, "password": password},
            timeout=5
        )
        if r.status_code == 200:
            TOKEN = r.json().get("access_token")
            return True
    except Exception as e:
        print("Login Error:", e)
    return False

def api_save_log(data):
    if not TOKEN: 
        return None
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        r = requests.post(f"{SERVER_URL}/log", json=data, headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("Save Log Error:", e)
    return None

def api_upload_photo(log_id, photo_path):
    if not TOKEN or not photo_path or not os.path.exists(photo_path): 
        return None
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        with open(photo_path, "rb") as f:
            r = requests.post(f"{SERVER_URL}/upload-photo/{log_id}", files={"file": f}, headers=headers, timeout=10)
            return r.json()
    except Exception as e:
        print("Upload Photo Error:", e)
    return None

# ------------------
# 2. UI 레이아웃 (KV String)
# ------------------
KV = '''
ScreenManager:
    LoginScreen:
        name: 'login'
    MainScreen:
        name: 'main'

<LoginScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 40
        spacing: 15
        Label:
            text: "설비 관리 시스템"
            font_size: '22sp'
        TextInput:
            id: username_input
            hint_text: "아이디 (admin 또는 worker1)"
            multiline: False
            size_hint_y: None
            height: '48dp'
        TextInput:
            id: password_input
            hint_text: "비밀번호 (1234)"
            password: True
            multiline: False
            size_hint_y: None
            height: '48dp'
        Button:
            text: "로그인"
            size_hint_y: None
            height: '50dp'
            on_press: root.do_login()
        Label:
            id: status_label
            text: ""
            color: 1, 0, 0, 1

<MainScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: 20
        spacing: 10
        Label:
            text: "작업 일지 작성"
            size_hint_y: 0.1
            font_size: '18sp'
        BoxLayout:
            orientation: "horizontal"
            size_hint_y: 0.12
            spacing: 5
            TextInput:
                id: machine_no_input
                hint_text: "호기 번호 입력 또는 QR스캔"
                multiline: False
            Button:
                text: "QR 스캔"
                size_hint_x: 0.35
                on_press: root.scan_qr()
        TextInput:
            id: memo_input
            hint_text: "작업 메모"
            size_hint_y: 0.4
        Button:
            text: "사진 촬영"
            size_hint_y: 0.12
            on_press: root.take_picture()
        Button:
            text: "서버로 저장"
            size_hint_y: 0.12
            on_press: root.send()
'''

# ------------------
# 3. 화면 동작 로직
# ------------------
class LoginScreen(Screen):
    def do_login(self):
        username = self.ids.username_input.text.strip()
        password = self.ids.password_input.text.strip()
        
        if not username or not password:
            self.ids.status_label.text = "아이디와 비밀번호를 입력하세요."
            return

        if api_login(username, password):
            self.manager.current = 'main'
        else:
            self.ids.status_label.text = "서버 연결 실패 또는 정보 오류"

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.photo_path = ""

    def scan_qr(self):
        self.ids.machine_no_input.text = "QR_SCANNED_10호기"
        self.ids.memo_input.text = "QR 스캔 완료!"

    def take_picture(self):
        if not camera:
            self.ids.memo_input.text = "카메라 모듈을 로드할 수 없습니다."
            return

        # 내부 저장소 내 앱 데이터 전용 경로 생성 (권한 에러 방지)
        app_dir = App.get_running_app().user_data_dir
        self.photo_path = os.path.join(app_dir, "work_photo.jpg")

        try:
            camera.take_picture(filename=self.photo_path, on_complete=self.on_picture_complete)
        except Exception as e:
            self.ids.memo_input.text = f"카메라 촬영 실패: {str(e)}"

    def on_picture_complete(self, filename):
        if os.path.exists(filename):
            self.photo_path = filename
            self.ids.memo_input.text = "사진 촬영 완료!"
        else:
            self.ids.memo_input.text = "사진 저장 실패"

    def send(self):
        machine_no = self.ids.machine_no_input.text.strip()
        memo = self.ids.memo_input.text.strip()

        if not machine_no:
            self.ids.memo_input.text = "호기 번호를 입력해 주세요."
            return

        data = {
            "work_date": date.today().isoformat(),
            "location_id": 1,
            "model_id": 1,
            "machine_no": machine_no,
            "item": "폭기",
            "memo": memo,
            "latitude": 37.52,
            "longitude": 126.97
        }
        
        # 1. 일지 데이터 전송
        res = api_save_log(data)
        
        if res:
            # 2. 사진 파일 전송
            if "log_id" in res and self.photo_path and os.path.exists(self.photo_path):
                api_upload_photo(res["log_id"], self.photo_path)
            self.ids.memo_input.text = "서버 저장 성공!"
            self.photo_path = ""
        else:
            self.ids.memo_input.text = "서버 저장 실패 (네트워크 확인 필요)"

class MaintenanceApp(App):
    def build(self):
        return Builder.load_string(KV)

    def on_start(self):
        # 안드로이드 실행 시 동적 권한 요청
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.INTERNET
            ])

if __name__ == '__main__':
    MaintenanceApp().run()
