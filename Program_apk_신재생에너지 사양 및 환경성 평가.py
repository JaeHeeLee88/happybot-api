import ctypes
import math
import os
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


def resource_path(relative_path):
    """PyInstaller 임시 실행 경로(_MEIPASS) 또는 현재 디렉토리의 파일 절대 경로를 반환합니다."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def init_font_system():
    """Windows API(gdi32)를 이용해 폰트 파일(.ttf)을 프로세스 메모리에 강제로 동적 등록합니다."""
    if sys.platform.startswith("win"):
        FR_PRIVATE = 0x10  # 현재 프로세스 내에서만 폰트 사용

        # 1. PyInstaller exe 내부 번들로 포함된 폰트 파일 등록 시도
        font_filename = "malgun.ttf"
        bundled_font_path = resource_path(font_filename)

        if os.path.exists(bundled_font_path):
            ctypes.windll.gdi32.AddFontResourceExW(
                bundled_font_path, FR_PRIVATE, 0
            )
        else:
            # 2. 번들 파일이 없을 경우 개발 PC 내 C:\Windows\Fonts 경로의 폰트 직접 등록 시도
            system_font_path = os.path.join(
                os.environ.get("WINDIR", r"C:\Windows"), "Fonts", font_filename
            )
            if os.path.exists(system_font_path):
                ctypes.windll.gdi32.AddFontResourceExW(
                    system_font_path, FR_PRIVATE, 0
                )


class RenewableEnergyApp:

    def __init__(self, root):
        self.root = root
        self.root.title(
            "신재생에너지원별 통합 설계·사양·환경성 및 경제성(LCOE/ROI) 평가 시스템"
        )
        self.root.geometry("1500x950")

        # 폰트 오프셋 (기본 0)
        self.font_delta = 0

        # 세부 연료전지 타입 데이터베이스
        self.fc_types = {
            "PEMFC (고분자전해질형)": {
                "temp": "80 °C (저온형)",
                "eta_el": 45.0,
                "eta_th": 35.0,
                "desc": "수소차, 건물용, 수송용 주력 (순수 수소 연료 사용)",
                "nox_factor": 0.000,
                "flow": [
                    "순수 수소/공기 공급",
                    "PEM 고분자 막 반응",
                    "직류 전력 생성",
                    "인버터 변환",
                    "전력 및 80°C 온수 이용",
                ],
            },
            "PAFC (인산형)": {
                "temp": "200 °C (중온형)",
                "eta_el": 42.0,
                "eta_th": 43.0,
                "desc": "발전용·건물용 열병합 발전 (LNG 개질 수소 활용)",
                "nox_factor": 0.005,
                "flow": [
                    "LNG/수소 공급",
                    "인산 전해질 반응(200°C)",
                    "직류 전력 생성",
                    "인버터 변환",
                    "전력 및 중온 증기 활용",
                ],
            },
            "MCFC (용융탄산염형)": {
                "temp": "650 °C (고온형)",
                "eta_el": 47.0,
                "eta_th": 38.0,
                "desc": "대용량 발전용 (내부 개질 가능, 고온 폐열 활용)",
                "nox_factor": 0.008,
                "flow": [
                    "합성가스/LNG 공급",
                    "용융탄산염 전해질 반응",
                    "고온 전기화학 반응",
                    "PCS 변환",
                    "전력 및 고온 스팀 회수",
                ],
            },
            "SOFC (고체산화물형)": {
                "temp": "750 °C ~ 1000 °C (초고온형)",
                "eta_el": 55.0,
                "eta_th": 30.0,
                "desc": "고효율 발전용 (최고 수준 전기효율, 복합발전 가능)",
                "nox_factor": 0.003,
                "flow": [
                    "연료 gas (H2/NG) 공급",
                    "세라믹 고체전해질 반응",
                    "고효율 직류 발전",
                    "인버터 변환",
                    "전력 및 초고온 폐열 이용",
                ],
            },
        }

        # 에너지원 데이터베이스 (설계 변수 + 경제성 변수)
        self.energy_db = {
            "1. 태양광 (Solar PV)": {
                "category": "재생에너지",
                "inputs": [
                    ("설치 면적 (A)", 500, "m²"),
                    ("수평면 일사량 (G)", 1000, "W/m²"),
                    ("모듈 변환 효율 (η)", 20.0, "%"),
                    ("모듈 동작 온도 (T)", 45, "°C"),
                    ("온도 계수 (γ)", 0.4, "%/°C"),
                    ("시스템 종합 효율 (PR)", 85.0, "%"),
                    ("초기 투자비 (CAPEX)", 12000, "만원"),
                    ("연간 유지관리비 (OPEX)", 150, "만원/년"),
                    ("전력 판매단가 (SMP+REC)", 160, "원/kWh"),
                    ("내용연수 (Lifespan)", 25, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "태양광 입사",
                    "PN접합 반도체",
                    "직류(DC) 전력",
                    "인버터(AC변환)",
                    "전력 계통 연계",
                ],
                "calc_fn": self.calc_solar_pv,
            },
            "2. 태양열 (Solar Thermal)": {
                "category": "재생에너지",
                "inputs": [
                    ("집열기 면적 (A)", 100, "m²"),
                    ("일사량 (G)", 800, "W/m²"),
                    ("집열기 기준 효율 (η0)", 75.0, "%"),
                    ("1차 손실 계수 (a1)", 3.5, "W/m²·K"),
                    ("평균 집열 온도 (Tm)", 60, "°C"),
                    ("외기 온도 (Ta)", 15, "°C"),
                    ("초기 투자비 (CAPEX)", 4000, "만원"),
                    ("연간 유지관리비 (OPEX)", 60, "만원/년"),
                    ("열 생산 가치 단가", 120, "원/kWh"),
                    ("내용연수 (Lifespan)", 20, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "태양 집열",
                    "집열판 흡수",
                    "열매체 유체 수송",
                    "열교환기",
                    "온수/난방 공급",
                ],
                "calc_fn": self.calc_solar_thermal,
            },
            "3. 풍력 (Wind Power)": {
                "category": "재생에너지",
                "inputs": [
                    ("공기 밀도 (ρ)", 1.225, "kg/m³"),
                    ("로터 블레이드 반경 (R)", 40, "m"),
                    ("풍속 (v)", 10, "m/s"),
                    ("파워 계수 (Cp)", 0.45, "-"),
                    ("기계/발전기 효율 (η)", 90.0, "%"),
                    ("초기 투자비 (CAPEX)", 250000, "만원"),
                    ("연간 유지관리비 (OPEX)", 3500, "만원/년"),
                    ("전력 판매단가 (SMP+REC)", 170, "원/kWh"),
                    ("내용연수 (Lifespan)", 20, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "바람 운동에너지",
                    "블레이드 회전",
                    "증속기(Gearbox)",
                    "동기/유도 발전기",
                    "전력 출력",
                ],
                "calc_fn": self.calc_wind,
            },
            "4. 수력 (Hydro Power)": {
                "category": "재생에너지",
                "inputs": [
                    ("유량 (Q)", 2.5, "m³/s"),
                    ("유효 낙차 (H)", 15, "m"),
                    ("수차 효율 (η_t)", 88.0, "%"),
                    ("발전기 효율 (η_g)", 95.0, "%"),
                    ("초기 투자비 (CAPEX)", 100000, "만원"),
                    ("연간 유지관리비 (OPEX)", 1500, "만원/년"),
                    ("전력 판매단가 (SMP+REC)", 150, "원/kWh"),
                    ("내용연수 (Lifespan)", 30, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "취수 및 도수",
                    "낙차 수압 형성",
                    "수차(Turbine) 회전",
                    "발전기 연동",
                    "전력 생산",
                ],
                "calc_fn": self.calc_hydro,
            },
            "5. 지열 (Geothermal)": {
                "category": "재생에너지",
                "inputs": [
                    ("히트펌프 전력 (P_in)", 10, "kW"),
                    ("난방 성적계수 (COP)", 4.2, "-"),
                    ("지중 열교환기 길이당 열량", 50, "W/m"),
                    ("운전 시간", 8, "시간/일"),
                    ("초기 투자비 (CAPEX)", 2500, "만원"),
                    ("연간 유지관리비 (OPEX)", 30, "만원/년"),
                    ("열에너지 절감 단가", 130, "원/kWh"),
                    ("내용연수 (Lifespan)", 20, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "지중 열교환기",
                    "순환수 열흡수",
                    "히트펌프 압축",
                    "열교환 응축",
                    "건물 냉난방",
                ],
                "calc_fn": self.calc_geothermal,
            },
            "6. 해양 (Marine - 조력/파력)": {
                "category": "재생에너지",
                "inputs": [
                    ("해수 밀도 (ρ)", 1025, "kg/m³"),
                    ("조지 면적 (A)", 100000, "m²"),
                    ("조차 (H)", 5, "m"),
                    ("발전 효율 (η)", 80.0, "%"),
                    ("초기 투자비 (CAPEX)", 500000, "만원"),
                    ("연간 유지관리비 (OPEX)", 6000, "만원/년"),
                    ("전력 판매단가 (SMP+REC)", 180, "원/kWh"),
                    ("내용연수 (Lifespan)", 30, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "밀물/썰물 유입",
                    "수문 통과 및 수위차",
                    "해양 수차 회전",
                    "발전기 동작",
                    "전력 송전",
                ],
                "calc_fn": self.calc_marine,
            },
            "7. 바이오 (Bioenergy)": {
                "category": "재생에너지",
                "inputs": [
                    ("바이오가스 유량 (Q)", 50, "m³/h"),
                    ("메탄 함량 (CH4)", 60.0, "%"),
                    ("메탄 저위발열량 (LHV)", 35.8, "MJ/m³"),
                    ("발전 효율 (η_e)", 35.0, "%"),
                    ("열회수 효율 (η_th)", 45.0, "%"),
                    ("초기 투자비 (CAPEX)", 80000, "만원"),
                    ("연간 유지관리비 (OPEX)", 2000, "만원/년"),
                    ("복합 판매 단가 (전력+열)", 170, "원/kWh"),
                    ("내용연수 (Lifespan)", 20, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "유기성 폐기물",
                    "혐기성 발효",
                    "바이오가스 포집",
                    "열병합 발전기",
                    "전력 및 열 생산",
                ],
                "calc_fn": self.calc_bio,
            },
            "8. 수열 (Hydro-thermal)": {
                "category": "재생에너지",
                "inputs": [
                    ("유수 유량 (Q)", 100, "m³/h"),
                    ("유수 입출구 온도차 (ΔT)", 5, "°C"),
                    ("물 비열 (Cp)", 4.186, "kJ/kg·°C"),
                    ("히트펌프 COP", 4.5, "-"),
                    ("초기 투자비 (CAPEX)", 6000, "만원"),
                    ("연간 유지관리비 (OPEX)", 100, "만원/년"),
                    ("열 절감 가치 단가", 130, "원/kWh"),
                    ("내용연수 (Lifespan)", 20, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "하천수/해수 취수",
                    "수열 열교환기",
                    "히트펌프 냉매열 transfer",
                    "에너지 증폭",
                    "지역 냉난방",
                ],
                "calc_fn": self.calc_hydro_thermal,
            },
            "9. 폐기물 (Waste Energy)": {
                "category": "재생에너지",
                "inputs": [
                    ("소각 폐기물량 (m)", 2, "ton/h"),
                    ("폐기물 발열량 (LHV)", 12000, "kJ/kg"),
                    ("보일러 열효율 (η_b)", 75.0, "%"),
                    ("스팀터빈 발전효율 (η_t)", 20.0, "%"),
                    ("초기 투자비 (CAPEX)", 600000, "만원"),
                    ("연간 유지관리비 (OPEX)", 15000, "만원/년"),
                    ("에너지 판매 단가", 140, "원/kWh"),
                    ("내용연수 (Lifespan)", 20, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "폐기물 투입",
                    "소각로 연소",
                    "폐열보일러 증기",
                    "증기 터빈 회전",
                    "전력/증기 공급",
                ],
                "calc_fn": self.calc_waste,
            },
            "10. 수소 (Hydrogen)": {
                "category": "신에너지",
                "inputs": [
                    ("수전해 공급 전력 (P_el)", 100, "kW"),
                    ("수전해 시스템 효율 (η_sys)", 70.0, "%"),
                    ("수소 저위발열량 (LHV)", 33.3, "kWh/kg"),
                    ("초기 투자비 (CAPEX)", 200000, "만원"),
                    ("연간 유지관리비 (OPEX)", 4000, "만원/년"),
                    ("수소 판매/가치 단가", 350, "원/kWh 등가"),
                    ("내용연수 (Lifespan)", 15, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "전력/순수 공급",
                    "수전해 스택(PEM/AEC)",
                    "수소/산소 분리",
                    "정제 및 압축",
                    "수소 저장",
                ],
                "calc_fn": self.calc_hydrogen,
            },
            "11. 연료전지 (Fuel Cell)": {
                "category": "신에너지",
                "inputs": [
                    ("수소 소모량 (m_H2)", 5.0, "kg/h"),
                    ("발전 효율 (η_el)", 45.0, "%"),
                    ("열회수 효율 (η_th)", 35.0, "%"),
                    ("수소 저위발열량 (LHV)", 33.3, "kWh/kg"),
                    ("초기 투자비 (CAPEX)", 150000, "만원"),
                    ("연간 유지관리비 (OPEX)", 3000, "만원/년"),
                    ("전력+열 판매 단가", 220, "원/kWh"),
                    ("내용연수 (Lifespan)", 20, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "순수 수소/공기 공급",
                    "PEM 고분자 막 반응",
                    "직류 전력 생성",
                    "인버터 변환",
                    "전력 및 80°C 온수 이용",
                ],
                "calc_fn": self.calc_fuel_cell,
            },
            "12. 석탄 가스화·액화 (IGCC)": {
                "category": "신에너지",
                "inputs": [
                    ("석탄 투입량 (m)", 10, "ton/h"),
                    ("석탄 발열량 (LHV)", 25000, "kJ/kg"),
                    ("가스화炉 효율 (η_g)", 80.0, "%"),
                    ("복합발전 효율 (η_cc)", 45.0, "%"),
                    ("초기 투자비 (CAPEX)", 1500000, "만원"),
                    ("연간 유지관리비 (OPEX)", 35000, "만원/년"),
                    ("전력 판매단가", 150, "원/kWh"),
                    ("내용연수 (Lifespan)", 30, "년"),
                    ("할인율 (r)", 4.5, "%"),
                ],
                "flow": [
                    "석탄 미분화",
                    "고온/고압 가스화",
                    "합성가스(Syngas) 정제",
                    "가스터빈/증기터빈",
                    "복합 발전",
                ],
                "calc_fn": self.calc_igcc,
            },
        }

        self.input_entries = {}
        self.fc_type_combo = None
        self.setup_ui()

    def get_font(self, base_size, bold=False):
        """폰트 크기를 동적으로 계산하여 반환"""
        sz = max(6, int(base_size + self.font_delta))
        weight = "bold" if bold else "normal"
        return ("맑은 고딕", sz, weight)

    def setup_ui(self):
        # 상단 타이틀
        self.title_frame = tk.Frame(self.root, bg="#1E293B", height=50)
        self.title_frame.pack(fill=tk.X, side=tk.TOP)

        self.title_label = tk.Label(
            self.title_frame,
            text="신재생에너지원별 통합 설계·사양·환경성·경제성(LCOE/ROI) 평가 시스템",
            font=self.get_font(13, True),
            fg="white",
            bg="#1E293B",
            pady=8,
        )
        self.title_label.pack(side=tk.LEFT, padx=15)

        # 컨트롤 바 (에너지원 선택 + 폰트 사이즈 제어)
        self.select_frame = tk.Frame(self.root, bg="#334155", pady=6)
        self.select_frame.pack(fill=tk.X, side=tk.TOP)

        self.lbl_select = tk.Label(
            self.select_frame,
            text="에너지원 선택:",
            font=self.get_font(10, True),
            fg="white",
            bg="#334155",
        )
        self.lbl_select.pack(side=tk.LEFT, padx=(15, 5))

        self.energy_var = tk.StringVar()
        self.combo = ttk.Combobox(
            self.select_frame,
            textvariable=self.energy_var,
            state="readonly",
            font=self.get_font(10),
            width=28,
        )
        self.combo["values"] = list(self.energy_db.keys())
        self.combo.current(0)
        self.combo.pack(side=tk.LEFT, padx=5)
        self.combo.bind("<<ComboboxSelected>>", self.on_energy_change)

        self.category_label = tk.Label(
            self.select_frame,
            text="",
            font=self.get_font(10, True),
            fg="#38BDF8",
            bg="#334155",
        )
        self.category_label.pack(side=tk.LEFT, padx=15)

        # 오른쪽 상단 폰트 크기 확대/축소/초기화 컨트롤 버튼
        font_ctrl_frame = tk.Frame(self.select_frame, bg="#334155")
        font_ctrl_frame.pack(side=tk.RIGHT, padx=15)

        btn_font_dec = tk.Button(
            font_ctrl_frame,
            text=" - 폰트 축소 ",
            font=self.get_font(9, True),
            bg="#475569",
            fg="white",
            relief="flat",
            command=self.decrease_font,
            cursor="hand2",
        )
        btn_font_dec.pack(side=tk.LEFT, padx=2)

        self.lbl_font_disp = tk.Label(
            font_ctrl_frame,
            text=f"폰트: {10+self.font_delta}pt",
            font=self.get_font(9, True),
            fg="#FDE047",
            bg="#334155",
            width=10,
        )
        self.lbl_font_disp.pack(side=tk.LEFT, padx=3)

        btn_font_inc = tk.Button(
            font_ctrl_frame,
            text=" + 폰트 확대 ",
            font=self.get_font(9, True),
            bg="#475569",
            fg="white",
            relief="flat",
            command=self.increase_font,
            cursor="hand2",
        )
        btn_font_inc.pack(side=tk.LEFT, padx=2)

        btn_font_rst = tk.Button(
            font_ctrl_frame,
            text=" 초기화 ",
            font=self.get_font(9),
            bg="#64748B",
            fg="white",
            relief="flat",
            command=self.reset_font,
            cursor="hand2",
        )
        btn_font_rst.pack(side=tk.LEFT, padx=4)

        # 하단 서명 바
        footer_frame = tk.Frame(self.root, bg="#0F172A", height=20)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        signature_label = tk.Label(
            footer_frame,
            text="저작권 권한 서명: Lee Jae-Hee, 2026.09.03.",
            font=("Consolas", max(7, 8 + self.font_delta), "bold"),
            fg="#94A3B8",
            bg="#0F172A",
            anchor="e",
        )
        signature_label.pack(side=tk.RIGHT, padx=10, pady=2)

        # 메인 컨테이너 (3분할)
        self.main_frame = tk.Frame(self.root, bg="#F1F5F9")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 2))

        # 왼쪽 프레임: 입력 변수
        self.left_frame = tk.LabelFrame(
            self.main_frame,
            text=" 1. 기술 및 경제성 입력 변수 ",
            font=self.get_font(10, True),
            bg="white",
            fg="#0F172A",
            padx=10,
            pady=8,
        )
        self.left_frame.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4
        )

        # 중앙 프레임: 공정도
        self.mid_frame = tk.LabelFrame(
            self.main_frame,
            text=" 2. 시스템 공정도 (Process Flow) ",
            font=self.get_font(10, True),
            bg="white",
            fg="#0F172A",
            padx=10,
            pady=8,
        )
        self.mid_frame.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4
        )

        self.flow_canvas = tk.Canvas(
            self.mid_frame, bg="#F8FAFC", highlightthickness=0
        )
        self.flow_canvas.pack(fill=tk.BOTH, expand=True)

        # 오른쪽 프레임: 결과 계산서
        self.right_frame = tk.LabelFrame(
            self.main_frame,
            text=" 3. 종합 평가서 (상세 수식·환경성·경제성 LCOE/ROI 및 참고문헌) ",
            font=self.get_font(10, True),
            bg="white",
            fg="#0F172A",
            padx=10,
            pady=8,
        )
        self.right_frame.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4
        )

        self.out_text = scrolledtext.ScrolledText(
            self.right_frame,
            font=("Consolas", max(7, 9 + self.font_delta)),
            bg="white",
            fg="black",
            insertbackground="black",
        )
        self.out_text.pack(fill=tk.BOTH, expand=True)

        self.on_energy_change(None)

    def increase_font(self):
        if self.font_delta < 8:
            self.font_delta += 1
            self.update_all_fonts()

    def decrease_font(self):
        if self.font_delta > -4:
            self.font_delta -= 1
            self.update_all_fonts()

    def reset_font(self):
        self.font_delta = 0
        self.update_all_fonts()

    def update_all_fonts(self):
        """UI 내 모든 컨트롤 및 텍스트 폰트 재적용"""
        self.lbl_font_disp.config(
            text=f"폰트: {10+self.font_delta}pt", font=self.get_font(9, True)
        )
        self.title_label.config(font=self.get_font(13, True))
        self.lbl_select.config(font=self.get_font(10, True))
        self.combo.config(font=self.get_font(10))
        self.category_label.config(font=self.get_font(10, True))

        self.left_frame.config(font=self.get_font(10, True))
        self.mid_frame.config(font=self.get_font(10, True))
        self.right_frame.config(font=self.get_font(10, True))

        self.out_text.config(font=("Consolas", max(7, 9 + self.font_delta)))

        # 입력값 보존하면서 UI 재생성
        saved_values = {}
        for k, v in self.input_entries.items():
            saved_values[k] = v.get()

        self.on_energy_change(None)

        # 저장된 입력값 복원
        for k, v in saved_values.items():
            if k in self.input_entries:
                self.input_entries[k].delete(0, tk.END)
                self.input_entries[k].insert(0, str(v))

        self.run_calculation()

    def on_energy_change(self, event):
        selected = self.energy_var.get()
        data = self.energy_db[selected]

        self.category_label.config(
            text=f"[법적 분류: {data['category']}]",
            fg="#E2E8F0" if data["category"] == "신에너지" else "#38BDF8",
        )

        for child in self.left_frame.winfo_children():
            child.destroy()

        self.input_entries = {}

        if selected == "11. 연료전지 (Fuel Cell)":
            type_frame = tk.Frame(self.left_frame, bg="#EFF6FF", pady=4, padx=4)
            type_frame.pack(fill=tk.X, pady=(0, 6))

            tk.Label(
                type_frame,
                text="연료전지 타입 선택:",
                font=self.get_font(9, True),
                bg="#EFF6FF",
                fg="#1E40AF",
            ).pack(side=tk.LEFT)

            self.fc_type_var = tk.StringVar(value=list(self.fc_types.keys())[0])
            self.fc_type_combo = ttk.Combobox(
                type_frame,
                textvariable=self.fc_type_var,
                state="readonly",
                font=self.get_font(9),
                width=20,
            )
            self.fc_type_combo["values"] = list(self.fc_types.keys())
            self.fc_type_combo.pack(side=tk.RIGHT, padx=5)
            self.fc_type_combo.bind("<<ComboboxSelected>>", self.on_fc_type_change)

        for label, default_val, unit in data["inputs"]:
            row_frame = tk.Frame(self.left_frame, bg="white", pady=2)
            row_frame.pack(fill=tk.X)

            if "초기 투자비" in label:
                sep_frame = tk.Frame(self.left_frame, bg="#E2E8F0", height=1)
                sep_frame.pack(fill=tk.X, pady=4)

            lbl = tk.Label(
                row_frame,
                text=label,
                font=self.get_font(9),
                bg="white",
                width=23,
                anchor="w",
            )
            lbl.pack(side=tk.LEFT)

            ent = tk.Entry(
                row_frame,
                font=self.get_font(9),
                width=9,
                justify="right",
                relief="solid",
                bd=1,
            )
            ent.insert(0, str(default_val))
            ent.pack(side=tk.LEFT, padx=3)

            unit_lbl = tk.Label(
                row_frame,
                text=unit,
                font=self.get_font(9),
                bg="white",
                fg="#64748B",
            )
            unit_lbl.pack(side=tk.LEFT)

            self.input_entries[label] = ent

        btn_calc = tk.Button(
            self.left_frame,
            text="통합 평가 및 경제성 계산 실행 ▶",
            font=self.get_font(10, True),
            bg="#2563EB",
            fg="white",
            activebackground="#1D4ED8",
            activeforeground="white",
            command=self.run_calculation,
            pady=6,
            relief="flat",
            cursor="hand2",
        )
        btn_calc.pack(fill=tk.X, side=tk.BOTTOM, pady=8)

        self.draw_flowchart(data["flow"])
        self.run_calculation()

    def on_fc_type_change(self, event):
        fc_type_name = self.fc_type_var.get()
        fc_info = self.fc_types[fc_type_name]

        if "발전 효율 (η_el)" in self.input_entries:
            self.input_entries["발전 효율 (η_el)"].delete(0, tk.END)
            self.input_entries["발전 효율 (η_el)"].insert(
                0, str(fc_info["eta_el"])
            )

        if "열회수 효율 (η_th)" in self.input_entries:
            self.input_entries["열회수 효율 (η_th)"].delete(0, tk.END)
            self.input_entries["열회수 효율 (η_th)"].insert(
                0, str(fc_info["eta_th"])
            )

        self.draw_flowchart(fc_info["flow"])
        self.run_calculation()

    def draw_flowchart(self, steps):
        self.flow_canvas.delete("all")
        self.root.update_idletasks()

        w = self.flow_canvas.winfo_width()
        if w <= 1:
            w = 320

        box_w = max(160, int(190 + self.font_delta * 8))
        box_h = max(35, int(40 + self.font_delta * 3))
        start_y = 15
        spacing = 18

        for i, step in enumerate(steps):
            x1 = (w - box_w) / 2
            y1 = start_y + i * (box_h + spacing)
            x2 = x1 + box_w
            y2 = y1 + box_h

            self.flow_canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill="#E0F2FE",
                outline="#0284C7",
                width=2,
                tags="box",
            )
            self.flow_canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=f"{i+1}. {step}",
                font=self.get_font(9, True),
                fill="#0369A1",
            )

            if i < len(steps) - 1:
                arrow_y1 = y2
                arrow_y2 = y2 + spacing
                self.flow_canvas.create_line(
                    w / 2,
                    arrow_y1,
                    w / 2,
                    arrow_y2,
                    arrow=tk.LAST,
                    fill="#64748B",
                    width=2,
                )

    def calculate_economics_report(self, p, annual_kwh):
        capex_man = p.get("초기 투자비 (CAPEX)", 10000)
        opex_man = p.get("연간 유지관리비 (OPEX)", 100)
        price_per_kwh = (
            p.get("전력 판매단가 (SMP+REC)", 0)
            or p.get("전력/열 판매 단가", 0)
            or p.get("전력 판매단가", 0)
            or p.get("열 생산 가치 단가", 0)
            or p.get("열에너지 절감 단가", 0)
            or p.get("복합 판매 단가 (전력+열)", 0)
            or p.get("열 절감 가치 단가", 0)
            or p.get("에너지 판매 단가", 0)
            or p.get("수소 판매/가치 단가", 0)
            or p.get("전력+열 판매 단가", 0)
            or 150.0
        )
        lifespan = int(p.get("내용연수 (Lifespan)", 20))
        r = p.get("할인율 (r)", 4.5) / 100.0

        capex = capex_man * 10000.0
        opex = opex_man * 10000.0

        annual_revenue = annual_kwh * price_per_kwh
        annual_net_cf = annual_revenue - opex

        if annual_net_cf > 0:
            payback_years = capex / annual_net_cf
            pb_yrs = int(payback_years)
            pb_months = int(round((payback_years - pb_yrs) * 12))
            payback_str = f"{payback_years:.2f} 년 (약 {pb_yrs}년 {pb_months}개월)"
        else:
            payback_str = "회수 불가능 (연간 순수익이 음수이거나 0원임)"

        roi = (annual_net_cf / capex) * 100.0 if capex > 0 else 0.0

        pv_opex_sum = sum(opex / ((1 + r) ** t) for t in range(1, lifespan + 1))
        pv_costs_total = capex + pv_opex_sum
        pv_energy_sum = sum(
            annual_kwh / ((1 + r) ** t) for t in range(1, lifespan + 1)
        )

        lcoe = pv_costs_total / pv_energy_sum if pv_energy_sum > 0 else 0.0

        return f"""
==================================================
[ 경제성 분석 상세 계산 (LCOE, ROI, 손익분기점) ]
==================================================
1. 주요 입력 파라미터 요약:
   • 초기 투자비 (CAPEX): {capex_man:,.0f} 만원 ({capex:,.0f} 원)
   • 연간 유지관리비 (OPEX): {opex_man:,.0f} 만원/년 ({opex:,.0f} 원/년)
   • 에너지가치/판매단가: {price_per_kwh:,.1f} 원/kWh
   • 설비 내용연수(N): {lifespan} 년 | 기준 할인율(r): {r*100:.1f} %

2. 연간 예상 수익 및 현금흐름 산출:
   • 연간 총수익 = 연간생산량({annual_kwh:,.1f} kWh) × 단가({price_per_kwh}원)
                = {annual_revenue/10000.0:,.2f} 만원/년
   • 연간 순수익 (Annual Net CF) = 총수익 - OPEX
                = {annual_revenue/10000.0:,.2f} - {opex_man:,.2f} = {annual_net_cf/10000.0:,.2f} 만원/년

3. 투자 수익률 (ROI) 및 손익분기점 (Payback Period):
   • 연간 ROI = (연간 순수익 / CAPEX) × 100
             = ({annual_net_cf:,.0f} / {capex:,.0f}) × 100 = {roi:.2f} %
   • 단순 투자 회수 기간 = CAPEX / 연간 순수익
                     = {capex:,.0f} / {annual_net_cf:,.0f} = {payback_str}

4. 균등화 발전 단가 (LCOE) 상세 할인 수식:
   • LCOE = [ CAPEX + ∑(OPEX_t / (1+r)^t) ] / [ ∑(Energy_t / (1+r)^t) ]
   • 총 비용 할인 현재 가치 합계 (PV_Costs): {pv_costs_total/10000.0:,.2f} 만원
     - CAPEX 현가: {capex/10000.0:,.2f} 만원
     - OPEX {lifespan}년간 현가 합계: {pv_opex_sum/10000.0:,.2f} 만원
   • 총 발전량 할인 현재 가치 합계 (PV_Energy): {pv_energy_sum:,.1f} kWh
   • 최종 산출 LCOE = {pv_costs_total:,.0f} 원 / {pv_energy_sum:,.1f} kWh
                   = {lcoe:,.2f} 원/kWh

==================================================
[ 전체 관련 참고문헌 및 학술·법적 기준 (References) ]
==================================================
1. 산업통상자원부 (2024), 「신·재생에너지 설비의 지원 등에 관한 지침」, 산업통상자원부 고시.
2. 한국에너지공단 신재생에너지센터 (2023), 「신·재생에너지 원별 기술 표준 및 보급통계 데이터북」.
3. IPCC (2019), 「2019 Refinement to the 2006 IPCC Guidelines for National Greenhouse Gas Inventories」.
4. 환경부 (2022), 「온실가스 배출권거래제의 배출량 보고 및 인증에 관한 지침」 (국가 전력 배출계수 0.4595 kgCO2eq/kWh 적용).
5. National Renewable Energy Laboratory (NREL, 2023), 「Transparent Cost Database and LCOE Calculation Methodology」.
6. International Energy Agency (IEA, 2020), 「Projected Costs of Generating Electricity 2020 Edition」.
7. 한국전력공사 (KEPCO), 「월별 전력통계월보 - SMP (계통한계가격) 및 REC 거래가격 동향」.
8. 한국신재생에너지학회, 「신재생에너지 시스템 설계 및 경제성 평가에 관한 표준 학술 가이드라인」.
"""

    def run_calculation(self):
        selected = self.energy_var.get()
        data = self.energy_db[selected]

        try:
            inputs = {}
            for label, _, _ in data["inputs"]:
                val = float(self.input_entries[label].get())
                inputs[label] = val

            result_text = data["calc_fn"](inputs)

            self.out_text.delete(1.0, tk.END)
            self.out_text.insert(tk.END, result_text)

        except ValueError:
            messagebox.showerror(
                "입력 오류", "모든 입력값은 올바른 숫자 형태여야 합니다."
            )

    def calc_solar_pv(self, p):
        A = p["설치 면적 (A)"]
        G = p["수평면 일사량 (G)"]
        eta = p["모듈 변환 효율 (η)"] / 100.0
        T = p["모듈 동작 온도 (T)"]
        gamma = p["온도 계수 (γ)"] / 100.0
        PR = p["시스템 종합 효율 (PR)"] / 100.0

        temp_loss = 1 - gamma * (T - 25)
        P_stc = A * (G / 1000) * eta
        P_act = P_stc * temp_loss * PR
        E_daily = P_act * 3.6
        E_annual_kwh = E_daily * 365
        num_modules = math.ceil((P_stc * 1000) / 500)

        ghg_avoided = (E_annual_kwh * 0.4595) / 1000.0
        econ_report = self.calculate_economics_report(p, E_annual_kwh)

        return (
            f"""[ 태양광 발전 시스템 상세 공학 계산 과정 ]

1. 표준시험조건(STC: 25°C, 1000W/m²) 피크 출력 산출:
   • P_stc = 면적(A) × (일사량 G / 1000) × 모듈효율(η)
          = {A} m² × ({G} / 1000 W/m²) × {eta*100}% = {P_stc:.2f} kWp

2. 온도 상승 및 시스템 손실율(PR) 적용 실효 AC 출력:
   • 온도 손실 계수 = 1 - γ × (T - 25°C) = 1 - {gamma*100:.2f}% × ({T}-25) = {temp_loss:.4f}
   • 실효 출력(P_act) = P_stc × 온도손실계수 × PR
                    = {P_stc:.2f} kWp × {temp_loss:.4f} × {PR} = {P_act:.2f} kW

3. 기간별 발전량 산출 (일 평균 발전시간 3.6시간 적용 기준):
   • 일일 발전량 = P_act × 3.6 hours/day = {P_act:.2f} × 3.6 = {E_daily:.2f} kWh/day
   • 연간 발전량 = 일일 발전량 × 365 일 = {E_annual_kwh:,.1f} kWh/year ({E_annual_kwh/1000:.2f} MWh/year)

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 태양광 모듈: 500 Wp 고효율 단결정 모듈 약 {num_modules} 장 (어레이 점유 면적 {A:.1f} m²)
• 인버터 규격: {P_stc * 1.1:.1f} kW 급 3상 계통연계형 스트링 인버터 (MPPT 내장)

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 직접 배출량: 0.00 tCO2eq/year (발전 중 화석연료 연소 없음)
• 국가 전력계통 대체 감축량 (배출계수 0.4595 kgCO2eq/kWh 적용):
  - 감축량 = {E_annual_kwh:,.1f} kWh × 0.4595 kg/kWh / 1000 = {ghg_avoided:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx 0.00 kg/yr | SOx 0.00 kg/yr | PM 0.00 kg/yr
"""
            + econ_report
        )

    def calc_solar_thermal(self, p):
        A = p["집열기 면적 (A)"]
        G = p["일사량 (G)"]
        eta0 = p["집열기 기준 효율 (η0)"] / 100.0
        a1 = p["1차 손실 계수 (a1)"]
        Tm = p["평균 집열 온도 (Tm)"]
        Ta = p["외기 온도 (Ta)"]

        dT = Tm - Ta
        eta = max(0, eta0 - (a1 * dT / G)) if G > 0 else 0
        Q_collect = A * G * eta / 1000.0
        E_annual_kwh = Q_collect * 3.6 * 365
        tank_vol = A * 60

        ghg_avoided = (E_annual_kwh / 1000.0) * 0.202
        econ_report = self.calculate_economics_report(p, E_annual_kwh)

        return (
            f"""[ 태양열 집열 시스템 상세 공학 계산 과정 ]

1. 집열기 열손실 수식 및 집열 효율 산출:
   • 온대차(ΔT) = 평균집열온도(Tm) - 외기온도(Ta) = {Tm} - {Ta} = {dT:.1f} °C
   • 순간 집열효율(η) = η0 - [ a1 × (ΔT / G) ]
                     = {eta0*100}% - [ {a1} × ({dT:.1f} / {G}) ] = {eta*100:.2f} %

2. 유효 취득 열량 및 연간 생성 열량 산출:
   • 취득 열량(Q_collect) = 면적(A) × 일사량(G) × 집열효율(η) / 1000
                         = {A} m² × {G} W/m² × {eta:.4f} / 1000 = {Q_collect:.2f} kW_th
   • 연간 생산 열량 = Q_collect × 3.6 h/day × 365일 = {E_annual_kwh:,.1f} kWh_th/year ({E_annual_kwh/1000:.2f} MWh_th/year)

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 집열기: 고효율 평판형/진공관형 집열기 {A:.1f} m²
• 축열 용량: {tank_vol:.0f} Liters 이중 직수로 보온 축열탱크 (SUS304 재질)

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 직접 배출량: 0.00 tCO2eq/year
• LNG 보일러 대체 감축량 (도시가스 열원 배출계수 0.202 tCO2eq/MWh 적용):
  - 감축량 = {E_annual_kwh/1000:.2f} MWh × 0.202 tCO2/MWh = {ghg_avoided:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx 0.00 kg/yr | SOx 0.00 kg/yr | PM 0.00 kg/yr
"""
            + econ_report
        )

    def calc_wind(self, p):
        rho = p["공기 밀도 (ρ)"]
        R = p["로터 블레이드 반경 (R)"]
        v = p["풍속 (v)"]
        Cp = p["파워 계수 (Cp)"]
        eta = p["기계/발전기 효율 (η)"] / 100.0

        A = math.pi * (R**2)
        P_wind = 0.5 * rho * A * (v**3) / 1000.0
        P_elec = P_wind * Cp * eta
        E_annual_kwh = P_elec * 8760 * 0.25

        ghg_avoided = (E_annual_kwh * 0.4595) / 1000.0
        econ_report = self.calculate_economics_report(p, E_annual_kwh)

        return (
            f"""[ 풍력 발전 터빈 상세 공학 계산 과정 ]

1. 로터 수풍 면적 및 바람 운동에너지 역학 산출:
   • 수풍 면적(A) = π × R² = 3.14159 × ({R} m)² = {A:.2f} m²
   • 공기 유체 운동에너지(P_wind) = 0.5 × ρ × A × v³ / 1000
                                = 0.5 × {rho} kg/m³ × {A:.2f} m² × ({v} m/s)³ / 1000 = {P_wind:.2f} kW

2. 벳츠 한계(Betz limit) 적용 파워계수(Cp) 및 전기적 변환 출력:
   • 전기 출력(P_elec) = P_wind × Cp × 기계발전효율(η)
                     = {P_wind:.2f} kW × {Cp} × {eta} = {P_elec:.2f} kW

3. 설비 이용률(Capacity Factor 25%) 적용 연간 발전량:
   • 연간 발전량 = P_elec × 8,760 시간/년 × 0.25
                = {E_annual_kwh:,.1f} kWh/year ({E_annual_kwh/1000:.2f} MWh/year)

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 로터 규격: 직경 {2*R:.1f} m (블레이드 3엽), 지지 타워 높이 {2*R * 1.2:.1f} m
• 발전기 규격: {P_elec:.1f} kW 급 영구자석형 동기발전기 (PMSG / DFIG)

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 직접 배출량: 0.00 tCO2eq/year
• 화석연료 대체 감축량: {ghg_avoided:.2f} tCO2eq/year (배출계수 0.4595 적용)
• 대기 오염물질 배출량: NOx 0.00 kg/yr | SOx 0.00 kg/yr | PM 0.00 kg/yr
"""
            + econ_report
        )

    def calc_hydro(self, p):
        Q = p["유량 (Q)"]
        H = p["유효 낙차 (H)"]
        eta_t = p["수차 효율 (η_t)"] / 100.0
        eta_g = p["발전기 효율 (η_g)"] / 100.0

        P_hydro = 9.81 * Q * H * eta_t * eta_g
        E_annual_kwh = P_hydro * 8760 * 0.6

        ghg_avoided = (E_annual_kwh * 0.4595) / 1000.0
        econ_report = self.calculate_economics_report(p, E_annual_kwh)

        return (
            f"""[ 수력 발전 설비 상세 공학 계산 과정 ]

1. 수두 위치에너지 기반 수력 출력 산출 수식:
   • 이론 수력 P_th = ρ × g × Q × H = 1000kg/m³ × 9.81m/s² × {Q}m³/s × {H}m = {9.81*Q*H:.2f} kW
   • 종합 수력 출력(P_hydro) = 9.81 × Q × H × 수차효율(η_t) × 발전기효율(η_g)
                           = 9.81 × {Q} × {H} × {eta_t} × {eta_g} = {P_hydro:.2f} kW

2. 설비 이용률(Capacity Factor 60%) 적용 연간 발전량:
   • 연간 발전량 = P_hydro × 8,760 시간/년 × 0.60
                = {E_annual_kwh:,.1f} kWh/year ({E_annual_kwh/1000:.2f} MWh/year)

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 수차 설비: 프란시스(Francis) 또는 카플란(Kaplan) 수차 (유량 {Q} m³/s, 낙차 {H} m)
• 발전기 규격: {P_hydro:.1f} kW 급 동기발전기 (3상 6.6kV/380V)

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 직접 배출량: 0.00 tCO2eq/year
• 계통 전력 대체 감축량: {ghg_avoided:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx 0.00 kg/yr | SOx 0.00 kg/yr | PM 0.00 kg/yr
"""
            + econ_report
        )

    def calc_geothermal(self, p):
        P_in = p["히트펌프 전력 (P_in)"]
        COP = p["난방 성적계수 (COP)"]
        q_unit = p["지중 열교환기 길이당 열량"]
        hours = p["운전 시간"]

        Q_heat = P_in * COP
        Q_ground = Q_heat - P_in
        L_pipe = (Q_ground * 1000.0) / q_unit

        E_elec_annual = P_in * hours * 365
        E_heat_annual_kwh = Q_heat * hours * 365

        ghg_indirect = (E_elec_annual * 0.4595) / 1000.0
        ghg_displaced = (E_heat_annual_kwh / 1000.0) * 0.202
        ghg_net_reduction = ghg_displaced - ghg_indirect

        econ_report = self.calculate_economics_report(p, E_heat_annual_kwh)

        return (
            f"""[ 지열 히트펌프 시스템 상세 공학 계산 과정 ]

1. 히트펌프 사이클 및 지중 채열량 열역학 산출:
   • 총 난방 열출력(Q_heat) = 입력 전력(P_in) × COP = {P_in} kW × {COP} = {Q_heat:.2f} kW_th
   • 지중 흡수 열량(Q_ground) = Q_heat - P_in = {Q_heat:.2f} - {P_in} = {Q_ground:.2f} kW
   • 필요 지중 열교환 파이프 길이 = (Q_ground × 1000 W/kW) / {q_unit} W/m
                                 = {L_pipe:.2f} m

2. 연간 구동 전력량 및 열 생산량 산출 (일 {hours}시간 운전 기준):
   • 연간 소비 전력량 = {P_in} kW × {hours} 시간/일 × 365일 = {E_elec_annual:,.1f} kWh_e/year
   • 연간 공급 열에너지량 = {Q_heat:.2f} kW × {hours} 시간/일 × 365일 = {E_heat_annual_kwh:,.1f} kWh_th/year

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 지열 히트펌프: 구동 전력 {P_in:.1f} kW_e, 난방 용량 {Q_heat:.1f} kW_th (수-수 타입)
• 지중 열교환기: HDPE U-Tube 총 {L_pipe:.1f} m (150m 천공 기준 약 {math.ceil(L_pipe/150)} 공 필요)

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 구동 전력 간접 배출량: {ghg_indirect:.2f} tCO2eq/year
• 보일러 대체 순 감축량: {ghg_net_reduction:.2f} tCO2eq/year (대체 감축 {ghg_displaced:.2f} - 간접 {ghg_indirect:.2f})
• 대기 오염물질 배출량: NOx 0.00 kg/yr | SOx 0.00 kg/yr | PM 0.00 kg/yr
"""
            + econ_report
        )

    def calc_marine(self, p):
        rho = p["해수 밀도 (ρ)"]
        A = p["조지 면적 (A)"]
        H = p["조차 (H)"]
        eta = p["발전 효율 (η)"] / 100.0

        E_single = 0.5 * rho * 9.81 * A * (H**2) / 3600000.0
        E_daily = E_single * 4 * eta
        E_annual_kwh = E_daily * 365

        ghg_avoided = (E_annual_kwh * 0.4595) / 1000.0
        econ_report = self.calculate_economics_report(p, E_annual_kwh)

        return (
            f"""[ 조력/해양 발전 시스템 상세 공학 계산 과정 ]

1. 조석 수위차 기반 1회 및 일일 에너지 포텐셜 산출:
   • 1회 낙차 포텐셜 = 0.5 × ρ × g × A × H² / 3.6×10⁶
                   = 0.5 × {rho}kg/m³ × 9.81m/s² × {A}m² × ({H}m)² / 3.6×10⁶ = {E_single:.2f} kWh
   • 일일 발전량 (하루 4회 창·밀물 적용 및 효율 반영):
     - E_daily = 1회 포텐셜 × 4 회/일 × 발전효율(η)
               = {E_single:.2f} × 4 × {eta} = {E_daily:.2f} kWh/day

2. 연간 예상 발전량 산출:
   • 연간 발전량 = E_daily × 365 일 = {E_annual_kwh:,.1f} kWh/year ({E_annual_kwh/1000:.2f} MWh/year)

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 해양 수차: 벌브형(Bulb Type) 해수 수차 발전기 (평균 발전 출력 {E_daily/24:.1f} kW)
• 조지 구조물: 차수 제방 및 자동 유압 방조 수문 시스템 ({A:,.0f} m²)

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 직접 배출량: 0.00 tCO2eq/year
• 계통 전력 대체 감축량: {ghg_avoided:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx 0.00 kg/yr | SOx 0.00 kg/yr | PM 0.00 kg/yr
"""
            + econ_report
        )

    def calc_bio(self, p):
        Q = p["바이오가스 유량 (Q)"]
        ch4 = p["메탄 함량 (CH4)"] / 100.0
        lhv = p["메탄 저위발열량 (LHV)"]
        eta_e = p["발전 효율 (η_e)"] / 100.0
        eta_th = p["열회수 효율 (η_th)"] / 100.0

        Q_in_kW = (Q * ch4 * lhv) / 3.6
        P_elec = Q_in_kW * eta_e
        Q_heat = Q_in_kW * eta_th

        E_elec_annual_kwh = P_elec * 8000
        E_heat_annual_kwh = Q_heat * 8000
        Total_equivalent_kwh = E_elec_annual_kwh + E_heat_annual_kwh

        ghg_avoided = (
            E_elec_annual_kwh * 0.4595 / 1000.0
        ) + (E_heat_annual_kwh / 1000.0) * 0.202
        nox_emission = E_elec_annual_kwh * 0.15 / 1000.0

        econ_report = self.calculate_economics_report(p, Total_equivalent_kwh)

        return (
            f"""[ 바이오가스 CHP 열병합발전 상세 공학 계산 과정 ]

1. 바이오가스 입열량 계산:
   • 입열량(Q_in) = 유량(Q) × CH4함량 × LHV / 3.6
                  = {Q} m³/h × {ch4} × {lhv} MJ/m³ / 3.6 = {Q_in_kW:.2f} kW_th

2. 열병합 발전 전력 및 열회수 출력 계산:
   • 전기 출력(P_elec) = Q_in × 발전효율(η_e) = {Q_in_kW:.2f} × {eta_e} = {P_elec:.2f} kW_e
   • 열회수 출력(Q_heat) = Q_in × 열효율(η_th) = {Q_in_kW:.2f} × {eta_th} = {Q_heat:.2f} kW_th

3. 연간 가동 8,000시간 적용 에너지역량:
   • 연간 전력 생산량 = {E_elec_annual_kwh:,.1f} kWh_e/year
   • 연간 열 생산량 = {E_heat_annual_kwh:,.1f} kWh_th/year

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 가스 엔진 발전기: {P_elec:.1f} kW_e 급 바이오가스 전용 CHP 엔진
• 전처리 설비: Desulfurization 습식/건식 탈황탑 및 실록산 제거 세척 장치

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 직접 배출량: 0.00 tCO2eq/year (생물성 탄소 중립 적용)
• 전력 및 열 대체 감축량: {ghg_avoided:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx {nox_emission:.2f} kg/yr (연소 부산물)
"""
            + econ_report
        )

    def calc_hydro_thermal(self, p):
        Q_m3 = p["유수 유량 (Q)"]
        dT = p["유수 입출구 온도차 (ΔT)"]
        Cp = p["물 비열 (Cp)"]
        COP = p["히트펌프 COP"]

        m_dot = (Q_m3 * 1000.0) / 3600.0
        Q_source = m_dot * Cp * dT
        P_in = Q_source / (COP - 1.0)
        Q_supply = P_in * COP

        E_elec_annual = P_in * 4000
        E_heat_annual_kwh = Q_supply * 4000

        ghg_indirect = (E_elec_annual * 0.4595) / 1000.0
        ghg_displaced = (E_heat_annual_kwh / 1000.0) * 0.202
        ghg_net_reduction = ghg_displaced - ghg_indirect

        econ_report = self.calculate_economics_report(p, E_heat_annual_kwh)

        return (
            f"""[ 수열 (하천수/해수) 에너지 히트펌프 상세 공학 계산 과정 ]

1. 수열 흡수량 및 히트펌프 일률 계산:
   • 유수 질량 유량(m_dot) = {Q_m3} m³/h × 1000 kg/m³ / 3600 s = {m_dot:.2f} kg/s
   • 열원 흡수량(Q_source) = m_dot × Cp × ΔT = {m_dot:.2f} × {Cp} kJ/kg°C × {dT}°C = {Q_source:.2f} kW_th
   • 소요 구동 전력(P_in) = Q_source / (COP - 1) = {Q_source:.2f} / ({COP} - 1) = {P_in:.2f} kW_e
   • 최종 공급 열량(Q_supply) = P_in × COP = {P_in:.2f} × {COP} = {Q_supply:.2f} kW_th

2. 연간 가동시간 4,000시간 적용 에너지역량:
   • 연간 구동 전력량 = {E_elec_annual:,.1f} kWh_e/year
   • 연간 공급 열량 = {E_heat_annual_kwh:,.1f} kWh_th/year

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 수열 히트펌프: 압축기 {P_in:.1f} kW_e, 공급 열량 {Q_supply:.1f} kW_th
• 열교환기 및 취수 설비: 티타늄(Titanium) 판형 열교환기 및 취수 펌프 ({Q_m3} m³/h)

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 구동 전력 간접 배출량: {ghg_indirect:.2f} tCO2eq/year
• 보일러 대체 순 감축량: {ghg_net_reduction:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx 0.00 kg/yr | SOx 0.00 kg/yr | PM 0.00 kg/yr
"""
            + econ_report
        )

    def calc_waste(self, p):
        m_ton_h = p["소각 폐기물량 (m)"]
        lhv = p["폐기물 발열량 (LHV)"]
        eta_b = p["보일러 열효율 (η_b)"] / 100.0
        eta_t = p["스팀터빈 발전효율 (η_t)"] / 100.0

        m_kg_h = m_ton_h * 1000.0
        Q_in_kW = (m_kg_h * lhv) / 3600.0
        Q_steam = Q_in_kW * eta_b
        P_elec = Q_steam * eta_t

        annual_waste_ton = m_ton_h * 8000
        E_elec_annual_kwh = P_elec * 8000
        E_steam_annual_kwh = Q_steam * 8000
        Total_kwh = E_elec_annual_kwh + E_steam_annual_kwh

        ghg_direct = annual_waste_ton * 0.40
        ghg_avoided = (
            E_elec_annual_kwh * 0.4595 / 1000.0
        ) + (E_steam_annual_kwh / 1000.0) * 0.202
        ghg_net = ghg_avoided - ghg_direct

        econ_report = self.calculate_economics_report(p, Total_kwh)

        return (
            f"""[ 폐기물 소각 열회수 발전 상세 공학 계산 과정 ]

1. 폐기물 소각 연소 입열 및 증기/전력 출력:
   • 연소 입열량(Q_in) = (처리량 kg/h × LHV kJ/kg) / 3600
                       = ({m_kg_h} × {lhv}) / 3600 = {Q_in_kW:.2f} kW_th
   • 보일러 증기회수량(Q_steam) = Q_in × 보일러효율 = {Q_in_kW:.2f} × {eta_b} = {Q_steam:.2f} kW_th
   • 스팀터빈 발전출력(P_elec) = Q_steam × 터빈효율 = {Q_steam:.2f} × {eta_t} = {P_elec:.2f} kW_e

2. 연간 8,000시간 운전 생산량 산출:
   • 연간 소각 폐기물량 = {annual_waste_ton:,.0f} ton/year
   • 연간 발전량 = {E_elec_annual_kwh:,.1f} kWh_e/year
   • 연간 증기공급량 = {E_steam_annual_kwh:,.1f} kWh_th/year

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 소각로: 스토커 또는 유동층 소각로 (처리 능력 {m_ton_h:.1f} ton/h)
• 폐열보일러 & 터빈: 40 bar 400°C 고압 보일러 및 {P_elec:.1f} kW_e 증기 터빈

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 소각 직접 배출량 (0.40 tCO2/ton waste): {ghg_direct:.2f} tCO2eq/year
• 대체 감축량: {ghg_avoided:.2f} tCO2eq/year (순 감축량: {ghg_net:.2f} tCO2eq/year)
• 대기 오염물질 배출량: NOx {annual_waste_ton*0.30:.1f} kg/yr | SOx {annual_waste_ton*0.05:.1f} kg/yr
"""
            + econ_report
        )

    def calc_hydrogen(self, p):
        P_el = p["수전해 공급 전력 (P_el)"]
        eta_sys = p["수전해 시스템 효율 (η_sys)"] / 100.0
        lhv = p["수소 저위발열량 (LHV)"]

        m_h2_h = (P_el * eta_sys) / lhv
        annual_power = P_el * 8000
        annual_h2_kg = m_h2_h * 8000
        E_h2_equivalent_kwh = annual_h2_kg * lhv

        ghg_indirect = (annual_power * 0.4595) / 1000.0
        ghg_avoided = (annual_h2_kg * 10.0) / 1000.0

        econ_report = self.calculate_economics_report(p, E_h2_equivalent_kwh)

        return (
            f"""[ 수전해 수소 생산 시스템 상세 공학 계산 과정 ]

1. 전열 화학 반응 수소 생산속도 계산:
   • 유효 전기화학 반응 전력 = P_el × 시스템효율 = {P_el} kW × {eta_sys} = {P_el * eta_sys:.2f} kW
   • 수소 생산 속도(m_H2) = 유효전력 / 수소 LHV
                         = {P_el * eta_sys:.2f} / {lhv} kWh/kg = {m_h2_h:.3f} kg-H2/h

2. 연간 8,000시간 가동 수소 생산량 산출:
   • 연간 수소 생산량 = {m_h2_h:.3f} kg/h × 8000 h = {annual_h2_kg:,.1f} kg-H2/year ({annual_h2_kg/1000:.2f} ton/year)
   • 연간 수소 에너지 등가량 = {E_h2_equivalent_kwh:,.1f} kWh/year

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 수전해 스택: PEM 또는 알칼라인 수전해 모듈 (입력 전력 {P_el:.1f} kW_e)
• 압축/저장 설비: 350 bar / 700 bar 고압 수소 압축기 및 튜브트레일러 연계기

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 소비 전력 간접 배출량: {ghg_indirect:.2f} tCO2eq/year (그리드 전력 사용 기준)
• 화석연료 개질수소(SMR) 대체 감축량: {ghg_avoided:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx 0.00 kg/yr | SOx 0.00 kg/yr | PM 0.00 kg/yr
"""
            + econ_report
        )

    def calc_fuel_cell(self, p):
        fc_type_name = (
            self.fc_type_var.get()
            if hasattr(self, "fc_type_var")
            else "PEMFC (고분자전해질형)"
        )
        fc_info = self.fc_types.get(
            fc_type_name, self.fc_types["PEMFC (고분자전해질형)"]
        )

        m_h2 = p["수소 소모량 (m_H2)"]
        eta_el = p["발전 효율 (η_el)"] / 100.0
        eta_th = p["열회수 효율 (η_th)"] / 100.0
        lhv = p["수소 저위발열량 (LHV)"]

        P_in = m_h2 * lhv
        P_elec = P_in * eta_el
        Q_heat = P_in * eta_th

        E_elec_annual_kwh = P_elec * 8000
        E_heat_annual_kwh = Q_heat * 8000
        Total_kwh = E_elec_annual_kwh + E_heat_annual_kwh

        ghg_avoided = (
            E_elec_annual_kwh * 0.4595 / 1000.0
        ) + (E_heat_annual_kwh / 1000.0) * 0.202
        nox_emission = (E_elec_annual_kwh / 1000.0) * fc_info["nox_factor"]

        econ_report = self.calculate_economics_report(p, Total_kwh)

        return (
            f"""[ {fc_type_name} 수소 연료전지 시스템 상세 공학 계산 ]

1. 선택 타입 특성 및 열화학 입출력 계산:
   • 동작 온도: {fc_info['temp']} | {fc_info['desc']}
   • 수소 화학 입열(P_in) = 소모량(m_H2) × LHV = {m_h2} kg/h × {lhv} kWh/kg = {P_in:.2f} kW
   • 전기 출력(P_elec) = P_in × 발전효율(η_el) = {P_in:.2f} × {eta_el} = {P_elec:.2f} kW_e
   • 열회수 출력(Q_heat) = P_in × 열효율(η_th) = {P_in:.2f} × {eta_th} = {Q_heat:.2f} kW_th

2. 연간 8,000시간 운전 생산량 산출:
   • 연간 전력 생산량 = {E_elec_annual_kwh:,.1f} kWh_e/year
   • 연간 열 생산량 = {E_heat_annual_kwh:,.1f} kWh_th/year

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 연료전지 스택: {P_elec:.1f} kW_e 급 {fc_type_name.split(' ')[0]} 전극 스택
• 전력 변환 장치 (PCS): {P_elec * 1.15:.1f} kW 급 계통 연계형 인버터

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 순수 수소 직접 배출량: 0.00 tCO2eq/year
• 전력 및 온수 대체 감축량: {ghg_avoided:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx {nox_emission:.3f} kg/yr
"""
            + econ_report
        )

    def calc_igcc(self, p):
        m_ton_h = p["석탄 투입량 (m)"]
        lhv = p["석탄 발열량 (LHV)"]
        eta_g = p["가스화炉 효율 (η_g)"] / 100.0
        eta_cc = p["복합발전 효율 (η_cc)"] / 100.0

        m_kg_s = (m_ton_h * 1000.0) / 3600.0
        Q_in = m_kg_s * lhv
        Q_syngas = Q_in * eta_g
        P_elec = Q_syngas * eta_cc

        E_elec_annual_kwh = P_elec * 8000

        ghg_direct = (E_elec_annual_kwh * 0.75) / 1000.0
        ghg_avoided_vs_coal = E_elec_annual_kwh * (0.90 - 0.75) / 1000.0

        econ_report = self.calculate_economics_report(p, E_elec_annual_kwh)

        return (
            f"""[ 석탄가스화 복합발전(IGCC) 상세 공학 계산 과정 ]

1. 가스화 반응 및 가스터빈/증기터빈 복합발전 산출:
   • 석탄 투입 입열량(Q_in) = ({m_ton_h} ton/h × 1000/3600) × {lhv} kJ/kg = {Q_in:.2f} kW
   • 합성가스(Syngas) 에너지 = Q_in × 가스화효율 = {Q_in:.2f} × {eta_g} = {Q_syngas:.2f} kW
   • 복합발전 전력출력(P_elec) = Q_syngas × 복합효율 = {Q_syngas:.2f} × {eta_cc} = {P_elec:.2f} kW_e

2. 연간 8,000시간 운전 생산량 산출:
   • 연간 발전량 = {E_elec_annual_kwh:,.1f} kWh_e/year ({E_elec_annual_kwh/1000:.2f} MWh/year)

==================================================
[ 장치 및 시설 주요 사양서 (Specification Sheet) ]
==================================================
• 가스화 반응기: 분류상 가스화로 ({m_ton_h:.1f} ton/h 처리, 1400°C 30bar)
• 정제 및 발전: Acid Gas Removal(AGR) 정제탑 및 {P_elec/1000:.2f} MW_e 급 복합터빈

==================================================
[ 온실가스(GHG) 및 대기 오염물질 감축량 평가 ]
==================================================
• 연소 직접 배출량 (0.75 kg/kWh 적용): {ghg_direct:.2f} tCO2eq/year
• 미분탄 석탄화력(0.90 kg/kWh) 대비 감축량: {ghg_avoided_vs_coal:.2f} tCO2eq/year
• 대기 오염물질 배출량: NOx {E_elec_annual_kwh*0.08/1000:.1f} kg/yr | SOx {E_elec_annual_kwh*0.03/1000:.1f} kg/yr
"""
            + econ_report
        )


if __name__ == "__main__":
    # 앱 시작 전 폰트 시스템 초기화 (동적 등록)
    init_font_system()

    root = tk.Tk()
    app = RenewableEnergyApp(root)
    root.mainloop()
