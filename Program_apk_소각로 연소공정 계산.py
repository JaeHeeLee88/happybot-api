import ctypes
import logging
import math
import os
import re
import sys
import traceback
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk
import matplotlib.backends.backend_tkagg as tkagg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np


# ----------------------------------------------------
# PyInstaller 실행 및 폰트 강제 등록/복사 헬퍼 함수
# ----------------------------------------------------
def resource_path(relative_path):
    """PyInstaller 단일 EXE 빌드 환경(_MEIPASS) 및 일반 파이썬 실행 환경의 경로 호환성 처리"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def setup_windows_fonts():
    """
    윈도우 환경 어디서나 한글 및 이모지 폰트가 깨지지 않도록
    PC 내 시스템 폰트(맑은 고딕, Segoe UI Emoji 등)를 탐색/복사 및
    Matplotlib 및 Windows GDI 시스템 레벨에 강제로 동적 등록
    """
    win_font_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    target_fonts = ["malgun.ttf", "malgunbd.ttf", "seguiemj.ttf", "gulim.ttc"]

    loaded_font_names = []

    for font_file in target_fonts:
        # 1. 번들 내 fonts 폴더 파일 우선 확인
        font_path = resource_path(os.path.join("fonts", font_file))

        # 2. 파일이 없는 경우, 현재 PC의 C:\Windows\Fonts 경로에서 탐색
        if not os.path.exists(font_path):
            font_path = os.path.join(win_font_dir, font_file)

        if os.path.exists(font_path):
            # Windows GDI 세션 등록 (Tkinter/CustomTkinter 한글 깨짐 방지)
            if sys.platform == "win32":
                try:
                    ctypes.windll.gdi32.AddFontResourceW(font_path)
                except Exception:
                    pass

            # Matplotlib 폰트 매니저 동적 강제 등록
            try:
                fm.fontManager.addfont(font_path)
                font_prop = fm.FontProperties(fname=font_path)
                loaded_font_names.append(font_prop.get_name())
            except Exception:
                pass

    # Matplotlib 폰트 패밀리 등록
    font_family_list = loaded_font_names + ["Malgun Gothic", "Segoe UI Emoji", "Gulim", "sans-serif"]
    plt.rcParams["font.family"] = font_family_list
    plt.rcParams["axes.unicode_minus"] = False


# Matplotlib 폰트 매니저 경고 로그 억제 및 폰트 강제 자동 등록 실행
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
setup_windows_fonts()

# 파이썬 GUI 테마 설정
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class IncinerationSystemApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("소각/공해방지시설 통합 수지 및 장치 상세 설계 시스템")
        self.geometry("1480x920")

        # 폰트 크기 상태 관리 변수
        self.default_font_size = 13
        self.current_font_size = self.default_font_size
        self.mono_font = ctk.CTkFont(family="Consolas", size=self.current_font_size)

        # 0. 확장된 계산 근거 및 참고문헌 / 보고서 DB
        self.reference_db = {
            "1. 환경부 소각시설 설치 및 운영 관리기준": {
                "name": "환경부 폐기물관리법 시행규칙 [별표 9]",
                "url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=245823",
                "desc": "소각 시설의 고온 체류시간(2초 이상), 연소실 용적열부하 및 배출허용기준",
            },
            "2. 국립환경과학원 대기오염방지시설 최적기술(BAT) 보고서": {
                "name": "국립환경과학원(NIER) 소각시설 방지기술 가이드라인",
                "url": "https://www.nier.go.kr",
                "desc": "SDR, Bag Filter, SCR, SNCR 최적 제거효율 및 설계 파라미터 표준",
            },
            "3. KECO 한국환경공단 소각 및 에너지회수 기술지침": {
                "name": "한국환경공단 기술지침 (KECO-TG-2023)",
                "url": "https://www.keco.or.kr",
                "desc": "화격자/용적 열부하 계산, LHV/HHV 연소수지 수식, ID Fan 동력 산정식",
            },
            "4. 에너지공단 폐열보일러 & 스팀터빈 발전 설계 기준": {
                "name": "한국에너지공단 열사용기자재 및 발전효율 기준",
                "url": "https://www.energy.or.kr",
                "desc": "증기 엔탈피, LMTD 전열면적 산정, 보일러 튜브 수량 산정 공식",
            },
            "5. 미국 EPA Air Pollution Control Cost Manual": {
                "name": "US EPA Air Pollution Control Cost Manual Ch.1-3",
                "url": "https://www.epa.gov/catc",
                "desc": "Cyclone 절단경, Bag Filter 여과속도(1.0m/min), SCR 공간속도 공학 기준",
            },
            "6. Perry's Chemical Engineers' Handbook": {
                "name": "Perry's Chemical Engineers' Handbook (Heat Exchangers)",
                "url": "https://www.accessengineeringlibrary.com",
                "desc": "열교환기 LMTD, 총괄열전달계수(U) 및 단위조작 공학 공식",
            },
            "7. ASME Steam Tables & PTC 6 발전효율 기준": {
                "name": "ASME Performance Test Codes (PTC 6 - Steam Turbines)",
                "url": "https://www.asme.org",
                "desc": "증기 엔탈피 강하량 및 스팀터빈 발전 효율(기계 98%, 발전 97%) 기준",
            },
            "8. 한국대기환경학회 여과집진 및 가스처리 설계 기준": {
                "name": "한국대기환경학회(KSAE) 대기오염방지공학 지침",
                "url": "http://www.kosae.or.kr",
                "desc": "Bag Filter 탈진 방식, Room 분할 및 집진효율 수식",
            },
        }

        # 장치별 주요 연관 참고문헌 매핑 테이블
        self.device_ref_map = {
            "Incinerator (소각로)": "1. 환경부 소각시설 설치 및 운영 관리기준",
            "WHB (폐열보일러)": "4. 에너지공단 폐열보일러 & 스팀터빈 발전 설계 기준",
            "Steam Turbine (스팀터빈)": "7. ASME Steam Tables & PTC 6 발전효율 기준",
            "SNCR (고온 탈질)": "2. 국립환경과학원 대기오염방지시설 최적기술(BAT) 보고서",
            "Cyclone (싸이클론)": "5. 미국 EPA Air Pollution Control Cost Manual",
            "SDR (반건식 반응탑)": "2. 국립환경과학원 대기오염방지시설 최적기술(BAT) 보고서",
            "Bag Filter (여과집진기)": "8. 한국대기환경학회 여과집진 및 가스처리 설계 기준",
            "SCR (촉매 탈질)": "2. 국립환경과학원 대기오염방지시설 최적기술(BAT) 보고서",
            "ID Fan (유인송풍기)": "3. KECO 한국환경공단 소각 및 에너지회수 기술지침",
            "Stack (굴뚝)": "1. 환경부 소각시설 설치 및 운영 관리기준",
        }

        # 1. 소각로 DB
        self.incinerator_db = {
            "스토커식 (Stoker)": {
                "short_name": "Stoker",
                "air_ratio": 1.7,
                "temp": 900,
                "fly_ash_ratio": 0.15,
                "heat_loss": 0.05,
            },
            "유동층식 (Fluidized Bed)": {
                "short_name": "Fluidized Bed",
                "air_ratio": 1.4,
                "temp": 850,
                "fly_ash_ratio": 0.60,
                "heat_loss": 0.04,
            },
            "로터리 킬른식 (Rotary Kiln)": {
                "short_name": "Rotary Kiln",
                "air_ratio": 1.6,
                "temp": 1000,
                "fly_ash_ratio": 0.25,
                "heat_loss": 0.06,
            },
            "가스화 용융식 (Gasification)": {
                "short_name": "Gasification",
                "air_ratio": 1.2,
                "temp": 1300,
                "fly_ash_ratio": 0.10,
                "heat_loss": 0.03,
            },
        }

        # 유기성 폐기물 목록 (함수율 가변 대상)
        self.organic_wastes = [
            "음식물류 폐기물",
            "하수슬러지",
            "가축분뇨(우분뇨)",
            "커피찌꺼기",
        ]

        # 2. 폐기물 DB (wt%) - 가나다 순 정렬
        self.waste_db = {
            "가연성 생활폐기물(MSW)": {
                "C": 35.0, "H": 4.8, "O": 22.0, "N": 0.6, "S": 0.15, "Cl": 0.45, "W": 25.0, "A": 12.0,
            },
            "가축분뇨(우분뇨)": {
                "C": 8.0, "H": 1.1, "O": 6.4, "N": 0.5, "S": 0.1, "Cl": 0.04, "W": 80.0, "A": 3.86,
            },
            "무연탄": {
                "C": 75.0, "H": 2.0, "O": 2.5, "N": 0.8, "S": 0.5, "Cl": 0.02, "W": 4.18, "A": 15.0,
            },
            "유연탄": {
                "C": 68.0, "H": 4.5, "O": 7.0, "N": 1.2, "S": 0.8, "Cl": 0.05, "W": 8.0, "A": 10.45,
            },
            "음식물류 폐기물": {
                "C": 9.6, "H": 1.3, "O": 7.6, "N": 0.9, "S": 0.1, "Cl": 0.1, "W": 80.0, "A": 0.4,
            },
            "커피찌꺼기": {
                "C": 24.0, "H": 3.2, "O": 16.5, "N": 1.1, "S": 0.1, "Cl": 0.1, "W": 54.0, "A": 1.0,
            },
            "폐목재/임목 부산물": {
                "C": 34.0, "H": 4.2, "O": 30.0, "N": 0.3, "S": 0.05, "Cl": 0.05, "W": 30.0, "A": 1.4,
            },
            "폐합성수지(플라스틱)": {
                "C": 65.0, "H": 9.0, "O": 10.0, "N": 0.5, "S": 0.2, "Cl": 1.5, "W": 10.0, "A": 3.8,
            },
            "하수슬러지": {
                "C": 8.0, "H": 1.1, "O": 5.5, "N": 1.2, "S": 0.4, "Cl": 0.1, "W": 80.0, "A": 3.7,
            },
        }

        self.file_path = ""
        self.calc_res = {}

        # 메인 레이아웃 분할
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # ----------------------------------------------------
        # [좌측 프레임] 입력 및 변수 설정
        # ----------------------------------------------------
        self.sidebar = ctk.CTkFrame(self, width=340, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        ctk.CTkLabel(
            self.sidebar,
            text="🔥 소각/APCD 변수 및 설계",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(padx=15, pady=(15, 10))

        # 1. 입력 모드
        ctk.CTkLabel(
            self.sidebar,
            text="📌 1. 데이터 입력 방식:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=15, pady=(2, 2))
        self.opt_mode = ctk.CTkOptionMenu(
            self.sidebar,
            values=[
                "🗑️ 폐기물 종류별 선택",
                "✍️ 원소분석 직접 입력",
                "📁 엑셀/CSV 불러오기",
            ],
            command=self.change_input_mode,
        )
        self.opt_mode.pack(padx=15, pady=(0, 5), fill="x")

        # 동적 패널
        self.frame_inputs = ctk.CTkFrame(self.sidebar)
        self.frame_inputs.pack(padx=15, pady=5, fill="x")

        # [A] 폐기물 DB 선택
        self.sub_waste = ctk.CTkFrame(self.frame_inputs, fg_color="transparent")
        ctk.CTkLabel(self.sub_waste, text="폐기물 DB:").pack(anchor="w")
        self.opt_waste_type = ctk.CTkOptionMenu(
            self.sub_waste,
            values=list(self.waste_db.keys()),
            command=self.on_waste_type_change,
        )
        self.opt_waste_type.pack(fill="x", pady=(0, 5))

        # 유기성 폐기물 가변 함수율 입력 패널
        self.frame_moisture = ctk.CTkFrame(self.sub_waste, fg_color="transparent")
        ctk.CTkLabel(
            self.frame_moisture,
            text="💧 가변 함수율 W (%):",
            font=ctk.CTkFont(weight="bold"),
            text_color="#1971C2",
        ).pack(side="left")
        self.ent_moisture = ctk.CTkEntry(
            self.frame_moisture, width=80, font=ctk.CTkFont(weight="bold")
        )
        self.ent_moisture.pack(side="right")

        # [B] 원소 직접 입력
        self.sub_direct = ctk.CTkFrame(self.frame_inputs, fg_color="transparent")
        self.entries_elem = {}
        elem_list = [
            ("탄소 C (%)", "35.0"),
            ("수소 H (%)", "4.8"),
            ("산소 O (%)", "22.0"),
            ("황 S (%)", "0.15"),
            ("염소 Cl (%)", "0.45"),
            ("수분 W (%)", "25.0"),
            ("회분 A (%)", "12.0"),
        ]
        for label, default_val in elem_list:
            row = ctk.CTkFrame(self.sub_direct, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=label, width=95, anchor="w").pack(side="left")
            ent = ctk.CTkEntry(row, height=22)
            ent.insert(0, default_val)
            ent.pack(side="right", fill="x", expand=True)
            self.entries_elem[label] = ent

        # [C] 파일 선택
        self.sub_file = ctk.CTkFrame(self.frame_inputs, fg_color="transparent")
        self.btn_file = ctk.CTkButton(
            self.sub_file, text="📁 엑셀 파일 선택", command=self.select_file
        )
        self.btn_file.pack(fill="x", pady=5)
        self.lbl_file_name = ctk.CTkLabel(
            self.sub_file, text="선택 파일 없음", text_color="gray", wraplength=200
        )
        self.lbl_file_name.pack(fill="x")

        # 2. 투입량 입력
        ctk.CTkLabel(
            self.sidebar,
            text="📌 2. 처리 투입량 (kg/h):",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=15, pady=(5, 2))
        self.ent_throughput = ctk.CTkEntry(self.sidebar)
        self.ent_throughput.insert(0, "1000")
        self.ent_throughput.pack(padx=15, fill="x")

        # 3. 소각로 형식 및 공연비 입력
        ctk.CTkLabel(
            self.sidebar,
            text="📌 3. 소각로 및 공연비(α) 설정:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=15, pady=(5, 2))
        self.opt_incinerator = ctk.CTkOptionMenu(
            self.sidebar,
            values=list(self.incinerator_db.keys()),
            command=self.on_incinerator_change,
        )
        self.opt_incinerator.pack(padx=15, fill="x", pady=(0, 4))

        frame_air = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        frame_air.pack(padx=15, fill="x", pady=2)
        ctk.CTkLabel(
            frame_air,
            text="공연비 (Air Ratio, α):",
            font=ctk.CTkFont(weight="bold"),
            text_color="#1971C2",
        ).pack(side="left")
        self.ent_air_ratio = ctk.CTkEntry(
            frame_air, width=80, font=ctk.CTkFont(weight="bold")
        )
        self.ent_air_ratio.insert(0, "1.70")
        self.ent_air_ratio.pack(side="right")

        # 4. 방지시설 및 에너지 회수 공정 구성
        ctk.CTkLabel(
            self.sidebar,
            text="📌 4. 방지시설 & 스팀터빈 공정 구성:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=15, pady=(5, 2))

        self.apcd_vars = {}
        apcd_list = [
            ("WHB (폐열보일러)", True),
            ("Steam Turbine (스팀터빈 발전)", True),
            ("SNCR (고온 탈질)", True),
            ("Cyclone (1차 집진)", True),
            ("SDR (반건식 반응탑)", True),
            ("Bag Filter (여과집진기)", True),
            ("SCR (촉매 탈질)", False),
        ]
        self.frame_apcd = ctk.CTkFrame(self.sidebar)
        self.frame_apcd.pack(padx=15, pady=2, fill="x")

        for name, default_chk in apcd_list:
            var = ctk.BooleanVar(value=default_chk)
            chk = ctk.CTkCheckBox(
                self.frame_apcd,
                text=name,
                variable=var,
                checkbox_height=17,
                checkbox_width=17,
            )
            chk.pack(anchor="w", padx=8, pady=2)
            self.apcd_vars[name] = var

        # 계산 실행 버튼
        self.btn_run = ctk.CTkButton(
            self.sidebar,
            text="🚀 연소 수지 및 장치 설계 연산",
            fg_color="#2B8A3E",
            hover_color="#216A30",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.run_full_simulation,
        )
        self.btn_run.pack(padx=15, pady=(12, 12), fill="x")

        self.change_input_mode("🗑️ 폐기물 종류별 선택")
        self.on_waste_type_change(self.opt_waste_type.get())

        # ----------------------------------------------------
        # [우측 메인 프레임] 결과 탭 및 상단 폰트 제어 바
        # ----------------------------------------------------
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # ----------------------------------------------------
        # [상단 우측 폰트 제어 바 (Font Size Control)]
        # ----------------------------------------------------
        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))

        self.font_control_frame = ctk.CTkFrame(self.top_bar)
        self.font_control_frame.pack(side="right", padx=5, pady=2)

        ctk.CTkLabel(
            self.font_control_frame,
            text="🔤 Font Size Control:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(8, 4))

        self.btn_font_dec = ctk.CTkButton(
            self.font_control_frame,
            text="[ - 폰트 축소 ]",
            width=90,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#495057",
            hover_color="#343A40",
            command=lambda: self.change_font_size(-1),
        )
        self.btn_font_dec.pack(side="left", padx=2)

        self.btn_font_reset = ctk.CTkButton(
            self.font_control_frame,
            text="[ 폰트 초기화 ]",
            width=90,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#6C757D",
            hover_color="#5A6268",
            command=self.reset_font_size,
        )
        self.btn_font_reset.pack(side="left", padx=2)

        self.btn_font_inc = ctk.CTkButton(
            self.font_control_frame,
            text="[ + 폰트 확대 ]",
            width=90,
            height=26,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1971C2",
            hover_color="#155799",
            command=lambda: self.change_font_size(1),
        )
        self.btn_font_inc.pack(side="left", padx=(2, 8))

        # 메인 탭 뷰
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.tab_pfd = self.tabview.add("🗺️ 공정도 (PFD)")
        self.tab_device = self.tabview.add("⚙️ 장치 상세 설계")
        self.tab_log = self.tabview.add("📊 연소 & 물질수지")
        self.tab_apcd = self.tabview.add("💨 APCD 오염물질 배출농도")
        self.tab_graph = self.tabview.add("📈 시각화 프로파일")

        # 1. PFD 탭
        self.frame_pfd = ctk.CTkFrame(self.tab_pfd)
        self.frame_pfd.pack(fill="both", expand=True, padx=5, pady=5)

        # 2. 장치 상세 설계 탭 (참고문헌/사이트 연동 드롭다운)
        self.frame_device_top = ctk.CTkFrame(self.tab_device)
        self.frame_device_top.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(
            self.frame_device_top,
            text="🔍 대상 장치:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(side="left", padx=(10, 2))
        self.opt_select_device = ctk.CTkOptionMenu(
            self.frame_device_top,
            values=[
                "Incinerator (소각로)",
                "WHB (폐열보일러)",
                "Steam Turbine (스팀터빈)",
                "SNCR (고온 탈질)",
                "Cyclone (싸이클론)",
                "SDR (반건식 반응탑)",
                "Bag Filter (여과집진기)",
                "SCR (촉매 탈질)",
                "ID Fan (유인송풍기)",
                "Stack (굴뚝)",
            ],
            command=self.on_device_change_handler,
            width=180,
        )
        self.opt_select_device.pack(side="left", padx=5)

        ctk.CTkLabel(
            self.frame_device_top,
            text="📚 계산 근거/참고문헌 DB:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(side="left", padx=(15, 2))

        self.opt_select_ref = ctk.CTkOptionMenu(
            self.frame_device_top,
            values=list(self.reference_db.keys()),
            width=330,
        )
        self.opt_select_ref.pack(side="left", padx=5)

        self.btn_open_ref = ctk.CTkButton(
            self.frame_device_top,
            text="🌐 사이트 열기",
            width=100,
            fg_color="#1971C2",
            hover_color="#155799",
            command=self.open_reference_url,
        )
        self.btn_open_ref.pack(side="left", padx=5)

        self.txt_device_design = ctk.CTkTextbox(
            self.tab_device, width=750, height=520, font=self.mono_font
        )
        self.txt_device_design.pack(fill="both", expand=True, padx=5, pady=5)

        # 3. 물질 수지 탭
        self.txt_log = ctk.CTkTextbox(
            self.tab_log, width=750, height=550, font=self.mono_font
        )
        self.txt_log.pack(fill="both", expand=True, padx=5, pady=5)

        # 4. APCD 농도 탭
        self.txt_apcd = ctk.CTkTextbox(
            self.tab_apcd, width=750, height=550, font=self.mono_font
        )
        self.txt_apcd.pack(fill="both", expand=True, padx=5, pady=5)

        # 5. 그래프 탭
        self.frame_graph = ctk.CTkFrame(self.tab_graph)
        self.frame_graph.pack(fill="both", expand=True, padx=5, pady=5)

        # ----------------------------------------------------
        # [슬림 하단 서명 바] 보안 및 저작권 권한 서명
        # ----------------------------------------------------
        self.footer_frame = ctk.CTkFrame(self, height=18, corner_radius=0, fg_color="transparent")
        self.footer_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 2))

        self.lbl_copyright = ctk.CTkLabel(
            self.footer_frame,
            text="Lee Jae-Hee, 2026.09.02.",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="gray"
        )
        self.lbl_copyright.pack(side="right", anchor="e")

        self.append_log(
            "시스템이 준비되었습니다. 좌측 메뉴에서 폐기물 종류, 함수율, 공연비(α) 및 설비 조건을 설정 후 연산을 실행하세요."
        )

    def change_font_size(self, delta):
        """상단 폰트 제어 바에서 폰트 크기 변경 시 호출하는 메서드"""
        new_size = self.current_font_size + delta
        if 8 <= new_size <= 24:
            self.current_font_size = new_size
            self.apply_font_size()

    def reset_font_size(self):
        """폰트 크기를 기본값(13pt)으로 초기화하는 메서드"""
        self.current_font_size = self.default_font_size
        self.apply_font_size()

    def apply_font_size(self):
        """변경된 폰트 크기를 모든 결과 출력 CTkTextbox 위젯에 적용"""
        self.mono_font.configure(size=self.current_font_size)
        self.txt_device_design.configure(font=self.mono_font)
        self.txt_log.configure(font=self.mono_font)
        self.txt_apcd.configure(font=self.mono_font)

    def append_text_with_links(self, textbox_widget, text_content):
        """텍스트 박스 내부의 URL을 인식하여 클릭 가능한 하이퍼링크로 렌더링하는 함수"""
        textbox_widget.configure(state="normal")
        textbox_widget.delete("1.0", "end")

        tk_text = getattr(textbox_widget, "_textbox", textbox_widget)
        url_pattern = re.compile(r'(https?://[^\s\)\],]+)')

        for line in text_content.split('\n'):
            last_idx = 0
            for match in url_pattern.finditer(line):
                start, end = match.span()
                url = match.group(0)

                tk_text.insert("end", line[last_idx:start])

                tag_name = f"link_{tk_text.index('end').replace('.', '_')}"
                tk_text.tag_config(tag_name, foreground="#1971C2", underline=True)
                tk_text.tag_bind(tag_name, "<Button-1>", lambda e, u=url: webbrowser.open(u))
                tk_text.tag_bind(tag_name, "<Enter>", lambda e: tk_text.config(cursor="hand2"))
                tk_text.tag_bind(tag_name, "<Leave>", lambda e: tk_text.config(cursor="arrow"))

                tk_text.insert("end", url, tag_name)
                last_idx = end

            tk_text.insert("end", line[last_idx:] + "\n")

        textbox_widget.see("1.0")

    def on_device_change_handler(self, device_name):
        """장치 선택 변경 시 연관 참고문헌 자동 선택 및 설계 텍스트 표출"""
        if device_name in self.device_ref_map:
            associated_ref = self.device_ref_map[device_name]
            self.opt_select_ref.set(associated_ref)
        self.display_device_design(device_name)

    def open_reference_url(self):
        """드롭다운에서 선택된 참고문헌 웹사이트/보고서 링크 열기"""
        ref_key = self.opt_select_ref.get()
        ref_info = self.reference_db.get(ref_key, {})
        if "url" in ref_info:
            webbrowser.open(ref_info["url"])
            messagebox.showinfo("링크 연결", f"[{ref_info['name']}] 참고 웹사이트로 연결합니다.\n\nURL: {ref_info['url']}")

    def change_input_mode(self, mode_name):
        self.sub_waste.pack_forget()
        self.sub_direct.pack_forget()
        self.sub_file.pack_forget()

        if "폐기물 종류" in mode_name:
            self.sub_waste.pack(fill="x", padx=5, pady=5)
            self.on_waste_type_change(self.opt_waste_type.get())
        elif "원소분석" in mode_name:
            self.sub_direct.pack(fill="x", padx=5, pady=5)
        elif "엑셀" in mode_name:
            self.sub_file.pack(fill="x", padx=5, pady=5)

    def on_waste_type_change(self, selected_waste):
        if selected_waste in self.organic_wastes:
            self.frame_moisture.pack(fill="x", pady=(2, 5))
            default_w = self.waste_db[selected_waste]["W"]
            self.ent_moisture.delete(0, "end")
            self.ent_moisture.insert(0, f"{default_w:.1f}")
        else:
            self.frame_moisture.pack_forget()

    def on_incinerator_change(self, inc_name):
        default_alpha = self.incinerator_db[inc_name]["air_ratio"]
        self.ent_air_ratio.delete(0, "end")
        self.ent_air_ratio.insert(0, f"{default_alpha:.2f}")

    def append_log(self, text):
        self.txt_log.insert("end", f"{text}\n")
        self.txt_log.see("end")

    def select_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Data Files", "*.xlsx *.xls *.csv")]
        )
        if file_path:
            self.file_path = file_path
            self.lbl_file_name.configure(
                text=f"선택됨: {os.path.basename(file_path)}", text_color="white"
            )

    def run_full_simulation(self):
        try:
            throughput = float(self.ent_throughput.get())
            inc_type = self.opt_incinerator.get()
            inc_info = self.incinerator_db[inc_type]
            inc_short_name = inc_info["short_name"]
            alpha = float(self.ent_air_ratio.get())

            if alpha < 1.0:
                messagebox.showwarning(
                    "경고", "공연비(α)는 1.0 이상이어야 정상 연소가 가능합니다."
                )

            mode = self.opt_mode.get()

            if "폐기물 종류" in mode:
                waste_name = self.opt_waste_type.get()
                elem = self.waste_db[waste_name].copy()

                if waste_name in self.organic_wastes:
                    w_new = float(self.ent_moisture.get())
                    if w_new < 0.0 or w_new >= 100.0:
                        messagebox.showwarning(
                            "경고", "함수율(W)은 0% 이상 100% 미만이어야 합니다."
                        )
                        return

                    w_base = elem["W"]
                    dry_base = 100.0 - w_base
                    dry_new = 100.0 - w_new
                    scale_factor = dry_new / dry_base if dry_base > 0 else 1.0

                    for key in elem:
                        if key == "W":
                            elem["W"] = w_new
                        else:
                            elem[key] = elem[key] * scale_factor

                    waste_name = f"{waste_name} (함수율 {w_new:.1f}% 적용)"

            elif "원소분석" in mode:
                waste_name = "사용자 직접 입력 폐기물"
                elem = {
                    "C": float(self.entries_elem["탄소 C (%)"].get()),
                    "H": float(self.entries_elem["수소 H (%)"].get()),
                    "O": float(self.entries_elem["산소 O (%)"].get()),
                    "S": float(self.entries_elem["황 S (%)"].get()),
                    "Cl": float(self.entries_elem["염소 Cl (%)"].get()),
                    "W": float(self.entries_elem["수분 W (%)"].get()),
                    "A": float(self.entries_elem["회분 A (%)"].get()),
                }
                elem["N"] = max(0.0, 100.0 - sum(elem.values()))
            elif "엑셀" in mode:
                waste_name = (
                    os.path.basename(self.file_path)
                    if self.file_path
                    else "엑셀 샘플 데이터"
                )
                elem = self.waste_db["가연성 생활폐기물(MSW)"].copy()

            C, H, O, S, Cl, N, W, A = (
                elem["C"] / 100,
                elem["H"] / 100,
                elem["O"] / 100,
                elem["S"] / 100,
                elem["Cl"] / 100,
                elem.get("N", 0) / 100,
                elem["W"] / 100,
                elem["A"] / 100,
            )

            hhv = max(0, 8100 * C + 34000 * (H - O / 8) + 2500 * S)
            lhv = max(0, hhv - 600 * (9 * H + W))

            O0 = max(0.001, 1.867 * C + 5.6 * H + 0.7 * S - 0.7 * O)
            A0 = O0 / 0.21
            A_actual = alpha * A0

            G_CO2 = 1.867 * C
            G_SO2 = 0.7 * S
            G_HCl = 0.63 * Cl
            G_H2O = 11.2 * H + 1.24 * W
            G_N2 = 0.8 * N + 0.79 * A_actual
            G_O2 = 0.21 * (alpha - 1) * A0

            G0d = G_CO2 + G_SO2 + G_HCl + 0.8 * N + 0.79 * A0
            G0w = G0d + G_H2O
            Gd = G0d + (alpha - 1) * A0
            Gw = G0w + (alpha - 1) * A0

            O2_percent = (G_O2 / Gd) * 100 if Gd > 0 else 0
            total_Gw_h = Gw * throughput
            total_Gd_h = Gd * throughput

            # 바닥재 & 비산재 분리
            total_ash = throughput * A
            fly_ash_ratio = inc_info["fly_ash_ratio"]
            bottom_ash_ratio = 1.0 - fly_ash_ratio
            fly_ash = total_ash * fly_ash_ratio
            bottom_ash = total_ash * bottom_ash_ratio

            dust_raw = (fly_ash * 1e6) / total_Gd_h if total_Gd_h > 0 else 0
            sox_raw = (G_SO2 / Gd) * 1e6 if Gd > 0 else 0
            hcl_raw = (G_HCl / Gd) * 1e6 if Gd > 0 else 0
            nox_raw = 180.0

            dust_mass_cur = fly_ash

            # 스팀 물성치
            p_steam = 20.0
            t_steam = 250.0
            t_feed = 80.0
            h_steam = 680.0
            h_feed = 80.0
            delta_h = h_steam - h_feed

            apcd_stages = []
            cur_temp = inc_info["temp"]
            cur_dust, cur_sox, cur_hcl, cur_nox = (
                dust_raw,
                sox_raw,
                hcl_raw,
                nox_raw,
            )
            steam_prod = 0.0
            heat_rec = 0.0

            if self.apcd_vars["WHB (폐열보일러)"].get():
                in_temp = cur_temp
                out_temp = 250.0
                cur_temp = out_temp
                heat_rec = total_Gw_h * 0.33 * (in_temp - out_temp)
                steam_prod = (heat_rec / delta_h) / 1000.0
                q_act = total_Gw_h * (273.15 + cur_temp) / 273.15
                apcd_stages.append(
                    {
                        "unit": "WHB",
                        "temp": cur_temp,
                        "q_act": q_act,
                        "dust": cur_dust,
                        "sox": cur_sox,
                        "hcl": cur_hcl,
                        "nox": cur_nox,
                        "dust_mass": dust_mass_cur,
                        "collected_dust": 0.0,
                        "note": f"증기생산 {steam_prod:.2f} t/h (P={p_steam}kg/cm², T={t_steam}°C)",
                    }
                )

            # 스팀터빈 발전
            eta_mech = 0.98
            eta_gen = 0.97
            delta_h_turb = 180.0

            is_turb_enabled = (
                self.apcd_vars["Steam Turbine (스팀터빈 발전)"].get()
                and self.apcd_vars["WHB (폐열보일러)"].get()
            )

            if is_turb_enabled:
                m_steam_kg_h = steam_prod * 1000.0
                p_elec_kw = (
                    m_steam_kg_h * delta_h_turb * (1.163 / 1000.0) * eta_mech * eta_gen
                )
                p_elec_mw = p_elec_kw / 1000.0
                daily_kwh = p_elec_kw * 24.0
                annual_mwh = p_elec_mw * 8760.0 * 0.90
            else:
                m_steam_kg_h = 0.0
                p_elec_kw = 0.0
                p_elec_mw = 0.0
                daily_kwh = 0.0
                annual_mwh = 0.0

            turbine_props = {
                "enabled": is_turb_enabled,
                "m_steam_kg_h": m_steam_kg_h,
                "delta_h_turb": delta_h_turb,
                "eta_mech": eta_mech,
                "eta_gen": eta_gen,
                "p_elec_kw": p_elec_kw,
                "p_elec_mw": p_elec_mw,
                "daily_kwh": daily_kwh,
                "annual_mwh": annual_mwh,
            }

            if self.apcd_vars["SNCR (고온 탈질)"].get():
                cur_nox *= 0.45
                q_act = total_Gw_h * (273.15 + cur_temp) / 273.15
                apcd_stages.append(
                    {
                        "unit": "SNCR",
                        "temp": cur_temp,
                        "q_act": q_act,
                        "dust": cur_dust,
                        "sox": cur_sox,
                        "hcl": cur_hcl,
                        "nox": cur_nox,
                        "dust_mass": dust_mass_cur,
                        "collected_dust": 0.0,
                        "note": "NOx 55% 제거",
                    }
                )

            if self.apcd_vars["Cyclone (1차 집진)"].get():
                collected = dust_mass_cur * 0.75
                dust_mass_cur *= 0.25
                cur_dust *= 0.25
                q_act = total_Gw_h * (273.15 + cur_temp) / 273.15
                apcd_stages.append(
                    {
                        "unit": "Cyclone",
                        "temp": cur_temp,
                        "q_act": q_act,
                        "dust": cur_dust,
                        "sox": cur_sox,
                        "hcl": cur_hcl,
                        "nox": cur_nox,
                        "dust_mass": dust_mass_cur,
                        "collected_dust": collected,
                        "note": "조대먼지 75% 집진",
                    }
                )

            if self.apcd_vars["SDR (반건식 반응탑)"].get():
                cur_temp = 160.0
                cur_hcl *= 0.10
                cur_sox *= 0.15
                collected = dust_mass_cur * 0.20
                dust_mass_cur *= 0.80
                cur_dust *= 0.80
                q_act = total_Gw_h * (273.15 + cur_temp) / 273.15
                apcd_stages.append(
                    {
                        "unit": "SDR",
                        "temp": cur_temp,
                        "q_act": q_act,
                        "dust": cur_dust,
                        "sox": cur_sox,
                        "hcl": cur_hcl,
                        "nox": cur_nox,
                        "dust_mass": dust_mass_cur,
                        "collected_dust": collected,
                        "note": "HCl 90%, SOx 85% 제거",
                    }
                )

            if self.apcd_vars["Bag Filter (여과집진기)"].get():
                collected = dust_mass_cur * 0.995
                dust_mass_cur *= 0.005
                cur_dust *= 0.005
                cur_hcl *= 0.40
                cur_sox *= 0.60
                q_act = total_Gw_h * (273.15 + cur_temp) / 273.15
                apcd_stages.append(
                    {
                        "unit": "Bag Filter",
                        "temp": cur_temp,
                        "q_act": q_act,
                        "dust": cur_dust,
                        "sox": cur_sox,
                        "hcl": cur_hcl,
                        "nox": cur_nox,
                        "dust_mass": dust_mass_cur,
                        "collected_dust": collected,
                        "note": "미세 먼지 99.5% 제거",
                    }
                )

            if self.apcd_vars["SCR (촉매 탈질)"].get():
                cur_nox *= 0.15
                q_act = total_Gw_h * (273.15 + cur_temp) / 273.15
                apcd_stages.append(
                    {
                        "unit": "SCR",
                        "temp": cur_temp,
                        "q_act": q_act,
                        "dust": cur_dust,
                        "sox": cur_sox,
                        "hcl": cur_hcl,
                        "nox": cur_nox,
                        "dust_mass": dust_mass_cur,
                        "collected_dust": 0.0,
                        "note": "NOx 85% 고효율 제거",
                    }
                )

            corr_factor = (
                (21.0 - 12.0) / (21.0 - O2_percent)
                if (21.0 - O2_percent) > 0
                else 1.0
            )
            act_gas_flow_m3h = total_Gw_h * ((273.15 + cur_temp) / 273.15)
            fan_power_kw = (act_gas_flow_m3h * 350.0) / (3600.0 * 102.0 * 0.65)

            self.calc_res = {
                "throughput": throughput,
                "inc_type": inc_type,
                "inc_short_name": inc_short_name,
                "waste_name": waste_name,
                "alpha": alpha,
                "elem_pct": {
                    "C": C * 100,
                    "H": H * 100,
                    "O": O * 100,
                    "S": S * 100,
                    "Cl": Cl * 100,
                    "N": N * 100,
                    "W": W * 100,
                    "A": A * 100,
                },
                "lhv": lhv,
                "hhv": hhv,
                "O0": O0,
                "A0": A0,
                "A_actual": A_actual,
                "G_CO2": G_CO2,
                "G_SO2": G_SO2,
                "G_HCl": G_HCl,
                "G_H2O": G_H2O,
                "G_N2": G_N2,
                "G_O2": G_O2,
                "Gw": Gw,
                "Gd": Gd,
                "total_Gw_h": total_Gw_h,
                "total_Gd_h": total_Gd_h,
                "O2_percent": O2_percent,
                "ash_props": {
                    "total_ash": total_ash,
                    "bottom_ash": bottom_ash,
                    "bottom_ash_ratio": bottom_ash_ratio * 100,
                    "fly_ash": fly_ash,
                    "fly_ash_ratio": fly_ash_ratio * 100,
                },
                "steam_props": {
                    "p_steam": p_steam,
                    "t_steam": t_steam,
                    "t_feed": t_feed,
                    "h_steam": h_steam,
                    "h_feed": h_feed,
                    "delta_h": delta_h,
                    "heat_rec": heat_rec,
                    "steam_prod": steam_prod,
                },
                "turbine_props": turbine_props,
                "fan_power": fan_power_kw,
                "act_gas_flow_m3h": act_gas_flow_m3h,
                "apcd_stages": apcd_stages,
                "inc_outlet_gas": {
                    "dust": dust_raw,
                    "sox": sox_raw,
                    "hcl": hcl_raw,
                    "nox": nox_raw,
                    "dust_mass": fly_ash,
                    "temp": inc_info["temp"],
                    "q_act": total_Gw_h * (273.15 + inc_info["temp"]) / 273.15,
                },
                "final_actual": {
                    "dust": cur_dust,
                    "sox": cur_sox,
                    "hcl": cur_hcl,
                    "nox": cur_nox,
                    "dust_mass": dust_mass_cur,
                },
                "final_corr": {
                    "dust": cur_dust * corr_factor,
                    "sox": cur_sox * corr_factor,
                    "hcl": cur_hcl * corr_factor,
                    "nox": cur_nox * corr_factor,
                },
            }

            self.update_log_tab()
            self.update_apcd_tab()
            self.render_pfd_diagram()
            self.render_graphs()
            self.on_device_change_handler(self.opt_select_device.get())

            messagebox.showinfo(
                "계산 완료",
                f"공연비(α={alpha:.2f})가 적용된 수지 및 스팀터빈 발전 포함 전체 설비 연산이 완료되었습니다.",
            )

        except ValueError:
            messagebox.showerror(
                "입력 오류", "숫자 입력창에 올바른 수치를 입력하세요."
            )
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("오류", f"처리 중 오류 발생:\n{str(e)}")

    def update_log_tab(self):
        self.txt_log.delete("1.0", "end")
        r = self.calc_res
        e = r["elem_pct"]
        tp = r["throughput"]
        ash = r["ash_props"]
        stm = r["steam_props"]
        turb = r["turbine_props"]

        line = "=" * 80
        subline = "-" * 80

        log = [
            line,
            f" 📊 [연소 공학 및 물질수지 상세 산출 계산서] - 폐기물: {r['waste_name']}",
            line,
            "",
            "■ 1. 폐기물 원소 성분 및 발열량 산출 계산과정",
            subline,
            f"  [Step 1] 원소 분석 성분비 (wt% 기준)",
            f"     • C={e['C']:.2f}%, H={e['H']:.2f}%, O={e['O']:.2f}%, S={e['S']:.2f}%, Cl={e['Cl']:.2f}%, N={e['N']:.2f}%, W={e['W']:.2f}%, A={e['A']:.2f}%",
            "",
            "  [Step 2] 고위발열량 (HHV) 및 저위발열량 (LHV) 산정 공식",
            f"     • HHV = 8100×C + 34000×(H - O/8) + 2500×S",
            f"           = 8100×({e['C']/100:.4f}) + 34000×({e['H']/100:.4f} - {e['O']/100:.4f}/8) + 2500×({e['S']/100:.4f})",
            f"           = {r['hhv']:,.1f} kcal/kg",
            f"     • LHV = HHV - 600×(9×H + W)",
            f"           = {r['hhv']:,.1f} - 600×(9×{e['H']/100:.4f} + {e['W']/100:.4f})",
            f"           = {r['lhv']:,.1f} kcal/kg",
            "",
            "■ 2. 연소 필요 공기량 상세 산출 계산과정",
            subline,
            "  [Step 1] 이론 산소량 (O₀) 산정",
            f"     • 공식 : O₀ = 1.867×C + 5.6×H + 0.7×S - 0.7×O",
            f"     • 계산 : 1.867×({e['C']/100:.4f}) + 5.6×({e['H']/100:.4f}) + 0.7×({e['S']/100:.4f}) - 0.7×({e['O']/100:.4f})",
            f"     • 결과 : {r['O0']:.3f} Sm³/kg",
            "",
            "  [Step 2] 이론 공기량 (A₀) 및 실제 공기량 (A) 산정",
            f"     • 공식 : A₀ = O₀ / 0.21 = {r['O0']:.3f} / 0.21 = {r['A0']:.3f} Sm³/kg",
            f"     • 공식 : A  = α × A₀ (적용 공연비 α = {r['alpha']:.2f})",
            f"     • 계산 : {r['alpha']:.2f} × {r['A0']:.3f}",
            f"     • 결과 : {r['A_actual']:.3f} Sm³/kg",
            "",
            "■ 3. 생성 가스량 상세 산출 계산과정",
            subline,
            "  [Step 1] 성분별 단위 생성 가스량 (Sm³/kg)",
            f"     • G_CO₂ = 1.867 × C = 1.867 × {e['C']/100:.4f} = {r['G_CO2']:.3f} Sm³/kg",
            f"     • G_SO₂ = 0.700 × S = 0.700 × {e['S']/100:.4f} = {r['G_SO2']:.4f} Sm³/kg",
            f"     • G_HCl = 0.630 × Cl = 0.630 × {e['Cl']/100:.4f} = {r['G_HCl']:.4f} Sm³/kg",
            f"     • G_H₂O = 11.2×H + 1.24×W = 11.2×({e['H']/100:.4f}) + 1.24×({e['W']/100:.4f}) = {r['G_H2O']:.3f} Sm³/kg",
            f"     • G_N₂  = 0.8×N + 0.79×A = 0.8×({e['N']/100:.4f}) + 0.79×({r['A_actual']:.3f}) = {r['G_N2']:.3f} Sm³/kg",
            f"     • G_O₂  = 0.21×(α - 1)×A₀ = 0.21×({r['alpha']:.2f} - 1)×{r['A0']:.3f} = {r['G_O2']:.3f} Sm³/kg",
            "",
            "  [Step 2] 건연소가스량 (Gd) 및 습연소가스량 (Gw)",
            f"     • Gd = G_CO₂ + G_SO₂ + G_HCl + G_N₂ + G_O₂ = {r['Gd']:.3f} Sm³/kg",
            f"     • Gw = Gd + G_H₂O = {r['Gd']:.3f} + {r['G_H2O']:.3f} = {r['Gw']:.3f} Sm³/kg",
            "",
            "  [Step 3] 처리량 기준 총 가스 유량 및 산소 농도",
            f"     • 총 건가스유량 (Gd_total) = Gd × W = {r['Gd']:.3f} × {tp:,.1f} = {r['total_Gd_h']:,.1f} Sm³/h",
            f"     • 총 습가스유량 (Gw_total) = Gw × W = {r['Gw']:.3f} × {tp:,.1f} = {r['total_Gw_h']:,.1f} Sm³/h",
            f"     • 배출가스 산소 농도 (O₂ %) = (G_O₂ / Gd) × 100 = {r['O2_percent']:.2f} %",
            "",
            "■ 4. 부산물(Ash), 스팀 및 스팀터빈 발전 에너지 수지",
            subline,
            "  [Step 1] 바닥재(Bottom Ash) 및 비산재(Fly Ash) 발생 물질수지",
            f"     • 총 회분(Ash) 발생량 = {tp:,.1f} kg/h × ({e['A']:.2f}/100) = {ash['total_ash']:,.2f} kg/h",
            f"     • 바닥재 (Bottom Ash) = 총 회분 × {ash['bottom_ash_ratio']:.1f}% = {ash['bottom_ash']:,.2f} kg/h",
            f"     • 비산재 (Fly Ash)   = 총 회분 × {ash['fly_ash_ratio']:.1f}% = {ash['fly_ash']:,.2f} kg/h",
            "",
            "  [Step 2] 폐열보일러(WHB) 스팀 물성치 및 증기 생산 수지",
            f"     • 증기 운전 조건   : 압력 P = {stm['p_steam']:.1f} kg/cm²G | 온도 T = {stm['t_steam']:.1f} °C",
            f"     • 급수 운전 조건   : 온도 T_feed = {stm['t_feed']:.1f} °C",
            f"     • 스팀 엔탈피 (hs) : {stm['h_steam']:.1f} kcal/kg  | 급수 엔탈피 (hf) : {stm['h_feed']:.1f} kcal/kg",
            f"     • 증발 필요 엔탈피 : Δh = hs - hf = {stm['delta_h']:.1f} kcal/kg",
            f"     • 폐열 회수 열량   : Q_rec = {stm['heat_rec']:,.0f} kcal/h",
            f"     • 증기 생산 능력   : Steam = Q_rec / Δh / 1000 = {stm['steam_prod']:.2f} ton/h",
            "",
            "  [Step 3] 스팀터빈(Steam Turbine) 발전 공정 및 전력 생산 수지",
        ]

        if turb["enabled"]:
            log.extend([
                f"     • 터빈 공급 증기 유량 : {turb['m_steam_kg_h']:,.1f} kg/h ({stm['steam_prod']:.2f} ton/h)",
                f"     • 터빈 엔탈피 강하량 : Δh_turb = {turb['delta_h_turb']:.1f} kcal/kg",
                f"     • 터빈/발전기 효율    : 기계효율 {turb['eta_mech']*100:.1f}%, 발전효율 {turb['eta_gen']*100:.1f}%",
                f"     • 순간 발전 출력 (Power): {turb['p_elec_kw']:,.2f} kWe ({turb['p_elec_mw']:.3f} MWe)",
                f"     • 예상 일일 발전량   : {turb['daily_kwh']:,.1f} kWh/day",
                f"     • 예상 연간 발전량   : {turb['annual_mwh']:,.1f} MWh/year (가동률 90% 기준)",
            ])
        else:
            log.append("     • 스팀터빈 발전 공정 미선택 (발전량 계산 미실행)")

        log.extend([
            "",
            "  [Step 4] 유인송풍기 (ID Fan) 동력",
            f"     • 유인송풍기 축동력 = {r['fan_power']:.2f} kW",
            line,
        ])
        self.txt_log.insert("1.0", "\n".join(log))

    def update_apcd_tab(self):
        self.txt_apcd.delete("1.0", "end")
        r = self.calc_res
        tp = r["throughput"]
        inc_gas = r["inc_outlet_gas"]

        cap_ton_h = tp / 1000.0
        cap_ton_d = cap_ton_h * 24.0

        if cap_ton_h >= 2.0:
            cap_cat = "시간당 2톤 이상 (대형 소각시설 기준 적용)"
            limit_dust, limit_sox, limit_hcl, limit_nox = 10.0, 30.0, 12.0, 50.0
        elif cap_ton_h >= 0.2:
            cap_cat = "시간당 200kg 이상 ~ 2톤 미만 (중형 소각시설 기준 적용)"
            limit_dust, limit_sox, limit_hcl, limit_nox = 15.0, 40.0, 15.0, 70.0
        else:
            cap_cat = "시간당 200kg 미만 (소형 소각시설 기준 적용)"
            limit_dust, limit_sox, limit_hcl, limit_nox = 20.0, 50.0, 20.0, 100.0

        line = "=" * 80
        subline = "-" * 80

        log = [
            line,
            f" 💨 [{r['inc_type']} 출구 오염물질 발생량 및 APCD 단계별 제거 현황]",
            line,
            "",
            f"■ 1. 소각로 출구가스 ({r['inc_type']}) 초기 오염물질 발생 현황",
            subline,
            f"  • 가스 온도 (Temperature)                  : {inc_gas['temp']:.0f} °C",
            f"  • 먼지/비산재 농도 (Dust/Fly Ash Conc.)     : {inc_gas['dust']:.1f} mg/Sm³ ({inc_gas['dust_mass']:.2f} kg/h)",
            f"  • 황산화물 농도 (SOx Conc.)                 : {inc_gas['sox']:.1f} ppm",
            f"  • 염화수소 농도 (HCl Conc.)                 : {inc_gas['hcl']:.1f} ppm",
            f"  • 질소산화물 농도 (NOx Conc.)               : {inc_gas['nox']:.1f} ppm",
            "",
            "■ 2. APCD 단계별 오염물질 농도 및 포집 수지",
            subline,
        ]

        for stg in r["apcd_stages"]:
            log.extend([
                f" ▶ [{stg['unit']}] ({stg['note']})",
                f"    - 배출 가스 온도     : {stg['temp']:.0f} °C (실가스량: {stg['q_act']:,.1f} m³/h)",
                f"    - 먼지 농도 / 질량   : {stg['dust']:.2f} mg/Sm³ | 잔여 Dust: {stg['dust_mass']:.2f} kg/h (포집 Fly Ash: {stg['collected_dust']:.2f} kg/h)",
                f"    - SOx 농도           : {stg['sox']:.2f} ppm",
                f"    - HCl 농도           : {stg['hcl']:.2f} ppm",
                f"    - NOx 농도           : {stg['nox']:.2f} ppm",
                ""
            ])

        chk_dust = "적합" if r['final_corr']['dust'] <= limit_dust else "❌ 초과"
        chk_sox  = "적합" if r['final_corr']['sox']  <= limit_sox  else "❌ 초과"
        chk_hcl  = "적합" if r['final_corr']['hcl']  <= limit_hcl  else "❌ 초과"
        chk_nox  = "적합" if r['final_corr']['nox']  <= limit_nox  else "❌ 초과"

        log.extend([
            "■ 3. 소각용량별 법적 규제 기준 대비 배출 농도 비교 (O₂ 12% 보정 기준)",
            subline,
            f"  • 설비 소각 용량   : {cap_ton_h:.2f} ton/h ({cap_ton_d:.1f} ton/일)",
            f"  • 적용 규제 등급   : [ {cap_cat} ]",
            "",
            "  ▶ 먼지 (Dust)",
            f"     • 최종 실측농도: {r['final_actual']['dust']:.2f} mg/Sm³ | O₂ 보정농도: {r['final_corr']['dust']:.2f} mg/Sm³",
            f"     • 법적 허용기준: {limit_dust:.2f} mg/Sm³  ➡️ [ 최종 판정: {chk_dust} ]",
            "",
            "  ▶ 황산화물 (SOx)",
            f"     • 최종 실측농도: {r['final_actual']['sox']:.2f} ppm     | O₂ 보정농도: {r['final_corr']['sox']:.2f} ppm",
            f"     • 법적 허용기준: {limit_sox:.2f} ppm       ➡️ [ 최종 판정: {chk_sox} ]",
            "",
            "  ▶ 염화수소 (HCl)",
            f"     • 최종 실측농도: {r['final_actual']['hcl']:.2f} ppm     | O₂ 보정농도: {r['final_corr']['hcl']:.2f} ppm",
            f"     • 법적 허용기준: {limit_hcl:.2f} ppm       ➡️ [ 최종 판정: {chk_hcl} ]",
            "",
            "  ▶ 질소산화물 (NOx)",
            f"     • 최종 실측농도: {r['final_actual']['nox']:.2f} ppm     | O₂ 보정농도: {r['final_corr']['nox']:.2f} ppm",
            f"     • 법적 허용기준: {limit_nox:.2f} ppm       ➡️ [ 최종 판정: {chk_nox} ]",
            line,
        ])
        self.txt_apcd.insert("1.0", "\n".join(log))

    def display_device_design(self, device_name):
        if not self.calc_res:
            self.txt_device_design.configure(state="normal")
            self.txt_device_design.delete("1.0", "end")
            self.txt_device_design.insert(
                "1.0",
                "⚠️ 먼저 좌측 메뉴에서 [연소 수지 및 장치 설계 연산] 버튼을 클릭하세요.",
            )
            return

        r = self.calc_res
        tp = r["throughput"]
        lhv = r["lhv"]
        Gw_h = r["total_Gw_h"]
        t_inc = self.incinerator_db[r["inc_type"]]["temp"]
        ash = r["ash_props"]
        stm = r["steam_props"]
        turb = r["turbine_props"]

        line = "=" * 80
        log = [
            line,
            f" ⚙️ [장치 상세 공학 설계 및 상세 계산과정] - {device_name}",
            line,
        ]

        if "Incinerator" in device_name or "소각로" in device_name:
            Q_th = tp * lhv
            q_v = 120000.0
            V_furnace = Q_th / q_v
            Q_act_m3s = (Gw_h * (273.15 + t_inc) / 273.15) / 3600.0
            retention_time = V_furnace / Q_act_m3s if Q_act_m3s > 0 else 0.0
            q_a = 250000.0
            A_grate = Q_th / q_a

            log.extend([
                "",
                f"■ 1. 기본 설계 기준 조건 ({r['inc_type']})",
                f"  • 소각 처리량 (W)       : {tp:,.1f} kg/h",
                f"  • 저위 발열량 (LHV)     : {lhv:,.1f} kcal/kg",
                f"  • 소각로 운전 온도 (T)   : {t_inc} °C",
                f"  • 연소가스 유량 (Gw)    : {Gw_h:,.1f} Sm³/h",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 바닥재(Bottom Ash) 및 비산재(Fly Ash) 분리 수지",
                "     🔗 [참고법령]: 환경부 폐기물관리법 시행규칙 [별표9] ( https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=245823 )",
                f"     • 총 회분(Ash) 발생량 = {tp:,.1f} kg/h × {r['elem_pct']['A']:.2f}% = {ash['total_ash']:.2f} kg/h",
                f"     • 바닥재 (Bottom Ash) 배출 = {ash['total_ash']:.2f} × {ash['bottom_ash_ratio']:.1f}% = {ash['bottom_ash']:.2f} kg/h",
                f"     • 이송 먼지 (Dust/Fly Ash) = {ash['total_ash']:.2f} × {ash['fly_ash_ratio']:.1f}% = {ash['fly_ash']:.2f} kg/h",
                "",
                "  [Step 2] 총 연소 발열량 (Q_thermal) 계산",
                "     🔗 [참고지침]: KECO 한국환경공단 소각시설 기술지침 ( https://www.keco.or.kr )",
                f"     • 공식 : Q_thermal = W × LHV",
                f"     • 계산 : {tp:,.1f} kg/h × {lhv:,.1f} kcal/kg = {Q_th:,.0f} kcal/h",
                "",
                "  [Step 3] 필요 연소로 용적 (V_furnace) 산정",
                "     🔗 [참고기준]: 환경부 소각로 설계 표준 (용적열부하 q_v = 100,000 ~ 150,000 kcal/m³·h)",
                f"     • 설계 용적 열부하 (q_v) : {q_v:,.0f} kcal/m³·h",
                f"     • 공식 : V_furnace = Q_thermal / q_v",
                f"     • 계산 : {Q_th:,.0f} / {q_v:,.0f} = {V_furnace:.2f} m³",
                "",
                "  [Step 4] 노내 체류시간 (Retention Time) 및 화격자 면적 산정",
                "     🔗 [참고보고서]: 국립환경과학원 소각로 고온 체류시간(2초 이상) 검증 지침 ( https://www.nier.go.kr )",
                f"     • 온도가스 유량 Q_actual = ({Gw_h:,.1f} / 3600) × (273.15 + {t_inc}) / 273.15 = {Q_act_m3s:.2f} m³/s",
                f"     • 체류시간(τ) = V_furnace / Q_actual = {V_furnace:.2f} / {Q_act_m3s:.2f} = {retention_time:.2f} 초",
                f"     • 화격자 필요 면적 A_grate = Q_thermal / {q_a:,.0f} = {A_grate:.2f} m²",
                line
            ])

        elif "WHB" in device_name:
            t_in, t_out = t_inc, 250.0
            Q_whb = stm["heat_rec"]
            Q_whb_kw = Q_whb * 1.163 / 1000.0
            dt1, dt2 = t_in - 180.0, t_out - 30.0
            lmtd = (dt1 - dt2) / math.log(dt1 / dt2) if dt1 != dt2 else dt1
            U = 35.0
            A_whb = (Q_whb_kw * 1000.0) / (U * lmtd) if lmtd > 0 else 0.0
            n_tubes = math.ceil(A_whb / (math.pi * 0.0508 * 6.0))

            log.extend([
                "",
                "■ 1. 기본 설계 및 스팀 물성치 조건",
                f"  • 입구/출구 가스 온도  : {t_in} °C ➡️ {t_out} °C  | 가스유량: {Gw_h:,.1f} Sm³/h",
                f"  • 증기 운전 압력 (P)    : {stm['p_steam']:.1f} kg/cm²G",
                f"  • 증기 및 급수 온도    : 증기 {stm['t_steam']:.1f} °C, 급수 {stm['t_feed']:.1f} °C",
                f"  • 엔탈피 물성치        : 증기 hs = {stm['h_steam']:.1f} kcal/kg, 급수 hf = {stm['h_feed']:.1f} kcal/kg",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 폐열 회수 열량 (Q_whb) 계산",
                "     🔗 [참고지침]: 한국에너지공단 열사용기자재 및 폐열보일러 설계 기준 ( https://www.energy.or.kr )",
                f"     • 공식 : Q_whb = Gw × Cp × (T_in - T_out)",
                f"     • 계산 : {Gw_h:,.1f} × 0.33 × ({t_in} - {t_out}) = {Q_whb:,.0f} kcal/h ({Q_whb_kw:,.1f} kW)",
                "",
                "  [Step 2] 스팀 증기 생산량 산정",
                "     🔗 [참고표준]: ASME Steam Tables & 열증기 수지 공식 ( https://www.asme.org )",
                f"     • 증발 필요 단위 엔탈피 Δh = hs - hf = {stm['h_steam']:.1f} - {stm['h_feed']:.1f} = {stm['delta_h']:.1f} kcal/kg",
                f"     • 공식 : Steam Production = Q_whb / Δh / 1000",
                f"     • 계산 : {Q_whb:,.0f} / {stm['delta_h']:.1f} / 1000 = {stm['steam_prod']:.2f} ton/h",
                "",
                "  [Step 3] LMTD 및 필요 전열면적 (A_whb) 산정",
                "     🔗 [참고문헌]: Perry's Chemical Engineers' Handbook (Heat Exchangers - https://www.accessengineeringlibrary.com )",
                f"     • LMTD = (ΔT1 - ΔT2) / ln(ΔT1 / ΔT2) = {lmtd:.1f} °C",
                f"     • A_whb = (Q_kw × 1000) / (U × LMTD) = ({Q_whb_kw:,.1f} × 1000) / ({U} × {lmtd:.1f}) = {A_whb:.2f} m²",
                f"     • 보일러 튜브 수량 (2인치×6m 기준): {n_tubes} EA",
                line
            ])

        elif "Steam Turbine" in device_name or "스팀터빈" in device_name:
            p_thermal_kw = turb["m_steam_kg_h"] * turb["delta_h_turb"] * (1.163 / 1000.0)

            log.extend([
                "",
                "■ 1. 기본 설계 및 운전 조건 (Steam Turbine Generator)",
                f"  • 스팀 공급 유량 (m_steam) : {turb['m_steam_kg_h']:,.1f} kg/h ({stm['steam_prod']:.2f} ton/h)",
                f"  • 증기 입구 압력/온도      : P = {stm['p_steam']:.1f} kg/cm²G, T = {stm['t_steam']:.1f} °C",
                f"  • 터빈 엔탈피 강하량 (Δh) : {turb['delta_h_turb']:.1f} kcal/kg",
                f"  • 터빈 기계 효율 (η_mech)  : {turb['eta_mech']*100:.1f} %",
                f"  • 발전기 변환 효율 (η_gen) : {turb['eta_gen']*100:.1f} %",
                "",
                "■ 2. 단계별 전력 발전량 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 터빈 유입 열에너지 출력 (P_thermal) 산정",
                "     🔗 [참고보고서]: 한국전력공사 및 에너지공단 소규모 발전효율 산정 지침 ( https://www.energy.or.kr )",
                f"     • 공식 : P_thermal = m_steam × Δh_turb × 0.001163",
                f"     • 계산 : {turb['m_steam_kg_h']:,.1f} kg/h × {turb['delta_h_turb']:.1f} kcal/kg × 0.001163",
                f"     • 결과 : {p_thermal_kw:,.2f} kWth",
                "",
                "  [Step 2] 최종 전기 발전 출력 (P_elec) 산정",
                "     🔗 [참고표준]: ASME Performance Test Codes (PTC 6 - Steam Turbines - https://www.asme.org )",
                f"     • 공식 : P_elec = P_thermal × η_mech × η_gen",
                f"     • 계산 : {p_thermal_kw:,.2f} kWth × {turb['eta_mech']} × {turb['eta_gen']}",
                f"     • 결과 : {turb['p_elec_kw']:,.2f} kWe ({turb['p_elec_mw']:.3f} MWe)",
                "",
                "  [Step 3] 가동 기간별 예상 전력 생산량 산출",
                f"     • 일간 발전량 (24h 기준)   : {turb['p_elec_kw']:,.2f} kW × 24h = {turb['daily_kwh']:,.1f} kWh/day",
                f"     • 연간 발전량 (가동률 90%) : {turb['p_elec_mw']:.3f} MW × 8760h × 0.90 = {turb['annual_mwh']:,.1f} MWh/year",
                line
            ])

        elif "SNCR" in device_name:
            nox_in = r["inc_outlet_gas"]["nox"]
            nox_removed_kg = (nox_in * 0.55) * (r["total_Gd_h"] / 1e6) * (46.0 / 22.4)
            ammonia_feed = nox_removed_kg * (17.0 / 46.0) * 1.8

            log.extend([
                "",
                "■ 1. 기본 설계 기준 조건",
                f"  • 건연소가스 유량 (Gd) : {r['total_Gd_h']:,.1f} Sm³/h",
                f"  • 유입 NOx 농도        : {nox_in:.1f} ppm",
                f"  • 목표 NOx 제거 효율   : 55 % (반응 온도 창: 850°C ~ 1050°C)",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 제거 대상 NOx 질량 유량 계산",
                "     🔗 [참고보고서]: 국립환경과학원 대기오염방지기술(SNCR) 가이드라인 ( https://www.nier.go.kr )",
                f"     • 공식 : M_NOx = (NOx_in × 0.55) × (Gd / 10^6) × (46 / 22.4) = {nox_removed_kg:.2f} kg/h",
                "",
                "  [Step 2] 순수 암모니아 (NH₃) 및 25% 암모니아수 소요량 계산",
                "     🔗 [참고문헌]: US EPA Air Pollution Control Cost Manual Ch.1 (NOx Controls - https://www.epa.gov/catc )",
                f"     • 화학 몰비 (NSR) : 1.8 적용",
                f"     • 공식 : NH3_pure = M_NOx × (17.0 / 46.0) × 1.8 = {ammonia_feed:.2f} kg/h",
                f"     • 25% 암모니아수 필요량 = {ammonia_feed * 4:.2f} kg/h",
                line
            ])

        elif "Cyclone" in device_name:
            Q_act_m3h = Gw_h * ((273.15 + 250.0) / 273.15)
            Q_act_m3s = Q_act_m3h / 3600.0
            v_in = 18.0
            A_in = Q_act_m3s / v_in
            D_cyclone = math.sqrt(A_in / 0.125)
            H_total = D_cyclone * 4.0

            log.extend([
                "",
                "■ 1. 기본 설계 기준 조건",
                f"  • 처리가스량 (Gw)   : {Gw_h:,.1f} Sm³/h (운전온도: 250 °C)",
                f"  • 권장 입구 유속(Vin) : {v_in} m/s",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 온도가스 유량 (Q_actual) 및 입구 면적 (A_in) 산정",
                "     🔗 [참고지침]: 한국환경공단 방지시설 설계 파라미터 ( https://www.keco.or.kr )",
                f"     • Q_act = ({Gw_h:,.1f} / 3600) × 1.915 = {Q_act_m3s:.2f} m³/s ({Q_act_m3h:,.1f} m³/h)",
                f"     • A_in = Q_act / Vin = {Q_act_m3s:.2f} / {v_in} = {A_in:.3f} m²",
                "",
                "  [Step 2] 싸이클론 몸통 직경 (D) 및 전체 높이 (H) 계산",
                "     🔗 [참고표준]: US EPA Air Pollution Control Cost Manual - Cyclone Design ( https://www.epa.gov/catc )",
                f"     • 공식 : D = √(A_in / 0.125) = √({A_in:.3f} / 0.125) = {D_cyclone:.2f} m",
                f"     • 결과 : 싸이클론 전체 높이 H = {H_total:.2f} m",
                line
            ])

        elif "SDR" in device_name:
            Q_act_m3h = Gw_h * ((273.15 + 160.0) / 273.15)
            Q_act_m3s = Q_act_m3h / 3600.0
            tau_sdr = 12.0
            V_sdr = Q_act_m3s * tau_sdr
            v_down = 0.4
            A_sdr = Q_act_m3s / v_down
            D_sdr = math.sqrt((4 * A_sdr) / math.pi)
            H_sdr = V_sdr / A_sdr

            slurry_caoh2 = (
                (r["inc_outlet_gas"]["hcl"] * 0.90 * 0.5 + r["inc_outlet_gas"]["sox"] * 0.85 * 1.0)
                * (r["total_Gd_h"] / 1e6)
                * (74.1 / 22.4)
                * 1.4
            )

            log.extend([
                "",
                "■ 1. 기본 설계 기준 조건",
                f"  • 처리가스량 (Gw)    : {Gw_h:,.1f} Sm³/h (반응 온도: 160 °C)",
                f"  • 목표 가스 체류시간 : {tau_sdr} 초 | 탑 내 하향 유속 : {v_down} m/s",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 반응탑 필요 부피 (V_sdr) 및 제원 계산",
                "     🔗 [참고보고서]: 국립환경과학원 SDR 반건식 반응탑 최적 체류시간(10~15초) 지침 ( https://www.nier.go.kr )",
                f"     • V_sdr = Q_act × 체류시간(τ) = {Q_act_m3s:.2f} × {tau_sdr} = {V_sdr:.2f} m³",
                f"     • 단면적 A_sdr = Q_act / v_down = {A_sdr:.2f} m²",
                f"     • 내경 D = √(4 × A_sdr / π) = {D_sdr:.2f} m | 탑 높이 H = {H_sdr:.2f} m",
                "",
                "  [Step 2] 중화용 소석회 (Ca(OH)₂) 필요 투입량 산정",
                "     🔗 [참고문헌]: 환경부 대기오염방지기술 모범사례집 (당량비 SR 1.3~1.5 적용)",
                f"     • 당량비(SR) : 1.4 적용 (HCl 90% 제거, SOx 85% 제거)",
                f"     • 결과 : Ca(OH)₂ 소요량 = {slurry_caoh2:.2f} kg/h",
                line
            ])

        elif "Bag Filter" in device_name:
            Q_act_m3min = (Gw_h * ((273.15 + 160.0) / 273.15)) / 60.0
            vf = 1.0
            A_filter = Q_act_m3min / vf
            bag_area = math.pi * 0.15 * 6.0
            total_bags = math.ceil(A_filter / bag_area)
            comp_count = 4
            bags_per_comp = math.ceil(total_bags / comp_count)

            log.extend([
                "",
                "■ 1. 기본 설계 기준 조건",
                f"  • 처리가스량 (Gw)       : {Gw_h:,.1f} Sm³/h (여과 온도: 160 °C)",
                f"  • 설계 여과속도 (vf)    : {vf} m/min",
                f"  • 여과 백 규격         : 직경(D) 0.15 m × 길이(L) 6.0 m",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 총 필요 여과면적 (A_filter) 산정",
                "     🔗 [참고지침]: 한국대기환경학회 여과집진기 설계 파라미터 (vf = 0.8~1.2 m/min - http://www.kosae.or.kr )",
                f"     • Q_act = ({Gw_h:,.1f} / 60) × 1.586 = {Q_act_m3min:,.2f} m³/min",
                f"     • A_filter = Q_act / vf = {Q_act_m3min:,.2f} / {vf} = {A_filter:.2f} m²",
                "",
                "  [Step 2] 필요 백 수량 (N_total) 및 Room 분할 배치",
                "     🔗 [참고보고서]: US EPA Fabric Filter Design Manual ( https://www.epa.gov/catc )",
                f"     • 백 1개 표면적 = π × 0.15 × 6.0 = {bag_area:.2f} m²",
                f"     • 총 필요 백 수량 = {A_filter:.2f} / {bag_area:.2f} = {total_bags} 개 (정수화)",
                f"     • {comp_count}개 Rooms 분할 시 : Room당 {bags_per_comp} EA",
                line
            ])

        elif "SCR" in device_name:
            Q_act_m3h = Gw_h * ((273.15 + 180.0) / 273.15)
            sv = 4000.0
            v_cat = Q_act_m3h / sv

            log.extend([
                "",
                "■ 1. 기본 설계 기준 조건",
                f"  • 처리가스량 (Gw)       : {Gw_h:,.1f} Sm³/h (반응 온도: 180 °C)",
                f"  • 공간속도 (SV)         : {sv:,.0f} 1/h",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 필요 촉매 부피 (V_catalyst) 산정",
                "     🔗 [참고보고서]: 국립환경과학원 SCR 최적 촉매 공간속도(SV 3000~5000 1/h) 지침 ( https://www.nier.go.kr )",
                f"     • Q_act = {Gw_h:,.1f} × 1.659 = {Q_act_m3h:,.1f} m³/h",
                f"     • V_catalyst = Q_act / SV = {Q_act_m3h:,.1f} / {sv:,.0f} = {v_cat:.2f} m³",
                line
            ])

        elif "ID Fan" in device_name or "유인송풍기" in device_name:
            delta_p = 380.0
            flow_m3h = r["act_gas_flow_m3h"]
            eta_fan = 0.65
            kw = (flow_m3h * delta_p) / (3600.0 * 102.0 * eta_fan)
            motor_kw = kw * 1.15

            log.extend([
                "",
                "■ 1. 기본 설계 기준 조건",
                f"  • 유인 통풍 가스량    : {flow_m3h:,.1f} m³/h",
                f"  • 총 공정 압력손실 (ΔP) : {delta_p} mmH₂O | 팬 효율 (η) : {eta_fan*100:.0f} %",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 유인송풍기 축동력 (Shaft Power) 및 모터 용량 계산",
                "     🔗 [참고지침]: KECO 송풍기 축동력 및 전력 소요량 공식 ( https://www.keco.or.kr )",
                f"     • 축동력 공식 : P_shaft = (Q_act × ΔP) / (3600 × 102 × η)",
                f"     • 계산 : ({flow_m3h:,.1f} × {delta_p}) / (3600 × 102 × {eta_fan}) = {kw:.2f} kW",
                f"     • 모터 정격 용량 (안전율 15% 적용) : {kw:.2f} × 1.15 = {motor_kw:.2f} kW",
                line
            ])

        elif "Stack" in device_name:
            Q_act_m3h = Gw_h * ((273.15 + 140.0) / 273.15)
            Q_act_m3s = Q_act_m3h / 3600.0
            v_stack = 16.0
            A_stack = Q_act_m3s / v_stack
            D_stack = math.sqrt((4 * A_stack) / math.pi)

            log.extend([
                "",
                "■ 1. 기본 설계 기준 조건",
                f"  • 토출 가스량 (Gw)     : {Gw_h:,.1f} Sm³/h (토출 온도: 140 °C)",
                f"  • 설계 토출 유속 (V)   : {v_stack} m/s",
                "",
                "■ 2. 단계별 산출 계산 과정 및 참고문헌 링크",
                "  [Step 1] 굴뚝 단면적 (A_stack) 및 내경 (D) 산정",
                "     🔗 [참고법령]: 환경부 대기환경보전법 굴뚝 확산 및 최소 유속 기준 ( https://www.law.go.kr )",
                f"     • Q_act = {Q_act_m3s:.2f} m³/s ({Q_act_m3h:,.1f} m³/h)",
                f"     • A_stack = Q_act / V = {Q_act_m3s:.2f} / {v_stack} = {A_stack:.3f} m²",
                f"     • 굴뚝 내경 D = √(4 × A_stack / π) = {D_stack:.2f} m (권장 최소 높이: 35.0 m)",
                line
            ])

        # 하이퍼링크가 적용된 텍스트 렌더링 호출
        self.append_text_with_links(self.txt_device_design, "\n".join(log))

    def render_pfd_diagram(self):
        for w in self.frame_pfd.winfo_children():
            w.destroy()

        if not self.calc_res:
            return

        r = self.calc_res

        fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        inc_label = r["inc_short_name"]

        units = (
            [inc_label]
            + [s["unit"] for s in r["apcd_stages"]]
            + ["Stack"]
        )
        x_coords = np.linspace(0.07, 0.87, len(units))
        y_box = 0.35
        box_w = 0.085
        box_h = 0.20

        for i, unit in enumerate(units):
            x = x_coords[i]

            rect = mpatches.FancyBboxPatch(
                (x - box_w / 2, y_box),
                box_w,
                box_h,
                boxstyle="round,pad=0.01",
                ec="#1C7ED6",
                fc="#E7F5FF",
                lw=2,
            )
            ax.add_patch(rect)

            cx = x
            cy = y_box + box_h / 2 + 0.02

            if i == 0:
                furnace = mpatches.Rectangle((cx - 0.02, cy - 0.04), 0.04, 0.07, fc="#FFA8A8", ec="#E03131", lw=1.5)
                ax.add_patch(furnace)
            elif unit == "WHB":
                whb_box = mpatches.Rectangle((cx - 0.025, cy - 0.04), 0.05, 0.07, fc="#D0EBFF", ec="#1971C2", lw=1.5)
                ax.add_patch(whb_box)
            elif unit == "SNCR":
                sncr_box = mpatches.Rectangle((cx - 0.02, cy - 0.04), 0.04, 0.07, fc="#EEBFA3", ec="#D9480F", lw=1.5)
                ax.add_patch(sncr_box)
            elif unit == "Cyclone":
                cyl = mpatches.Rectangle((cx - 0.02, cy - 0.01), 0.04, 0.04, fc="#FCC2D7", ec="#C2255C", lw=1.5)
                ax.add_patch(cyl)
            elif unit == "SDR":
                sdr_tower = mpatches.Rectangle((cx - 0.02, cy - 0.02), 0.04, 0.05, fc="#E9FAC8", ec="#66A80F", lw=1.5)
                ax.add_patch(sdr_tower)
            elif unit == "Bag Filter":
                bf_box = mpatches.Rectangle((cx - 0.025, cy - 0.04), 0.05, 0.07, fc="#FFF3BF", ec="#F59F00", lw=1.5)
                ax.add_patch(bf_box)
            elif unit == "SCR":
                scr_box = mpatches.Rectangle((cx - 0.02, cy - 0.04), 0.04, 0.07, fc="#D3F9D8", ec="#2B8A3E", lw=1.5)
                ax.add_patch(scr_box)
            elif unit == "Stack":
                stack_bar = mpatches.Polygon([[cx - 0.015, cy - 0.045], [cx + 0.015, cy - 0.045], [cx + 0.01, cy + 0.03], [cx - 0.01, cy + 0.03]], fc="#CED4DA", ec="#343A40", lw=1.5)
                ax.add_patch(stack_bar)

            ax.text(x, y_box + 0.04, unit, ha="center", va="center", fontsize=8.5, color="#1864AB")

            # 스팀터빈 연계
            if unit == "WHB" and r["turbine_props"]["enabled"]:
                turb = r["turbine_props"]
                y_st = y_box + box_h + 0.16
                
                ax.annotate(
                    "",
                    xy=(cx, y_st),
                    xytext=(cx, y_box + box_h),
                    arrowprops=dict(arrowstyle="-|>", color="#1971C2", lw=1.8, ls="--", mutation_scale=10),
                )
                
                st_box = mpatches.FancyBboxPatch(
                    (cx - 0.045, y_st),
                    0.09,
                    0.12,
                    boxstyle="round,pad=0.01",
                    ec="#D9480F",
                    fc="#FFF3BF",
                    lw=1.8,
                )
                ax.add_patch(st_box)
                
                ax.text(
                    cx,
                    y_st + 0.08,
                    "Steam Turbine\nGenerator",
                    ha="center",
                    va="center",
                    fontsize=7.5,
                    color="#D9480F",
                )
                ax.text(
                    cx,
                    y_st + 0.03,
                    f"⚡ {turb['p_elec_kw']:,.1f} kWe\n({turb['p_elec_mw']:.3f} MWe)",
                    ha="center",
                    va="center",
                    fontsize=7.0,
                    color="#2B8A3E",
                )

            # 바닥재 배출
            if i == 0:
                bottom_ash_val = r["ash_props"]["bottom_ash"]
                ax.annotate(
                    "",
                    xy=(x, y_box - 0.12),
                    xytext=(x, y_box),
                    arrowprops=dict(arrowstyle="-|>", color="#5C3D2E", lw=1.5, mutation_scale=10),
                )
                ax.text(
                    x,
                    y_box - 0.16,
                    f"Bottom Ash:\n{bottom_ash_val:.1f} kg/h",
                    ha="center",
                    va="top",
                    fontsize=6.5,
                    color="#3E2723",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#EFEBE9", ec="#BCAAA4", lw=0.5)
                )

            # 가스 흐름
            if i < len(units) - 1:
                x_start = x + box_w / 2
                x_end = x_coords[i + 1] - box_w / 2
                y_pipe = y_box + box_h / 2

                ax.annotate(
                    "",
                    xy=(x_end, y_pipe),
                    xytext=(x_start, y_pipe),
                    arrowprops=dict(arrowstyle="-|>", color="#E03131", lw=2, mutation_scale=12),
                )

                if i == 0:
                    stg_info = r["inc_outlet_gas"]
                else:
                    stg_info = r["apcd_stages"][i - 1]

                info_txt = f"{stg_info['temp']:.0f}°C\n{stg_info['q_act']:,.0f} m³/h\nDust: {stg_info['dust_mass']:.1f}kg/h"
                ax.text(
                    (x_start + x_end) / 2,
                    y_pipe + 0.02,
                    info_txt,
                    ha="center",
                    va="bottom",
                    fontsize=6.5,
                    color="#C53030",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#FFF5F5", ec="#FFC9C9", lw=0.5)
                )
            else:
                x_start = x + box_w / 2
                x_end = min(0.98, x_start + 0.06)
                y_pipe = y_box + box_h / 2

                ax.annotate(
                    "",
                    xy=(x_end, y_pipe),
                    xytext=(x_start, y_pipe),
                    arrowprops=dict(arrowstyle="-|>", color="#2B8A3E", lw=2, mutation_scale=12),
                )

                last_stg = r["apcd_stages"][-1] if r["apcd_stages"] else r["inc_outlet_gas"]
                final_dust = r["final_actual"]["dust_mass"]

                info_txt = f"{last_stg['temp']:.0f}°C\n{last_stg['q_act']:,.0f} m³/h\nDust: {final_dust:.2f}kg/h"
                ax.text(
                    (x_start + x_end) / 2,
                    y_pipe + 0.02,
                    info_txt,
                    ha="center",
                    va="bottom",
                    fontsize=6.5,
                    color="#2B8A3E",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#E6FCF5", ec="#63E6BE", lw=0.5)
                )

            # 비산재 배출
            if i > 0 and i <= len(r["apcd_stages"]):
                stg = r["apcd_stages"][i - 1]
                if stg.get("collected_dust", 0) > 0:
                    ax.annotate(
                        "",
                        xy=(x, y_box - 0.12),
                        xytext=(x, y_box),
                        arrowprops=dict(arrowstyle="-|>", color="#795548", lw=1.5, mutation_scale=10),
                    )
                    ax.text(
                        x,
                        y_box - 0.16,
                        f"Fly Ash:\n{stg['collected_dust']:.1f} kg/h",
                        ha="center",
                        va="top",
                        fontsize=6.5,
                        color="#4E342E",
                        bbox=dict(boxstyle="round,pad=0.2", fc="#EFEBE9", ec="#D7CCC8", lw=0.5)
                    )

        ax.set_title(f"전체 공정도 및 물질/가스/스팀터빈 발전 PFD ({r['inc_type']} 연계)", fontsize=13, pad=15)
        canvas = FigureCanvasTkAgg(fig, master=self.frame_pfd)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def render_graphs(self):
        for w in self.frame_graph.winfo_children():
            w.destroy()

        if not self.calc_res:
            return

        r = self.calc_res

        inc_label = r["inc_short_name"]
        stages = [inc_label] + [s["unit"] for s in r["apcd_stages"]]

        dust_vals = [r["inc_outlet_gas"]["dust"]] + [s["dust"] for s in r["apcd_stages"]]
        sox_vals = [r["inc_outlet_gas"]["sox"]] + [s["sox"] for s in r["apcd_stages"]]
        hcl_vals = [r["inc_outlet_gas"]["hcl"]] + [s["hcl"] for s in r["apcd_stages"]]
        nox_vals = [r["inc_outlet_gas"]["nox"]] + [s["nox"] for s in r["apcd_stages"]]

        fig, axes = plt.subplots(2, 2, figsize=(11, 6), dpi=100)

        # 1. 먼지
        axes[0, 0].plot(stages, dust_vals, marker="o", color="#D9480F", linewidth=2.0, markersize=5)
        axes[0, 0].set_title("1. 먼지/비산재 (Dust/Fly Ash) 농도 (mg/Sm³)", fontsize=10.5)
        axes[0, 0].grid(True, linestyle="--", alpha=0.6)
        axes[0, 0].tick_params(axis="x", rotation=15, labelsize=8)

        # 2. SOx
        axes[0, 1].plot(stages, sox_vals, marker="s", color="#1971C2", linewidth=2.0, markersize=5)
        axes[0, 1].set_title("2. 황산화물 (SOx) 농도 변화 (ppm)", fontsize=10.5)
        axes[0, 1].grid(True, linestyle="--", alpha=0.6)
        axes[0, 1].tick_params(axis="x", rotation=15, labelsize=8)

        # 3. HCl
        axes[1, 0].plot(stages, hcl_vals, marker="^", color="#E67E22", linewidth=2.0, markersize=5)
        axes[1, 0].set_title("3. 염화수소 (HCl) 농도 변화 (ppm)", fontsize=10.5)
        axes[1, 0].grid(True, linestyle="--", alpha=0.6)
        axes[1, 0].tick_params(axis="x", rotation=15, labelsize=8)

        # 4. NOx
        axes[1, 1].plot(stages, nox_vals, marker="d", color="#2B8A3E", linewidth=2.0, markersize=5)
        axes[1, 1].set_title("4. 질소산화물 (NOx) 농도 변화 (ppm)", fontsize=10.5)
        axes[1, 1].grid(True, linestyle="--", alpha=0.6)
        axes[1, 1].tick_params(axis="x", rotation=15, labelsize=8)

        fig.suptitle(f"▶ {r['inc_type']} 출구 기준 APCD 공정 단계별 오염물질 프로파일", fontsize=12.5)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.frame_graph)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


if __name__ == "__main__":
    app = IncinerationSystemApp()
    app.mainloop()
