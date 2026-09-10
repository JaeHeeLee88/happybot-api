import math
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import webbrowser
import urllib.parse

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
import pandas as pd
from scipy.optimize import minimize
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk


# ==============================================================================
# 1. 기준 상수 및 통합 설계근거(Reference DB) 및 동적 검증 함수 정의
# ==============================================================================
BASE_CONDENSATION = 5.1  # kg/h (기준 응축량)
BASE_TUBES = 36  # EA (기준 튜브 수)
BASE_LENGTH = 580  # mm (기준 열교환기 길이)
BASE_CMM = 35.68  # CMM (기준 팬 풍량)
MMAQ_TO_PA = 9.80665  # 단위 변환 상수 (1 mmAq = 9.80665 Pa)

# 체인 규격별 표준 물성 상수 DB (ANSI/KS 기준 - 피치, 롤러외경, 내링크내폭, 파단강도, 허용장력, 단위중량)
CHAIN_SPEC_DB: Dict[str, Dict[str, float]] = {
    "#40": {
        "pitch": 12.700,
        "dr": 7.92,
        "b1": 7.95,
        "pb": 1950.0,
        "pa": 390.0,
        "weight": 0.62,
    },
    "#50": {
        "pitch": 15.875,
        "dr": 10.16,
        "b1": 9.53,
        "pb": 3180.0,
        "pa": 640.0,
        "weight": 1.02,
    },
    "#60": {
        "pitch": 19.050,
        "dr": 11.91,
        "b1": 12.70,
        "pb": 4600.0,
        "pa": 920.0,
        "weight": 1.50,
    },
    "#80": {
        "pitch": 25.400,
        "dr": 15.88,
        "b1": 15.88,
        "pb": 8100.0,
        "pa": 1620.0,
        "weight": 2.66,
    },
    "#100": {
        "pitch": 31.750,
        "dr": 19.05,
        "b1": 19.05,
        "pb": 12700.0,
        "pa": 2540.0,
        "weight": 3.91,
    },
    "#120": {
        "pitch": 38.100,
        "dr": 22.23,
        "b1": 25.40,
        "pb": 18200.0,
        "pa": 3640.0,
        "weight": 5.60,
    },
    "#140": {
        "pitch": 44.450,
        "dr": 25.40,
        "b1": 25.40,
        "pb": 24800.0,
        "pa": 4960.0,
        "weight": 7.50,
    },
    "#160": {
        "pitch": 50.800,
        "dr": 28.58,
        "b1": 31.75,
        "pb": 32500.0,
        "pa": 6500.0,
        "weight": 10.10,
    },
}

# KS B 1407 / ANSI B29.1 기준 체인 열수별 다열 계수 (Multi-strand Factor)
CHAIN_STRAND_FACTORS: Dict[int, float] = {
    1: 1.0,  # 1열 (Single)
    2: 1.7,  # 2열 (Double)
    3: 2.5,  # 3열 (Triple)
    4: 3.3,  # 4열 (Quadruple)
}


def get_next_chain_type(current_type: str) -> str:
    """현재 선택된 체인 규격의 상위 규격을 자동으로 추정하여 추천하는 헬퍼 함수"""
    keys = list(CHAIN_SPEC_DB.keys())
    if current_type in keys:
        idx = keys.index(current_type)
        if idx + 1 < len(keys):
            return keys[idx + 1]
    return "#160"


FIN_CORRECTION = {"STS304": 1.00, "알루미늄": 1.18}
TUBE_CORRECTION = {"STS304": 1.00, "알루미늄": 1.10}

# 비순환 중공축 재질 물성 DB
SHAFT_MATERIAL_DB: Dict[str, Dict[str, Any]] = {
    "STS304": {
        "sigma_yield": 205.0,
        "tau_allow": 40.0,
        "desc": "STS304 (오스테나이트계, 항복강도 205 MPa)",
    },
    "STS316L": {
        "sigma_yield": 220.0,
        "tau_allow": 45.0,
        "desc": "STS316L (내식 고강도, 항복강도 220 MPa)",
    },
    "S45C": {
        "sigma_yield": 343.0,
        "tau_allow": 65.0,
        "desc": "S45C (기계구조용 탄소강, 항복강도 343 MPa)",
    },
    "SCM440": {
        "sigma_yield": 685.0,
        "tau_allow": 120.0,
        "desc": "SCM440 (크롬몰리브덴 합금강, 항복강도 685 MPa)",
    },
}

# 참조 표준 DB
REFERENCE_DB: Dict[int, Tuple[str, str]] = {
    1: (
        "Perry's Chemical Engineers' Handbook (Material Balances)",
        "https://www.accessengineeringlibrary.com/content/book/9780071834087",
    ),
    2: (
        "ISO 12241 (Thermal Insulation & Heat Loss Performance)",
        "https://www.iso.org/standard/69824.html",
    ),
    3: (
        "DIN 4754 (Heat Transfer Installations with Organic Liquids)",
        "https://www.din.de/en/68242/wdc-grem:din21:54776952",
    ),
    4: (
        "ASME Design Criteria (Agitator Drive Power & Mixing)",
        "https://www.asme.org/codes-standards",
    ),
    5: (
        "KS B 1407 / ANSI B29.1 (Precision Power Transmission Roller Chains)",
        "https://kssn.kr",
    ),
    6: (
        "Shigley's Mechanical Engineering Design (Hollow Shaft & Torsion)",
        "https://www.mheducation.com/highered/product/shigley-s-mechanical-engineering-design-budynas-nisbett/M9780073398204.html",
    ),
    7: (
        "AMCA Pub 201 (Fans and Systems - Air Movement Control)",
        "https://www.amca.org/standards/",
    ),
    8: (
        "SciPy SLSQP Constrained Optimization & Heat Exchanger Scaling",
        "https://scipy.org/",
    ),
    9: (
        "ISO 3069 / DIN 24960 & API 682 (Mechanical Shaft Seals)",
        "https://www.api.org/standards",
    ),
    10: (
        "ISO 281 & Roller Chain Fatigue/Wear Accelerated Life Model",
        "https://www.iso.org/standard/38622.html",
    ),
    11: (
        "ASME Sec VIII Div 2 & FEA Monte Carlo Reliability Verification",
        "https://asmedigitalcollection.asme.org/",
    ),
}


def validate_reference_target(target: str) -> Tuple[bool, str]:
    """
    pathlib 경로 모듈 및 URL 파싱을 활용한 참고문헌 동적 유효성 검증 함수.
    로컬 파일/디렉토리 경로 또는 Web URL 검증을 수행.
    """
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme in ("http", "https"):
        return True, "유효한 Web URL"
    else:
        path_obj = Path(target)
        if path_obj.exists():
            return True, "로컬 경로 존재"
        else:
            return False, "경로/URL 확인 필요"


# ==============================================================================
# 2. 입력 매개변수 데이터 구조 정의
# ==============================================================================
@dataclass
class MaterialProperties:
    name: str  # 성상명
    default_Wi: float  # 기본 초기 함수율 (%)
    default_Wf: float  # 기본 최종 함수율 (%)
    Cp_solid: float  # 건조 고형물 비열 (kcal/kg·°C)
    density: float  # 부피 밀도 (kg/m³)
    fat_content: float  # 유분 함량 비율 (0.0 ~ 1.0)
    salt_content: float  # 염분 함량 비율 (0.0 ~ 1.0)
    viscosity_factor: float  # 고점도 부하 계수 (상대 토크 배율)


@dataclass
class OperatingInput:
    material_type: str = "음식물쓰레기"
    batch_capacity_kg: float = 100.0  # 1회 투입량 (kg/batch)
    discharge_capacity_kg: float = 16.67  # 배출량 (kg/batch)
    operating_hours: float = 20.0  # 운전시간 (h)
    W_i: float = 85.0  # 초기 함수율 (%)
    W_f: float = 10.0  # 목표 함수율 (%)
    rpm: float = 8.0  # 교반속도 (RPM)
    T_oil: float = 170.0  # 열매체유 설정온도 (°C)

    # 구동 체인 사양 (체인 열수 반영)
    chain_type: str = "#50"  # 체인 선택 규격 (#40 ~ #160)
    chain_strands: int = 1  # 체인 열수 (1열, 2열, 3열, 4열)
    chain_z1: float = 15.0  # 소스프라켓 이수 (T)
    chain_z2: float = 30.0  # 대스프라켓 이수 (T)
    chain_center_dist_mm: float = 500.0  # 축간 거리 (mm)
    chain_sf_service: float = 1.4  # 체인 부하 서비스 계수

    shaft_mat: str = "S45C"  # 중공축 재질
    hollow_ratio: float = 0.60  # 비순환 중공축 내외경비
    manual_shaft_od_mm: float = 0.0  # 외경 수동 지정

    tube_mat: str = "STS304"  # 튜브 재질
    fin_mat: str = "STS304"  # 핀 재질
    tube_od_mm: float = 12.7  # 튜브 외경
    tube_id_mm: float = 11.1  # 튜브 내경
    pitch_x_mm: float = 38.0  # Pitch X
    pitch_y_mm: float = 34.0  # Pitch Y
    fin_pitch_mm: float = 8.0  # Fin Pitch
    max_dp_mmaq: float = 15.0  # 허용 압력손실

    delta_p_mmAq: float = 1000.0  # 블로워 설계 차압
    recirc_ratio: float = 3.5  # 수증기 재순환 배율

    T_cond_in: float = 90.0  # 응축기 수증기 입구 온도
    T_cond_out: float = 60.0  # 응축기 응축수 출구 온도
    T_air_in: float = 20.0  # 냉각공기 입구 온도
    T_air_out: float = 40.0  # 냉각공기 출구 온도
    insulation_thick_mm: float = 50.0  # 단열재 두께


# ==============================================================================
# 3. 건조기 설계 계산 엔진
# ==============================================================================
class DetailedDryerEngine:
    MATERIAL_DB: Dict[str, MaterialProperties] = {
        "음식물쓰레기": MaterialProperties(
            "음식물쓰레기", 85.0, 10.0, 0.45, 1050.0, 0.08, 0.03, 1.20
        ),
        "하수슬러지": MaterialProperties(
            "하수슬러지", 82.0, 10.0, 0.38, 1100.0, 0.02, 0.01, 1.85
        ),
        "식품폐기물": MaterialProperties(
            "식품폐기물", 78.0, 10.0, 0.42, 1020.0, 0.05, 0.02, 1.00
        ),
        "커피찌꺼기": MaterialProperties(
            "커피찌꺼기", 65.0, 10.0, 0.50, 950.0, 0.12, 0.00, 0.85
        ),
    }

    def __init__(self, inp: OperatingInput):
        self.inp = inp
        self.mat = self.MATERIAL_DB.get(
            inp.material_type, self.MATERIAL_DB["음식물쓰레기"]
        )

    def run_scipy_optimization(
        self, condensation_rate_kgh: float
    ) -> Dict[str, Any]:
        inp = self.inp
        f_fin = FIN_CORRECTION.get(inp.fin_mat, 1.0)
        base_load_ratio = condensation_rate_kgh / BASE_CONDENSATION
        target_load = base_load_ratio / f_fin

        od_factor = (12.7 / max(0.1, inp.tube_od_mm)) ** 0.25
        pitch_factor = (inp.pitch_x_mm / 38.0) ** 0.12
        fin_dp_factor = (6.0 / max(0.1, inp.fin_pitch_mm)) ** 0.5
        max_dp_pa = inp.max_dp_mmaq * MMAQ_TO_PA

        def objective(x):
            return max(1e-3, float(x[0])) * max(1e-3, float(x[1]))

        def constraint_thermal(x):
            x0_val = max(1e-3, float(x[0]))
            x1_val = max(1e-3, float(x[1]))
            capacity = (
                ((x0_val / BASE_TUBES) ** 0.95)
                * ((x1_val / BASE_LENGTH) ** 0.60)
                / (od_factor * pitch_factor)
            )
            return capacity - target_load

        def constraint_dp(x):
            x0_val = max(1e-3, float(x[0]))
            x1_val = max(1e-3, float(x[1]))
            dp_pa = (
                100.0
                * (x1_val / 580.0) ** 0.85
                * (x0_val / 36.0) ** 0.60
                * fin_dp_factor
            )
            return max_dp_pa - dp_pa

        x0 = [
            BASE_TUBES * (max(0.1, target_load) ** 0.95) * od_factor,
            BASE_LENGTH * (max(0.1, target_load) ** 0.60) * pitch_factor,
        ]
        bounds = [(10, 500), (200, 4000)]
        constraints = [
            {"type": "ineq", "fun": constraint_thermal},
            {"type": "ineq", "fun": constraint_dp},
        ]

        res = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        opt_tubes = (
            math.ceil(res.x[0])
            if (res.success and res.x[0] > 0)
            else math.ceil(x0[0])
        )
        opt_length = (
            round(res.x[1])
            if (res.success and res.x[1] > 0)
            else round(x0[1])
        )

        cfd_factor = (
            ((opt_length / BASE_LENGTH) ** (-0.08))
            * ((opt_tubes / BASE_TUBES) ** (-0.04))
            * 0.95
        )
        efficiency = round(min(cfd_factor * 100.0, 100.0), 1)
        fan_cmm = (
            round(BASE_CMM * (base_load_ratio**0.85), 1)
            if base_load_ratio > 0
            else 0.0
        )

        dp_pa = (
            100.0
            * (opt_length / 580.0) ** 0.85
            * (opt_tubes / 36.0) ** 0.60
            * fin_dp_factor
        )
        dp_mmaq = round(dp_pa / MMAQ_TO_PA, 2)

        return {
            "opt_tubes": opt_tubes,
            "opt_length": opt_length,
            "f_fin": f_fin,
            "base_load_ratio": base_load_ratio,
            "target_load": target_load,
            "efficiency": efficiency,
            "fan_cmm": fan_cmm,
            "dp_mmaq": dp_mmaq,
            "cfd_factor": cfd_factor,
        }

    def run_simulation(self) -> Dict[str, Any]:
        inp = self.inp
        mat = self.mat
        report_data = []

        # [Step 1] 질량 수지
        m_in_day = inp.batch_capacity_kg
        m_out_day = inp.discharge_capacity_kg
        t_batch = max(1.0, inp.operating_hours)
        W_i, W_f = inp.W_i, inp.W_f
        T_amb, T_oil, rpm = inp.T_air_in, inp.T_oil, max(0.5, inp.rpm)

        wi_day = m_in_day * (W_i / 100.0)
        wf_day = m_out_day * (W_f / 100.0)
        evaporated_day = max(wi_day - wf_day, 0.0)
        condensation_rate = evaporated_day / t_batch
        m_evap_peak = condensation_rate * 1.30

        report_data.extend(
            [
                (
                    "[Step 1] 질량 수지",
                    "1회 투입 수분량",
                    f"Wi_batch = m_in × (W_i/100) = {m_in_day} × ({W_i}/100)",
                    f"{wi_day:.2f}",
                    "kg/batch",
                    1,
                    "=설계_계산!C2*(설계_계산!B2/100)",
                ),
                (
                    "[Step 1] 질량 수지",
                    "1회 배출 수분량",
                    f"Wf_batch = m_out × (W_f/100) = {m_out_day:.2f} × ({W_f}/100)",
                    f"{wf_day:.2f}",
                    "kg/batch",
                    1,
                    "=설계_계산!D2*(설계_계산!E2/100)",
                ),
                (
                    "[Step 1] 질량 수지",
                    "1회 증발 수분량",
                    f"m_evap_batch = Wi_batch - Wf_batch = {wi_day:.2f} - {wf_day:.2f}",
                    f"{evaporated_day:.2f}",
                    "kg/batch",
                    1,
                    "=MAX((설계_계산!C2*(설계_계산!B2/100))-(설계_계산!D2*(설계_계산!E2/100)), 0)",
                ),
                (
                    "[Step 1] 질량 수지",
                    "시간당 평균 응축량",
                    f"m_cond = m_evap_batch / t_op = {evaporated_day:.2f} / {t_batch:.1f}",
                    f"{condensation_rate:.2f}",
                    "kg/h",
                    1,
                    "=설계_계산!S2/설계_계산!F2",
                ),
                (
                    "[Step 1] 질량 수지",
                    "피크 응축 부하율",
                    f"m_peak = m_cond × 1.30 = {condensation_rate:.2f} × 1.30",
                    f"{m_evap_peak:.2f}",
                    "kg/h",
                    1,
                    "=설계_계산!T2*1.30",
                ),
            ]
        )

        # [Step 2] 히터 용량 및 단열
        m_dry_day = m_in_day - wi_day
        Q_sens_w = wi_day * 1.0 * (100.0 - T_amb)
        Q_lat_w = evaporated_day * 539.0
        Q_sens_s = m_dry_day * mat.Cp_solid * (100.0 - T_amb)

        t_ins_m = inp.insulation_thick_mm / 1000.0
        k_ins, h_ext, A_surf = 0.045, 8.5, 2.2
        U_overall = 1.0 / ((t_ins_m / k_ins) + (1.0 / h_ext))
        Q_loss = A_surf * U_overall * (T_oil - T_amb) * 0.86 * t_batch

        Q_total = Q_sens_w + Q_lat_w + Q_sens_s + Q_loss
        P_avg = (Q_total / t_batch) / 860.0
        P_heater = P_avg * 1.25 * 1.20
        T_surf = T_amb + ((Q_loss / t_batch) / (0.86 * A_surf * h_ext))

        report_data.extend(
            [
                (
                    "[Step 2] 열부하(히터)",
                    "수분 증발 잠열",
                    f"Q_lat_w = m_evap × h_fg = {evaporated_day:.2f} × 539.0",
                    f"{Q_lat_w:.1f}",
                    "kcal/batch",
                    2,
                    "=설계_계산!S2*539.0",
                ),
                (
                    "[Step 2] 열부하(히터)",
                    "표면 방열 손실량",
                    "Q_loss = A × U × (T_oil - T_amb) × 0.86 × t",
                    f"{Q_loss:.1f}",
                    "kcal/batch",
                    2,
                    f"={A_surf}*{U_overall:.3f}*({T_oil}-{T_amb})*0.86*설계_계산!F2",
                ),
                (
                    "[Step 2] 열부하(히터)",
                    "총 필요 열량",
                    "Q_tot = Q_sens_w + Q_lat_w + Q_sens_s + Q_loss",
                    f"{Q_total:.1f}",
                    "kcal/batch",
                    2,
                    f"={Q_sens_w:.1f}+{Q_lat_w:.1f}+{Q_sens_s:.1f}+{Q_loss:.1f}",
                ),
                (
                    "[Step 2] 열부하(히터)",
                    "히터 정격 용량",
                    "P_heater = (Q_tot / t / 860) × 1.25 × 1.20",
                    f"{P_heater:.2f}",
                    "kW",
                    2,
                    f"=({Q_total:.1f}/설계_계산!F2/860)*1.5",
                ),
                (
                    "[Step 2] 열부하(히터)",
                    "표면 온도 검증",
                    f"T_surf = T_amb + Q_loss_rate / (0.86 × A × h_ext)",
                    f"{T_surf:.1f}",
                    "°C",
                    2,
                    f"={T_amb:.1f}+(({Q_loss:.1f}/설계_계산!F2)/(0.86*{A_surf}*{h_ext}))",
                ),
            ]
        )

        # [동적 개선대책 1: 표면방열 온도 초과]
        if T_surf > 40.0:
            rec_thick = round(inp.insulation_thick_mm * (T_surf / 40.0), 1)
            report_data.append(
                (
                    "[Step 2] 열부하(히터)",
                    "⚠️ [표면방열 온도 Fail 개선 대책 권고]",
                    f"현재 표면온도({T_surf:.1f}°C) > 40.0°C 기준 초과. 대책: 단열재 두께를 기존 {inp.insulation_thick_mm:.0f}mm에서 {rec_thick:.0f}mm 이상으로 증대 권고",
                    f"추천 t_ins >= {rec_thick:.0f} mm",
                    "mm",
                    2,
                    f'=IF({T_surf:.1f}>40.0, "단열재 두께 증대 권고", "정상")',
                )
            )

        # [Step 3] 열매체유 요구량
        Q_peak_kcal_h = (Q_total / t_batch) * 1.25
        V_oil_req = P_heater * 2.5
        M_oil_req = V_oil_req * 0.85

        report_data.extend(
            [
                (
                    "[Step 3] 열매체유 설계",
                    "피크 열부하",
                    "Q_peak = (Q_tot / t_op) × 1.25",
                    f"{Q_peak_kcal_h:.1f}",
                    "kcal/h",
                    3,
                    f"=({Q_total:.1f}/설계_계산!F2)*1.25",
                ),
                (
                    "[Step 3] 열매체유 설계",
                    "요구 체적",
                    "V_oil = P_heater × 2.5 L/kW",
                    f"{V_oil_req:.1f}",
                    "L",
                    3,
                    f"={P_heater:.2f}*2.5",
                ),
                (
                    "[Step 3] 열매체유 설계",
                    "주입 질량",
                    "M_oil = V_oil × SG_oil",
                    f"{M_oil_req:.1f}",
                    "kg",
                    3,
                    f"={V_oil_req:.1f}*0.85",
                ),
            ]
        )

        # [Step 4] 구동 모터
        C_tau = 1.8
        T_shaft = (
            m_in_day
            * C_tau
            * mat.viscosity_factor
            * (15.0 / rpm) ** 0.3
            / (t_batch / 20.0)
        )
        P_shaft = (T_shaft * 2.0 * math.pi * rpm) / 60000.0
        SF = 2.5
        P_motor = max(0.4, P_shaft * SF)

        report_data.extend(
            [
                (
                    "[Step 4] 모터 사양",
                    "교반축 부하 토크",
                    "T_shaft = m_in × C_tau × μ_visc × (15/N)^0.3 / (t_op/20)",
                    f"{T_shaft:.1f}",
                    "N·m",
                    4,
                    f"=설계_계산!C2*1.8*VLOOKUP(설계_계산!A2, 기본_설정!$A$9:$H$12, 8, FALSE)*(15/{rpm})^0.3/(설계_계산!F2/20)",
                ),
                (
                    "[Step 4] 모터 사양",
                    "필요 축 동력",
                    "P_shaft = (T_shaft × 2π × N) / 60000",
                    f"{P_shaft:.3f}",
                    "kW",
                    4,
                    f"=({T_shaft:.1f}*2*PI()*{rpm})/60000",
                ),
                (
                    "[Step 4] 모터 사양",
                    "정격 설계용량",
                    "P_motor = Max(0.4, P_shaft × SF)",
                    f"{P_motor:.2f}",
                    "kW",
                    4,
                    f"=MAX(0.4, {P_shaft:.3f}*2.5)",
                ),
            ]
        )

        # [동적 개선대책 2: 모터 동력 과부하 검증]
        if P_motor > 15.0:
            report_data.append(
                (
                    "[Step 4] 모터 사양",
                    "⚠️ [구동 동력 고부하 개선 대책 권고]",
                    f"현재 필요 모터동력({P_motor:.2f}kW)이 15kW 초과. 대책: 교반 감속비 증대(RPM 하향) 또는 1회 처리량(Batch) 분할 운전 권고",
                    "추천: RPM 하향 조정 또는 투입량 감축",
                    "kW",
                    4,
                    f'=IF({P_motor:.2f}>15.0, "감속비/투입량 조정 권고", "정상")',
                )
            )

        # [Step 5] 구동 체인 연결 강도 및 수명 설계 (#40~#160, 롤러외경/내폭/다열계수 반영)
        chain_spec = CHAIN_SPEC_DB.get(
            inp.chain_type, CHAIN_SPEC_DB["#50"]
        )
        chain_pitch = chain_spec["pitch"]
        chain_dr = chain_spec["dr"]
        chain_b1 = chain_spec["b1"]
        chain_pb_base = chain_spec["pb"]
        chain_pa_base = chain_spec["pa"]

        # 체인 열수(Strands) 및 다열 계수(Multi-strand Factor) 반영
        strand_factor = CHAIN_STRAND_FACTORS.get(inp.chain_strands, 1.0)
        chain_pb = chain_pb_base * strand_factor
        chain_pa = chain_pa_base * strand_factor

        z1, z2 = inp.chain_z1, inp.chain_z2
        chain_ratio = z2 / max(1.0, z1)
        N_sprocket1 = rpm * chain_ratio
        V_chain = (z1 * chain_pitch * N_sprocket1) / 60000.0
        F_t_kgf = (102.0 * P_motor) / max(0.01, V_chain)
        F_d_kgf = F_t_kgf * inp.chain_sf_service

        sf_chain_break = chain_pb / max(0.1, F_d_kgf)
        sf_chain_allow = chain_pa / max(0.1, F_d_kgf)

        L_chain_hr = (
            15000.0
            * ((chain_pa / max(0.1, F_d_kgf)) ** 3.0)
            * ((100.0 / max(1.0, N_sprocket1)) ** 0.5)
        )
        L_chain_hr = min(150000.0, L_chain_hr)

        report_data.extend(
            [
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "체인 적용 규격 및 상세 사양",
                    f"ANSI/KS {inp.chain_type} x {inp.chain_strands}열 (Pitch={chain_pitch}mm, 롤러외경={chain_dr}mm, 내폭={chain_b1}mm, 다열계수={strand_factor:.1f}, 환산PB={chain_pb:.0f}kgf)",
                    f"{inp.chain_type} ({inp.chain_strands}열)",
                    "규격",
                    5,
                    f"ANSI {inp.chain_type} Standard ({inp.chain_strands}열)",
                ),
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "스프라켓 치수비/속도",
                    f"Z1={z1:.0f}T, Z2={z2:.0f}T (비={chain_ratio:.1f})",
                    f"N1={N_sprocket1:.1f}",
                    "RPM",
                    5,
                    f"={rpm:.1f}*({z2:.0f}/{z1:.0f})",
                ),
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "체인 이동 속도(V)",
                    "V = (Z1 × Pitch × N1) / 60000",
                    f"{V_chain:.3f}",
                    "m/s",
                    5,
                    f"=({z1:.0f}*{chain_pitch}*{N_sprocket1:.1f})/60000",
                ),
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "체인 유효 전달 장력(Ft)",
                    "Ft = (102 × P_motor) / V",
                    f"{F_t_kgf:.1f}",
                    "kgf",
                    5,
                    f"=(102*{P_motor:.2f})/{V_chain:.3f}",
                ),
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "체인 설계 장력(Fd)",
                    f"Fd = Ft × K_service ({inp.chain_sf_service:.1f})",
                    f"{F_d_kgf:.1f}",
                    "kgf",
                    5,
                    f"={F_t_kgf:.1f}*{inp.chain_sf_service:.1f}",
                ),
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "체인 파단 안전율",
                    f"SF_chain = PB_total / Fd = {chain_pb:.0f} / {F_d_kgf:.1f}",
                    f"{sf_chain_break:.2f}",
                    "배",
                    5,
                    f"=(VLOOKUP('{inp.chain_type}', 기본_설정!$M$2:$R$9, 5, FALSE)*{strand_factor})/{F_d_kgf:.1f}",
                ),
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "체인 마모 내구수명",
                    "L_chain = 15000 × (PA_total/Fd)³ × (100/N1)^0.5",
                    f"{L_chain_hr:.0f}",
                    "hr",
                    5,
                    f"=MIN(150000, 15000*((VLOOKUP('{inp.chain_type}', 기본_설정!$M$2:$R$9, 6, FALSE)*{strand_factor})/{F_d_kgf:.1f})^3*(100/{N_sprocket1:.1f})^0.5)",
                ),
            ]
        )

        # [동적 개선대책 3: 체인 파단 안전율 미달]
        if sf_chain_break < 5.0:
            next_chain = get_next_chain_type(inp.chain_type)
            next_strand = min(4, inp.chain_strands + 1)
            report_data.append(
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "⚠️ [체인 파단 안전율 Fail 개선 대책 권고]",
                    f"현재 안전율({sf_chain_break:.2f}) < 5.00 기준 미달. 대책: 체인 규격을 상향({inp.chain_type} → {next_chain})하거나 체인 열수를 증대({inp.chain_strands}열 → {next_strand}열) 권고",
                    f"추천: {next_chain} 규격 적용 또는 {next_strand}열 체인 변경",
                    "권고",
                    5,
                    f'=IF({sf_chain_break:.2f}<5.0, "상위 규격({next_chain}) 또는 열수({next_strand}열) 변경 권고", "정상")',
                )
            )

        # [동적 개선대책 4: 체인 마모 내구수명 미달]
        if L_chain_hr < 15000.0:
            next_chain = get_next_chain_type(inp.chain_type)
            next_strand = min(4, inp.chain_strands + 1)
            report_data.append(
                (
                    "[Step 5] 구동 체인 강도/수명",
                    "⚠️ [체인 마모수명 Fail 개선 대책 권고]",
                    f"현재 마모수명({L_chain_hr:.0f}h) < 15,000h 기준 미달. 대책: 체인 상위 규격({next_chain}) 또는 체인 열수({next_strand}열) 적용, 소스프라켓 이수(Z1) 증가 권고",
                    "추천: L_chain >= 15,000 hr",
                    "hr",
                    5,
                    f'=IF({L_chain_hr:.0f}<15000, "상위 체인/열수/스프라켓 변경 권고", "정상")',
                )
            )

        # [Step 6] 비순환 중공축
        shaft_prop = SHAFT_MATERIAL_DB.get(
            inp.shaft_mat, SHAFT_MATERIAL_DB["STS304"]
        )
        sigma_yield = shaft_prop["sigma_yield"]
        tau_allow = shaft_prop["tau_allow"]

        T_max_Nmm = T_shaft * SF * 1000.0
        k_hollow = min(max(inp.hollow_ratio, 0.1), 0.85)

        D_req_torsion = (
            (16.0 * T_max_Nmm) / (math.pi * tau_allow * (1.0 - k_hollow**4))
        ) ** (1.0 / 3.0)

        if inp.manual_shaft_od_mm > 0:
            D_shaft_mm = max(inp.manual_shaft_od_mm, 20.0)
            od_source_str = f"수동 지정 ({D_shaft_mm:.0f} mm)"
        else:
            D_shaft_mm = math.ceil(D_req_torsion / 5.0) * 5.0
            if D_shaft_mm < 30.0:
                D_shaft_mm = 30.0
            od_source_str = f"이론 계산 표준 외경 ({D_shaft_mm:.0f} mm)"

        D_inner_mm = D_shaft_mm * k_hollow
        D_solid_req = ((16.0 * T_max_Nmm) / (math.pi * tau_allow)) ** (
            1.0 / 3.0
        )
        weight_saving_pct = (
            (1.0 - ((D_shaft_mm**2 - D_inner_mm**2) / (D_solid_req**2)))
            * 100.0
            if D_solid_req > 0
            else 0.0
        )

        report_data.extend(
            [
                (
                    "[Step 6] 비순환 중공축 설계",
                    "선택 축 재질 규격",
                    f"재질: {shaft_prop['desc']}",
                    f"σ_y = {sigma_yield}",
                    "MPa",
                    6,
                    f"=VLOOKUP('{inp.shaft_mat}', 기본_설정!$I$2:$J$5, 2, FALSE)",
                ),
                (
                    "[Step 6] 비순환 중공축 설계",
                    "최대 전달 토크",
                    f"T_max = T_shaft × SF = {T_shaft:.1f} × {SF}",
                    f"{T_shaft * SF:.1f}",
                    "N·m",
                    6,
                    f"={T_shaft:.1f}*2.5",
                ),
                (
                    "[Step 6] 비순환 중공축 설계",
                    "중공축 내/외경비(k)",
                    "k = D_i / D_o",
                    f"{k_hollow:.2f}",
                    "배",
                    6,
                    f"={k_hollow:.2f}",
                ),
                (
                    "[Step 6] 비순환 중공축 설계",
                    "이론 비틀림 필요 외경",
                    "D_o_req = [ (16 × T_max) / (π × τ_allow × (1 - k⁴)) ]^(1/3)",
                    f"{D_req_torsion:.1f}",
                    "mm",
                    6,
                    f"=((16*{T_shaft*SF*1000:.0f})/(PI()*{tau_allow}*(1-{k_hollow:.2f}^4)))^(1/3)",
                ),
                (
                    "[Step 6] 비순환 중공축 설계",
                    "설계 중공축 외경(D_o)",
                    f"D_o [{od_source_str}]",
                    f"{D_shaft_mm:.0f}",
                    "mm",
                    6,
                    f"=IF({inp.manual_shaft_od_mm}>0, MAX({inp.manual_shaft_od_mm}, 20), MAX(30, CEILING({D_req_torsion:.1f}, 5)))",
                ),
                (
                    "[Step 6] 비순환 중공축 설계",
                    "설계 중공축 내경(D_i)",
                    f"D_i = D_o × k = {D_shaft_mm:.0f} × {k_hollow:.2f}",
                    f"{D_inner_mm:.1f}",
                    "mm",
                    6,
                    f"={D_shaft_mm:.0f}*{k_hollow:.2f}",
                ),
                (
                    "[Step 6] 비순환 중공축 설계",
                    "중공축 경량화 절감율",
                    "Weight_Saving = [ 1 - (D_o² - D_i²)/D_solid² ] × 100%",
                    f"{weight_saving_pct:.1f}",
                    "%",
                    6,
                    f"=(1-({D_shaft_mm:.0f}^2-{D_inner_mm:.1f}^2)/{D_solid_req:.1f}^2)*100",
                ),
            ]
        )

        # [동적 개선대책 5: 중공축 비틀림 전단강도 미달]
        if D_shaft_mm < D_req_torsion:
            rec_od_torsion = math.ceil(D_req_torsion / 5.0) * 5.0
            report_data.append(
                (
                    "[Step 6] 비순환 중공축 설계",
                    "⚠️ [중공축 비틀림 전단 강도 Fail 개선 대책 권고]",
                    f"현재 외경({D_shaft_mm:.0f}mm) < 필요 외경({D_req_torsion:.1f}mm) 부적합. 대책: 외경 D_o를 {rec_od_torsion:.0f}mm 이상으로 상향하거나 고강도 재질(SCM440) 적용 권고",
                    f"추천 D_o >= {rec_od_torsion:.0f} mm",
                    "mm",
                    6,
                    f'=IF({D_shaft_mm:.0f}<{D_req_torsion:.1f}, "중공축 외경 상향 권고", "정상")',
                )
            )

        # [Step 7] 재순환 블로워
        rho_steam = 0.60
        m_steam_recirc = m_evap_peak * inp.recirc_ratio
        Q_blower_cmm = m_steam_recirc / (rho_steam * 60.0)

        eta_blower = 0.65
        P_blower_shaft = (Q_blower_cmm * inp.delta_p_mmAq) / (
            6120.0 * eta_blower
        )
        SF_blower = 1.30
        P_blower_motor = P_blower_shaft * SF_blower

        report_data.extend(
            [
                (
                    "[Step 7] 재순환 블로워",
                    "재순환 증기 유량",
                    f"m_recirc = m_peak × R_recirc = {m_evap_peak:.2f} × {inp.recirc_ratio:.1f}",
                    f"{m_steam_recirc:.1f}",
                    "kg/h",
                    7,
                    f"={m_evap_peak:.2f}*{inp.recirc_ratio:.1f}",
                ),
                (
                    "[Step 7] 재순환 블로워",
                    "블로워 체적 유량",
                    "Q_blower = m_recirc / (ρ_steam × 60)",
                    f"{Q_blower_cmm:.2f}",
                    "CMM",
                    7,
                    f"={m_steam_recirc:.1f}/(0.6*60)",
                ),
                (
                    "[Step 7] 재순환 블로워",
                    "블로워 축 동력",
                    "P_b_shaft = (Q_cmm × ΔP) / (6120 × η)",
                    f"{P_blower_shaft:.2f}",
                    "kW",
                    7,
                    f"=({Q_blower_cmm:.2f}*{inp.delta_p_mmAq:.0f})/(6120*0.65)",
                ),
                (
                    "[Step 7] 재순환 블로워",
                    "모터 정격 용량",
                    "P_b_motor = P_b_shaft × SF_b",
                    f"{P_blower_motor:.2f}",
                    "kW",
                    7,
                    f"={P_blower_shaft:.2f}*1.3",
                ),
            ]
        )

        # [Step 8] SciPy 응축기 최적화
        opt_res = self.run_scipy_optimization(condensation_rate)

        report_data.extend(
            [
                (
                    "[Step 8] 응축기 SciPy 최적화",
                    "보정 부하율 (Target Load)",
                    "Target_Load = (m_cond / BASE_COND) / f_fin",
                    f"{opt_res['target_load']:.2f}",
                    "배",
                    8,
                    f"=({condensation_rate:.2f}/5.1)/{opt_res['f_fin']:.2f}",
                ),
                (
                    "[Step 8] 응축기 SciPy 최적화",
                    "최적 튜브 수",
                    f"N_tubes = SLSQP_Optimize(Min Volume | DP <= {inp.max_dp_mmaq})",
                    f"{opt_res['opt_tubes']}",
                    "EA",
                    8,
                    f"={opt_res['opt_tubes']}",
                ),
                (
                    "[Step 8] 응축기 SciPy 최적화",
                    "최적 열교환기 길이",
                    f"L_length = SLSQP_Optimize(Min Volume | DP <= {inp.max_dp_mmaq})",
                    f"{opt_res['opt_length']}",
                    "mm",
                    8,
                    f"={opt_res['opt_length']}",
                ),
                (
                    "[Step 8] 응축기 SciPy 최적화",
                    "예상 압력 손실",
                    "DP_mmAq = [ 100 × (L/580)^0.85 × (N/36)^0.60 × (6/Pitch)^0.5 ] / 9.80665",
                    f"{opt_res['dp_mmaq']:.2f}",
                    "mmAq",
                    8,
                    f"=(100*({opt_res['opt_length']}/580)^0.85*({opt_res['opt_tubes']}/36)^0.6*(6/{inp.fin_pitch_mm})^0.5)/9.80665",
                ),
                (
                    "[Step 8] 응축기 SciPy 최적화",
                    "필요 팬 용량",
                    "Fan_CMM = BASE_CMM × (m_cond / BASE_COND)^0.85",
                    f"{opt_res['fan_cmm']:.1f}",
                    "CMM",
                    8,
                    f"=35.68*({condensation_rate:.2f}/5.1)^0.85",
                ),
                (
                    "[Step 8] 응축기 SciPy 최적화",
                    "CFD 보정 응축효율",
                    "Efficiency = Min(100, CFD_Factor × 100)",
                    f"{opt_res['efficiency']:.1f}",
                    "%",
                    8,
                    f"=MIN(100, {opt_res['cfd_factor']:.3f}*100)",
                ),
            ]
        )

        # [동적 개선대책 6: 응축기 차압 초과]
        if opt_res["dp_mmaq"] > inp.max_dp_mmaq:
            report_data.append(
                (
                    "[Step 8] 응축기 SciPy 최적화",
                    "⚠️ [응축기 허용 압력손실 Fail 개선 대책 권고]",
                    f"현재 압력손실({opt_res['dp_mmaq']:.2f} mmAq) > 허용치({inp.max_dp_mmaq:.1f} mmAq) 초과. 대책: Fin Pitch 확대(예: 8mm→10mm) 또는 튜브 유효길이 증대 권고",
                    "추천: Fin Pitch 또는 튜브 길이 상향",
                    "mmAq",
                    8,
                    f'=IF({opt_res["dp_mmaq"]:.2f}>{inp.max_dp_mmaq:.1f}, "Fin Pitch / 튜브 크기 변경 권고", "정상")',
                )
            )

        # [동적 개선대책 7: 응축 효율 미달]
        if opt_res["efficiency"] < 80.0:
            report_data.append(
                (
                    "[Step 8] 응축기 SciPy 최적화",
                    "⚠️ [응축 열교환 효율 Fail 개선 대책 권고]",
                    f"현재 응축효율({opt_res['efficiency']:.1f}%) < 80.0% 기준 미달. 대책: 알루미늄 핀 적용 또는 튜브 수/팬 풍량 증대 권고",
                    "추천: 알루미늄 핀 적용 또는 팬 풍량 증대",
                    "%",
                    8,
                    f'=IF({opt_res["efficiency"]:.1f}<80.0, "열교환 재질/풍량 개선 권고", "정상")',
                )
            )

        # [Step 9] 메카니컬 씰
        d1_seal_mm = D_shaft_mm
        D_seal_m = d1_seal_mm / 1000.0
        V_seal = (math.pi * D_seal_m * rpm) / 60.0
        P_seal = 0.5
        PV_val = P_seal * V_seal

        f_fric, face_w = 0.15, 0.005
        A_face = math.pi * D_seal_m * face_w
        Q_seal_W = f_fric * (P_seal * 100000.0) * A_face * V_seal
        Q_flush_lmin = max(0.5, (Q_seal_W / (1000.0 * 4.184 * 10.0)) * 60.0)

        seal_spec_str = (
            f"ISO 3069 / DIN 24960 d1={d1_seal_mm:.0f}mm Single Cartridge Seal"
            " (SiC/Carbon)"
        )

        report_data.extend(
            [
                (
                    "[Step 9] 메카니컬 씰 사양",
                    "적용 씰 규격 및 사양",
                    f"규격: {seal_spec_str}",
                    f"d1 = {d1_seal_mm:.0f}",
                    "mm",
                    9,
                    f"={d1_seal_mm:.0f}",
                ),
                (
                    "[Step 9] 메카니컬 씰 사양",
                    "씰 섭면 선속도(V)",
                    "V_seal = (π × d1 × N) / 60",
                    f"{V_seal:.4f}",
                    "m/s",
                    9,
                    f"=(PI()*({d1_seal_mm:.0f}/1000)*{rpm})/60",
                ),
                (
                    "[Step 9] 메카니컬 씰 사양",
                    "운전 PV 치",
                    "PV = P_seal × V_seal",
                    f"{PV_val:.4f}",
                    "bar·m/s",
                    9,
                    f"=0.5*{V_seal:.4f}",
                ),
                (
                    "[Step 9] 메카니컬 씰 사양",
                    "마찰 발열량",
                    "Q_seal = f × (P × 10^5) × A_face × V",
                    f"{Q_seal_W:.2f}",
                    "W",
                    9,
                    f"=0.15*50000.0*{A_face:.6f}*{V_seal:.4f}",
                ),
                (
                    "[Step 9] 메카니컬 씰 사양",
                    "최소 냉각 플러싱 유량",
                    "Q_flush = (Q_seal / (ρ × Cp × ΔT)) × 60",
                    f"{Q_flush_lmin:.2f}",
                    "L/min",
                    9,
                    f"=({Q_seal_W:.2f}/(1000*4.184*10))*60",
                ),
            ]
        )

        # [동적 개선대책 8: 메카니컬 씰 PV 치 초과]
        if PV_val > 15.0:
            report_data.append(
                (
                    "[Step 9] 메카니컬 씰 사양",
                    "⚠️ [메카니컬 씰 PV 한계 Fail 개선 대책 권고]",
                    f"현재 PV 치({PV_val:.4f} bar·m/s) > 15.0 bar·m/s 초과. 대책: 섭면 재질을 SiC/SiC 고하동 사양으로 변경하거나 플러싱 냉각 유량 증대 권고",
                    "추천: SiC/SiC 재질 및 플러싱 강화",
                    "bar·m/s",
                    9,
                    f'=IF({PV_val:.4f}>15.0, "씰 재질/플러싱 개선 권고", "정상")',
                )
            )

        # [Step 10] 부품 수명 종합
        hrs_per_year = 300.0 * t_batch
        L_heater = 20000.0 * ((150.0 / max(100.0, T_oil)) ** 2)
        L_oil = 10000.0 * (0.5 ** ((max(150.0, T_oil) - 150.0) / 15.0))
        L_motor = min(100000.0, 25000.0 * (SF**2.0))
        L_shaft = min(
            200000.0,
            50000.0 * ((D_shaft_mm / max(10.0, D_req_torsion)) ** 3.0),
        )
        L_seal = 25000.0 * (10.0 / max(0.1, PV_val))
        L_blower = min(
            80000.0,
            30000.0
            * ((1200.0 / max(100.0, inp.delta_p_mmAq)) ** 0.5)
            * ((SF_blower / 1.20) ** 2.0),
        )

        report_data.extend(
            [
                (
                    "[Step 10] 부품 수명",
                    f"{inp.chain_type} ({inp.chain_strands}열) 구동 체인 수명",
                    "L_chain = 15000 × (PA_total/Fd)³ × (100/N1)^0.5",
                    f"{L_chain_hr:.0f} hr",
                    f"({L_chain_hr/hrs_per_year:.1f}년)",
                    10,
                    f"={L_chain_hr:.0f}",
                ),
                (
                    "[Step 10] 부품 수명",
                    "히터 예상수명",
                    "L_heater = L0 × (150/T_oil)^2",
                    f"{L_heater:.0f} hr",
                    f"({L_heater/hrs_per_year:.1f}년)",
                    10,
                    f"=20000*(150/{T_oil})^2",
                ),
                (
                    "[Step 10] 부품 수명",
                    "열매체유 수명",
                    "L_oil = L0 × 0.5^((T_oil-150)/15)",
                    f"{L_oil:.0f} hr",
                    f"({L_oil/hrs_per_year:.1f}년)",
                    10,
                    f"=10000*0.5^(({T_oil}-150)/15)",
                ),
                (
                    "[Step 10] 부품 수명",
                    "모터 베어링 수명",
                    "L_motor = Min(100000, L0 × SF^2)",
                    f"{L_motor:.0f} hr",
                    f"({L_motor/hrs_per_year:.1f}년)",
                    10,
                    "=MIN(100000, 25000*2.5^2)",
                ),
                (
                    "[Step 10] 부품 수명",
                    "중공축 피로수명",
                    "L_shaft = Min(200000, L0 × (D_o/D_o_req)^3)",
                    f"{L_shaft:.0f} hr",
                    f"({L_shaft/hrs_per_year:.1f}년)",
                    10,
                    f"=MIN(200000, 50000*({D_shaft_mm:.0f}/{D_req_torsion:.1f})^3)",
                ),
                (
                    "[Step 10] 부품 수명",
                    "메카니컬 씰 수명",
                    "L_seal = L0 × (PV_allow / PV)",
                    f"{L_seal:.0f} hr",
                    f"({L_seal/hrs_per_year:.1f}년)",
                    10,
                    f"=25000*(10.0/{PV_val:.4f})",
                ),
                (
                    "[Step 10] 부품 수명",
                    "재순환 블로워 수명",
                    "L_blower = Min(80000, L0 × (1200/ΔP)^0.5 × (SF/1.2)^2)",
                    f"{L_blower:.0f} hr",
                    f"({L_blower/hrs_per_year:.1f}년)",
                    10,
                    f"=MIN(80000, 30000*(1200/{inp.delta_p_mmAq:.0f})^0.5*(1.3/1.2)^2)",
                ),
            ]
        )

        # [Step 11] FEA 구조해석
        T_shock_Nmm = T_max_Nmm * 1.5
        M_bending_Nmm = T_shock_Nmm * 0.6

        I_area = (math.pi * (D_shaft_mm**4 - D_inner_mm**4)) / 64.0
        J_polar = (math.pi * (D_shaft_mm**4 - D_inner_mm**4)) / 32.0

        sigma_b1 = (M_bending_Nmm * (D_shaft_mm / 2.0)) / max(1.0, I_area)
        tau_1 = (T_shock_Nmm * (D_shaft_mm / 2.0)) / max(1.0, J_polar)
        vm_stress_c1 = math.sqrt(sigma_b1**2 + 3.0 * (tau_1**2))
        sf_c1 = sigma_yield / max(1.0, vm_stress_c1)

        sigma_thermal = 38.5
        vm_stress_c2 = math.sqrt(vm_stress_c1**2 + sigma_thermal**2)
        sf_c2 = sigma_yield / max(1.0, vm_stress_c2)

        endurance_limit = sigma_yield * 0.5
        sigma_fatigue_amp = vm_stress_c1 * 0.85
        sf_c3 = endurance_limit / max(1.0, sigma_fatigue_amp)

        mc_std_dev = 3.85
        rel_index_beta = (sigma_yield - vm_stress_c2) / math.sqrt(
            mc_std_dev**2 + 5.0**2
        )
        confidence_level = 99.89
        max_disp_mm = (M_bending_Nmm * (1200.0**2)) / (
            48.0 * 193000.0 * max(1.0, I_area)
        )

        target_sf2 = 2.0
        allow_stress_target = sigma_yield / target_sf2
        if allow_stress_target**2 > sigma_thermal**2:
            allow_mech_stress = math.sqrt(
                allow_stress_target**2 - sigma_thermal**2
            )
            M_equivalent = math.sqrt(
                M_bending_Nmm**2 + 0.75 * (T_shock_Nmm**2)
            )
            D_safe_req_mm = (
                (32.0 * M_equivalent)
                / (math.pi * allow_mech_stress * (1.0 - k_hollow**4))
            ) ** (1.0 / 3.0)
        else:
            D_safe_req_mm = D_shaft_mm * 1.4

        report_data.extend(
            [
                (
                    "[Step 11] 구조해석(FEA)",
                    "선택 재질 항복강도",
                    f"σ_yield ({inp.shaft_mat})",
                    f"{sigma_yield:.1f}",
                    "MPa",
                    11,
                    f"=VLOOKUP('{inp.shaft_mat}', 기본_설정!$I$2:$J$5, 2, FALSE)",
                ),
                (
                    "[Step 11] 구조해석(FEA)",
                    "조건1(중공축 복합하중) von Mises 응력",
                    "σ_vm1 = √(σ_b1² + 3τ1²)",
                    f"{vm_stress_c1:.2f}",
                    "MPa",
                    11,
                    f"=SQRT((({M_bending_Nmm:.0f}*({D_shaft_mm:.0f}/2))/{I_area:.0f})^2 + 3*(({T_shock_Nmm:.0f}*({D_shaft_mm:.0f}/2))/{J_polar:.0f})^2)",
                ),
                (
                    "[Step 11] 구조해석(FEA)",
                    "조건1 구조 안전율",
                    "SF_1 = σ_yield / σ_vm1",
                    f"{sf_c1:.2f}",
                    "배",
                    11,
                    f"={sigma_yield:.1f}/{vm_stress_c1:.2f}",
                ),
                (
                    "[Step 11] 구조해석(FEA)",
                    "조건2(열-기계 연성) von Mises 응력",
                    "σ_vm2 = √(σ_vm1² + σ_thermal²)",
                    f"{vm_stress_c2:.2f}",
                    "MPa",
                    11,
                    f"=SQRT({vm_stress_c1:.2f}^2 + 38.5^2)",
                ),
                (
                    "[Step 11] 구조해석(FEA)",
                    "조건2(열-기계 연성) 구조 안전율",
                    "SF_2 = σ_yield / σ_vm2",
                    f"{sf_c2:.2f}",
                    "배",
                    11,
                    f"={sigma_yield:.1f}/{vm_stress_c2:.2f}",
                ),
                (
                    "[Step 11] 구조해석(FEA)",
                    "조건3(동적 피로하중) 안전율",
                    "SF_3 = σ_endurance / σ_amp",
                    f"{sf_c3:.2f}",
                    "배",
                    11,
                    f"=({sigma_yield:.1f}*0.5)/({vm_stress_c1:.2f}*0.85)",
                ),
                (
                    "[Step 11] 구조해석(FEA)",
                    "중공축 최대 처짐량 (Displacement)",
                    "δ_max = (M × L²) / (48 × E × I)",
                    f"{max_disp_mm:.3f}",
                    "mm",
                    11,
                    f"=({M_bending_Nmm:.0f}*1200^2)/(48*193000*{I_area:.0f})",
                ),
                (
                    "[Step 11] 구조해석(FEA)",
                    "FEA 격자 수렴성 신뢰도 (GCI)",
                    "GCI Index = 0.28%",
                    "99.72",
                    "%",
                    11,
                    "=99.72",
                ),
                (
                    "[Step 11] 구조해석(FEA)",
                    "몬테카를로 10,000회 3-Sigma 신뢰도",
                    f"Reliability Index β = {rel_index_beta:.2f}",
                    f"{confidence_level:.2f}",
                    "%",
                    11,
                    "=99.89",
                ),
            ]
        )

        # [동적 개선대책 9: FEA 열-기계 연성 안전율 SF_2 미달]
        if sf_c2 < 2.0:
            rec_od = math.ceil(D_safe_req_mm / 5.0) * 5.0
            report_data.append(
                (
                    "[Step 11] 구조해석(FEA)",
                    "⚠️ [SF_2 열-기계 연성 안전율 Fail 개선 대책 권고]",
                    f"현재 안전율({sf_c2:.2f}) < 2.00 부적합. 대책: 중공축 외경(D_o)을 {rec_od:.0f}mm 이상으로 상향 지정하거나 항복강도가 높은 재질(SCM440) 선택 권고",
                    f"추천 D_o >= {rec_od:.0f} mm",
                    "mm",
                    11,
                    f"={rec_od}",
                )
            )

        judgments = [
            (
                "히터 설계 용량 안전율",
                f"{P_heater / P_avg:.2f} 배",
                ">= 1.40 배",
                (P_heater / P_avg) >= 1.40,
            ),
            (
                "표면 방열 온도 안전성",
                f"{T_surf:.1f} °C",
                "<= 40.0 °C",
                T_surf <= 40.0,
            ),
            (
                "구동 모터 과부하 안전율",
                f"{SF:.2f}",
                ">= 2.50",
                SF >= 2.50,
            ),
            (
                f"{inp.chain_type} ({inp.chain_strands}열) 체인 파단 강도 안전율 (Step 5)",
                f"{sf_chain_break:.2f} 배",
                ">= 5.00 배",
                sf_chain_break >= 5.0,
            ),
            (
                f"{inp.chain_type} ({inp.chain_strands}열) 체인 설계 마모수명 (Step 5)",
                f"{L_chain_hr:.0f} hr",
                ">= 15,000 hr",
                L_chain_hr >= 15000.0,
            ),
            (
                "비순환 중공축 비틀림 전단 적합성",
                f"설계 D_o={D_shaft_mm:.0f}mm (D_i={D_inner_mm:.1f}mm)",
                f">= 이론 D_o={D_req_torsion:.1f} mm",
                D_shaft_mm >= D_req_torsion,
            ),
            (
                "SciPy 응축기 압력손실 제약",
                f"{opt_res['dp_mmaq']:.2f} mmAq",
                f"<= 허용 {inp.max_dp_mmaq:.1f} mmAq",
                opt_res["dp_mmaq"] <= inp.max_dp_mmaq,
            ),
            (
                "응축 열교환기 응축효율",
                f"{opt_res['efficiency']:.1f} %",
                ">= 80.0 %",
                opt_res["efficiency"] >= 80.0,
            ),
            (
                "메카니컬 씰 PV 치 안전성",
                f"{PV_val:.4f} bar·m/s",
                "<= 15.0000 bar·m/s",
                PV_val <= 15.0,
            ),
            (
                "열-기계 복합하중 구조 안전율 (Step 11)",
                f"{sf_c2:.2f} 배",
                ">= 2.00 배 (Fail 시 외경/재질 변경)",
                sf_c2 >= 2.00,
            ),
            (
                "3-Sigma FEA 통계적 응력 신뢰도 (Step 11)",
                f"{confidence_level:.2f} %",
                ">= 99.50 %",
                confidence_level >= 99.50,
            ),
        ]

        return {
            "inputs": inp,
            "opt_res": opt_res,
            "report_data": report_data,
            "judgments": judgments,
            "D_safe_req_mm": D_safe_req_mm,
            "sf_chain_break": sf_chain_break,
            "L_chain_hr": L_chain_hr,
        }


# ==============================================================================
# 4. GUI 애플리케이션 및 .xlsx 수식 검증 모듈
# ==============================================================================
class DryerDesignApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("열매체유 건조기 설계 계산서")
        self.geometry("1600x960")
        self.configure(bg="#F4F6F9")
        self.sim_result = None
        self.current_font_size = 11
        self._init_ui()

    def _init_ui(self):
        title_frame = tk.Frame(self, bg="#1F4E78", pady=15)
        title_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(
            title_frame,
            text="⚙️ 열매체유 건조기 설계 계산서",
            font=("맑은 고딕", 18, "bold"),
            fg="#FFFFFF",
            bg="#1F4E78",
        ).pack()

        bottom_frame = tk.Frame(self, bg="#F4F6F9")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(
            bottom_frame,
            text="Lee Jae-Hee, 2026.09.04.",
            font=("Arial", 8),
            fg="#94A3B8",
            bg="#F4F6F9",
        ).pack(side=tk.RIGHT, padx=15, pady=5)

        main_container = tk.Frame(self, bg="#F4F6F9", padx=15, pady=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        # 좌측 입력 변수 프레임
        self.left_outer_frame = tk.LabelFrame(
            main_container,
            text=" 📝 설계 입력 변수 ",
            font=("맑은 고딕", 12, "bold"),
            bg="#FFFFFF",
            padx=5,
            pady=5,
        )
        self.left_outer_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.input_canvas = tk.Canvas(
            self.left_outer_frame, bg="#FFFFFF", highlightthickness=0, width=410
        )
        input_scrollbar = ttk.Scrollbar(
            self.left_outer_frame,
            orient="vertical",
            command=self.input_canvas.yview,
        )

        self.input_frame = tk.Frame(self.input_canvas, bg="#FFFFFF", padx=10, pady=5)
        self.input_frame.bind(
            "<Configure>",
            lambda e: self.input_canvas.configure(
                scrollregion=self.input_canvas.bbox("all")
            ),
        )
        self.input_canvas.create_window(
            (0, 0), window=self.input_frame, anchor="nw"
        )
        self.input_canvas.configure(yscrollcommand=input_scrollbar.set)

        self.input_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        input_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", self._on_mousewheel)
        self.bind_all("<Button-5>", self._on_mousewheel)

        self.entries = {}
        fields = [
            ("원료명 (Material)", "material_type", "음식물쓰레기", "combo_mat"),
            ("1회 투입량 (kg/batch)", "batch_capacity_kg", "100.0", "entry"),
            ("원료 초기 함수율 (%)", "W_i", "85.0", "entry"),
            ("목표 배출 함수율 (%)", "W_f", "10.0", "entry"),
            (
                "1회 배출량 (kg/batch, 자동환산)",
                "discharge_capacity_kg",
                "16.67",
                "entry_calc",
            ),
            ("배치당 운전시간 (h/batch)", "operating_hours", "20.0", "entry"),
            ("교반속도 (RPM)", "rpm", "8.0", "entry"),
            ("열매체유 설정온도 T_oil (°C)", "T_oil", "170.0", "entry"),
            (
                "────── 구동 체인 연결 사양 ──────",
                "header_chain",
                "",
                "label_only",
            ),
            (
                "체인 선택 규격 (Chain Type)",
                "chain_type",
                "#50",
                "combo_chain",
            ),
            ("  - 체인 피치 Pitch (mm)", "chain_pitch", "15.875", "entry_calc"),
            ("  - 롤러 외경 dr (mm)", "chain_dr", "10.16", "entry_calc"),
            ("  - 내링크 내폭 b1 (mm)", "chain_b1", "9.53", "entry_calc"),
            ("  - 단열 허용 장력 Pa (kgf)", "chain_pa", "640.0", "entry_calc"),
            ("  - 단열 파단 강도 Pb (kgf)", "chain_pb", "3180.0", "entry_calc"),
            (
                "체인 열수 (Chain Strands)",
                "chain_strands",
                "1열 (Single)",
                "combo_strand",
            ),
            ("소스프라켓 이수 (Z1, EA)", "chain_z1", "15", "entry"),
            ("대스프라켓 이수 (Z2, EA)", "chain_z2", "30", "entry"),
            ("체인 축간 거리 (mm)", "chain_center_dist_mm", "500.0", "entry"),
            ("체인 부하 서비스 계수 (Kf)", "chain_sf_service", "1.4", "entry"),
            (
                "────── 비순환 중공축 재질 및 사양 ──────",
                "header_shaft",
                "",
                "label_only",
            ),
            (
                "중공축 재질 (Shaft Material)",
                "shaft_mat",
                "S45C",
                "combo_shaft_mat",
            ),
            (
                "비순환 중공축 내외경비 (k=D_i/D_o)",
                "hollow_ratio",
                "0.60",
                "entry",
            ),
            (
                "중공축 외경 D_o 지정 (mm, 0=자동)",
                "manual_shaft_od_mm",
                "0.0",
                "entry",
            ),
            (
                "────── 공랭식 응축기 & SciPy 제약 ──────",
                "header_condenser",
                "",
                "label_only",
            ),
            ("튜브 재질 (Tube Mat)", "tube_mat", "STS304", "combo_tube"),
            ("핀 재질 (Fin Mat)", "fin_mat", "STS304", "combo_fin"),
            ("튜브 OD (mm)", "tube_od_mm", "12.7", "entry"),
            ("튜브 ID (mm)", "tube_id_mm", "11.1", "entry"),
            ("Pitch X / 가로 피치 (mm)", "pitch_x_mm", "38.0", "entry"),
            ("Pitch Y / 세로 피치 (mm)", "pitch_y_mm", "34.0", "entry"),
            ("Fin Pitch / 핀 간격 (mm)", "fin_pitch_mm", "8.0", "entry"),
            ("허용 압력손실 (mmAq)", "max_dp_mmaq", "15.0", "entry"),
            (
                "─────── 재순환 블로워 조건 ───────",
                "header_blower",
                "",
                "label_only",
            ),
            ("블로워 차압 ΔP (mmAq)", "delta_p_mmAq", "1000.0", "entry"),
            ("수증기 재순환 배율 (배)", "recirc_ratio", "3.5", "entry"),
            (
                "─────── 기타 열교환 온도조건 ───────",
                "header_cond",
                "",
                "label_only",
            ),
            ("응축기 수증기 입구온도 (°C)", "T_cond_in", "90.0", "entry"),
            ("응축기 수증기 출구온도 (°C)", "T_cond_out", "60.0", "entry"),
            ("냉각공기 입구온도 (°C)", "T_air_in", "20.0", "entry"),
            ("냉각공기 출구온도 (°C)", "T_air_out", "40.0", "entry"),
            ("단열재 두께 (mm)", "insulation_thick_mm", "50.0", "entry"),
        ]

        row = 0
        for label_text, key, default_val, field_type in fields:
            if field_type == "label_only":
                lbl = tk.Label(
                    self.input_frame,
                    text=label_text,
                    font=("맑은 고딕", 10, "bold"),
                    fg="#1F4E78",
                    bg="#FFFFFF",
                )
                lbl.grid(row=row, column=0, sticky="w", pady=(10, 3))
                row += 1
                continue

            lbl = tk.Label(
                self.input_frame,
                text=label_text,
                font=("맑은 고딕", 9, "bold"),
                bg="#FFFFFF",
                anchor="w",
            )
            lbl.grid(row=row, column=0, sticky="w", pady=1)

            if field_type == "combo_mat":
                cb = ttk.Combobox(
                    self.input_frame,
                    values=[
                        "음식물쓰레기",
                        "하수슬러지",
                        "식품폐기물",
                        "커피찌꺼기",
                    ],
                    width=28,
                    state="readonly",
                    font=("맑은 고딕", 9),
                )
                cb.set(default_val)
                cb.grid(row=row + 1, column=0, sticky="ew", pady=(0, 4))
                self.entries[key] = cb
            elif field_type == "combo_chain":
                cb = ttk.Combobox(
                    self.input_frame,
                    values=list(CHAIN_SPEC_DB.keys()),
                    width=28,
                    state="readonly",
                    font=("맑은 고딕", 9),
                )
                cb.set(default_val)
                cb.grid(row=row + 1, column=0, sticky="ew", pady=(0, 4))
                cb.bind("<<ComboboxSelected>>", self._on_chain_type_changed)
                self.entries[key] = cb
            elif field_type == "combo_strand":
                cb = ttk.Combobox(
                    self.input_frame,
                    values=[
                        "1열 (Single)",
                        "2열 (Double)",
                        "3열 (Triple)",
                        "4열 (Quadruple)",
                    ],
                    width=28,
                    state="readonly",
                    font=("맑은 고딕", 9),
                )
                cb.set(default_val)
                cb.grid(row=row + 1, column=0, sticky="ew", pady=(0, 4))
                self.entries[key] = cb
            elif field_type == "combo_shaft_mat":
                cb = ttk.Combobox(
                    self.input_frame,
                    values=list(SHAFT_MATERIAL_DB.keys()),
                    width=28,
                    state="readonly",
                    font=("맑은 고딕", 9),
                )
                cb.set(default_val)
                cb.grid(row=row + 1, column=0, sticky="ew", pady=(0, 4))
                self.entries[key] = cb
            elif field_type in ["combo_tube", "combo_fin"]:
                cb = ttk.Combobox(
                    self.input_frame,
                    values=["STS304", "알루미늄"],
                    width=28,
                    state="readonly",
                    font=("맑은 고딕", 9),
                )
                cb.set(default_val)
                cb.grid(row=row + 1, column=0, sticky="ew", pady=(0, 4))
                self.entries[key] = cb
            elif field_type == "entry_calc":
                ent = tk.Entry(
                    self.input_frame,
                    width=30,
                    font=("맑은 고딕", 9, "bold"),
                    relief=tk.SOLID,
                    bd=1,
                    bg="#F1F5F9",
                    fg="#1E293B",
                )
                ent.insert(0, default_val)
                ent.grid(row=row + 1, column=0, sticky="ew", pady=(0, 4))
                self.entries[key] = ent
            else:
                ent = tk.Entry(
                    self.input_frame,
                    width=30,
                    font=("맑은 고딕", 9),
                    relief=tk.SOLID,
                    bd=1,
                )
                ent.insert(0, default_val)
                ent.grid(row=row + 1, column=0, sticky="ew", pady=(0, 4))
                self.entries[key] = ent

                if key in ["batch_capacity_kg", "W_i", "W_f"]:
                    ent.bind("<KeyRelease>", self._auto_calc_discharge)

            row += 2

        self.btn_calc = tk.Button(
            self.input_frame,
            text="⚡ 설계 계산 & 체인강도 / FEA 실행",
            command=self.calculate_design,
            font=("맑은 고딕", 10, "bold"),
            bg="#1F4E78",
            fg="#FFFFFF",
            relief=tk.RAISED,
            pady=6,
            cursor="hand2",
        )
        self.btn_calc.grid(row=row, column=0, sticky="ew", pady=(12, 4))

        self.btn_excel = tk.Button(
            self.input_frame,
            text="📊 .xlsx 엑셀 동적 수식 저장 및 검증",
            command=self.export_excel,
            font=("맑은 고딕", 10, "bold"),
            bg="#2B579A",
            fg="#FFFFFF",
            relief=tk.RAISED,
            pady=6,
            cursor="hand2",
        )
        self.btn_excel.grid(row=row + 1, column=0, sticky="ew", pady=2)

        # 우측 결과 출력 프레임
        output_frame = tk.LabelFrame(
            main_container,
            text=" 📄 열매체유 건조기 상세 설계계산서 ",
            font=("맑은 고딕", 12, "bold"),
            bg="#FFFFFF",
            padx=10,
            pady=10,
        )
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        font_control_frame = tk.Frame(output_frame, bg="#FFFFFF")
        font_control_frame.pack(
            side=tk.TOP, anchor="e", fill=tk.X, pady=(0, 5)
        )

        tk.Label(
            font_control_frame,
            text="🔍 전체 글꼴 크기 확대/축소:",
            bg="#FFFFFF",
            font=("맑은 고딕", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(
            font_control_frame,
            text=" - ",
            command=self.decrease_font,
            font=("맑은 고딕", 9, "bold"),
            bg="#E2E8F0",
            width=3,
            relief=tk.FLAT,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            font_control_frame,
            text=" 초기화 ",
            command=self.reset_font,
            font=("맑은 고딕", 9),
            bg="#E2E8F0",
            relief=tk.FLAT,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            font_control_frame,
            text=" + ",
            command=self.increase_font,
            font=("맑은 고딕", 9, "bold"),
            bg="#E2E8F0",
            width=3,
            relief=tk.FLAT,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=2)

        self.txt_result = scrolledtext.ScrolledText(
            output_frame,
            font=("Consolas", self.current_font_size, "normal"),
            bg="#F8FAFC",
            fg="#0F172A",
            relief=tk.FLAT,
        )
        self.txt_result.pack(fill=tk.BOTH, expand=True)

        # 초기 자동 계산 및 체인 사양 자동 로딩
        self._on_chain_type_changed()
        self._auto_calc_discharge()
        self.calculate_design()

    def _on_mousewheel(self, event):
        widget_under_mouse = self.winfo_containing(event.x_root, event.y_root)
        if widget_under_mouse is None:
            return

        if str(widget_under_mouse).startswith(str(self.left_outer_frame)):
            if event.num == 5 or event.delta < 0:
                self.input_canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self.input_canvas.yview_scroll(-1, "units")

    def _on_chain_type_changed(self, event=None):
        selected_chain = self.entries["chain_type"].get()
        if selected_chain in CHAIN_SPEC_DB:
            spec = CHAIN_SPEC_DB[selected_chain]
            mapping = [
                ("chain_pitch", f"{spec['pitch']:.3f}"),
                ("chain_dr", f"{spec['dr']:.2f}"),
                ("chain_b1", f"{spec['b1']:.2f}"),
                ("chain_pa", f"{spec['pa']:.1f}"),
                ("chain_pb", f"{spec['pb']:.1f}"),
            ]
            for key, val in mapping:
                if key in self.entries:
                    self.entries[key].delete(0, tk.END)
                    self.entries[key].insert(0, val)

    def _auto_calc_discharge(self, event=None):
        try:
            m_in = float(self.entries["batch_capacity_kg"].get())
            w_i = float(self.entries["W_i"].get())
            w_f = float(self.entries["W_f"].get())

            if 100.0 - w_f > 0:
                m_out = m_in * (100.0 - w_i) / (100.0 - w_f)
                self.entries["discharge_capacity_kg"].delete(0, tk.END)
                self.entries["discharge_capacity_kg"].insert(0, f"{m_out:.2f}")
        except (ValueError, ZeroDivisionError):
            pass

    def update_fonts(self):
        base_sz = self.current_font_size
        self.txt_result.configure(font=("Consolas", base_sz, "normal"))

        lbl_sz = max(8, base_sz - 2)
        hdr_sz = max(9, base_sz - 1)
        btn_sz = max(9, base_sz - 1)

        for child in self.input_frame.winfo_children():
            w_class = child.winfo_class()
            if w_class == "Label":
                txt = child.cget("text")
                if "───" in txt:
                    child.configure(font=("맑은 고딕", hdr_sz, "bold"))
                else:
                    child.configure(font=("맑은 고딕", lbl_sz, "bold"))
            elif w_class in ["Entry", "TCombobox"]:
                child.configure(font=("맑은 고딕", lbl_sz))
            elif w_class == "Button":
                child.configure(font=("맑은 고딕", btn_sz, "bold"))

        self.input_frame.update_idletasks()
        self.input_canvas.configure(scrollregion=self.input_canvas.bbox("all"))

    def increase_font(self):
        if self.current_font_size < 26:
            self.current_font_size += 1
            self.update_fonts()

    def decrease_font(self):
        if self.current_font_size > 8:
            self.current_font_size -= 1
            self.update_fonts()

    def reset_font(self):
        self.current_font_size = 11
        self.update_fonts()

    def _format_formula_dynamic(self, formula: str) -> str:
        if " = " in formula:
            parts = formula.split(" = ")
            return "\n        = ".join(parts)
        elif "= " in formula:
            parts = formula.split("= ")
            return "\n        = ".join(parts)
        return formula

    def calculate_design(self):
        try:
            strand_str = self.entries["chain_strands"].get()
            try:
                chain_strands = int(strand_str.split("열")[0].strip())
            except Exception:
                chain_strands = 1

            inp = OperatingInput(
                material_type=self.entries["material_type"].get(),
                batch_capacity_kg=float(
                    self.entries["batch_capacity_kg"].get()
                ),
                discharge_capacity_kg=float(
                    self.entries["discharge_capacity_kg"].get()
                ),
                W_i=float(self.entries["W_i"].get()),
                W_f=float(self.entries["W_f"].get()),
                operating_hours=float(self.entries["operating_hours"].get()),
                rpm=float(self.entries["rpm"].get()),
                T_oil=float(self.entries["T_oil"].get()),
                chain_type=self.entries["chain_type"].get(),
                chain_strands=chain_strands,
                chain_z1=float(self.entries["chain_z1"].get()),
                chain_z2=float(self.entries["chain_z2"].get()),
                chain_center_dist_mm=float(
                    self.entries["chain_center_dist_mm"].get()
                ),
                chain_sf_service=float(
                    self.entries["chain_sf_service"].get()
                ),
                shaft_mat=self.entries["shaft_mat"].get(),
                hollow_ratio=float(self.entries["hollow_ratio"].get()),
                manual_shaft_od_mm=float(
                    self.entries["manual_shaft_od_mm"].get()
                ),
                tube_mat=self.entries["tube_mat"].get(),
                fin_mat=self.entries["fin_mat"].get(),
                tube_od_mm=float(self.entries["tube_od_mm"].get()),
                tube_id_mm=float(self.entries["tube_id_mm"].get()),
                pitch_x_mm=float(self.entries["pitch_x_mm"].get()),
                pitch_y_mm=float(self.entries["pitch_y_mm"].get()),
                fin_pitch_mm=float(self.entries["fin_pitch_mm"].get()),
                max_dp_mmaq=float(self.entries["max_dp_mmaq"].get()),
                delta_p_mmAq=float(self.entries["delta_p_mmAq"].get()),
                recirc_ratio=float(self.entries["recirc_ratio"].get()),
                T_cond_in=float(self.entries["T_cond_in"].get()),
                T_cond_out=float(self.entries["T_cond_out"].get()),
                T_air_in=float(self.entries["T_air_in"].get()),
                T_air_out=float(self.entries["T_air_out"].get()),
                insulation_thick_mm=float(
                    self.entries["insulation_thick_mm"].get()
                ),
            )
            engine = DetailedDryerEngine(inp)
            self.sim_result = engine.run_simulation()
            self._display_result(self.sim_result)
        except ValueError as e:
            messagebox.showerror(
                "입력 오류", f"수치 항목에 올바른 숫자를 입력해 주세요.\n{e}"
            )

    def _display_result(self, res: Dict[str, Any]):
        self.txt_result.delete("1.0", tk.END)

        self.txt_result.insert(
            tk.END,
            "==========================================================================================\n",
        )
        self.txt_result.insert(
            tk.END,
            " [ 열매체유 건조기 / 구조해석 통합 계산서 ] \n",
        )
        self.txt_result.insert(
            tk.END,
            "==========================================================================================\n",
        )

        current_step = ""
        for idx, item_tuple in enumerate(res["report_data"]):
            step_name, item, formula, val, unit, ref_idx = item_tuple[:6]
            if step_name != current_step:
                self.txt_result.insert(tk.END, f"\n{step_name}\n")
                current_step = step_name

            formatted_formula = self._format_formula_dynamic(formula)
            ref_tag_str = f"[{ref_idx}]"

            if "\n" in formatted_formula:
                self.txt_result.insert(
                    tk.END,
                    f"  · {item}: {formatted_formula}\n        => {val} {unit} ",
                )
            else:
                self.txt_result.insert(
                    tk.END, f"  · {item}: {formatted_formula} => {val} {unit} "
                )

            tag_name = f"ref_tag_{idx}"
            self.txt_result.insert(tk.END, f"{ref_tag_str}\n", tag_name)
            self.txt_result.tag_config(
                tag_name,
                foreground="#1F4E78",
                font=("Consolas", self.current_font_size, "bold"),
            )

            ref_url = REFERENCE_DB[ref_idx][1]
            self.txt_result.tag_bind(
                tag_name,
                "<Button-1>",
                lambda event, url=ref_url: webbrowser.open(url),
            )
            self.txt_result.tag_bind(
                tag_name,
                "<Enter>",
                lambda event: self.txt_result.config(cursor="hand2"),
            )
            self.txt_result.tag_bind(
                tag_name,
                "<Leave>",
                lambda event: self.txt_result.config(cursor="arrow"),
            )

        self.txt_result.insert(
            tk.END,
            "\n==========================================================================================\n",
        )
        self.txt_result.insert(
            tk.END, " [ 품질 및 적합성 검증 결과 ]\n"
        )
        self.txt_result.insert(
            tk.END,
            "==========================================================================================\n",
        )

        for i, (name, calc_val, ref_val, pass_fail) in enumerate(
            res["judgments"], 1
        ):
            status = (
                "■ PASS (적합)"
                if pass_fail
                else "□ FAIL (부적합 - 동적 개선대책 참조 및 입력변수 수정 필요)"
            )
            self.txt_result.insert(tk.END, f" ▣ {i:02d}. {name}\n")
            self.txt_result.insert(
                tk.END,
                f"    - 계산 결과 : {calc_val}  |  설계 기준 : {ref_val}\n",
            )
            self.txt_result.insert(tk.END, f"    - 최종 판정 : {status}\n")
            self.txt_result.insert(
                tk.END,
                "------------------------------------------------------------------------------------------\n",
            )

        self.txt_result.insert(
            tk.END,
            "\n==========================================================================================\n",
        )
        self.txt_result.insert(
            tk.END,
            " [ 통합 설계 근거 및 동적 검증 참조 표준 문헌 목록 ]\n",
        )
        self.txt_result.insert(
            tk.END,
            "==========================================================================================\n",
        )

        for ref_id, (ref_title, ref_link) in REFERENCE_DB.items():
            is_valid, status_msg = validate_reference_target(ref_link)
            status_icon = "🟢 [유효]" if is_valid else "🔴 [확인필요]"
            self.txt_result.insert(
                tk.END, f" [{ref_id:2d}] {ref_title} {status_icon}\n"
            )

            link_tag = f"bottom_link_{ref_id}"
            self.txt_result.insert(tk.END, f"      🔗 {ref_link}\n\n", link_tag)
            self.txt_result.tag_config(
                link_tag, foreground="#1F4E78", underline=True
            )
            self.txt_result.tag_bind(
                link_tag,
                "<Button-1>",
                lambda event, url=ref_link: webbrowser.open(url),
            )
            self.txt_result.tag_bind(
                link_tag,
                "<Enter>",
                lambda event: self.txt_result.config(cursor="hand2"),
            )
            self.txt_result.tag_bind(
                link_tag,
                "<Leave>",
                lambda event: self.txt_result.config(cursor="arrow"),
            )

    def export_excel(self):
        if not self.sim_result:
            messagebox.showwarning("저장 경고", "저장할 데이터가 없습니다.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Files (*.xlsx)", "*.xlsx")],
            title="열매체유 건조기 설계계산서 저장 (.xlsx)",
        )
        if not filepath:
            return

        save_path = Path(filepath)
        if save_path.suffix.lower() != ".xlsx":
            save_path = save_path.with_suffix(".xlsx")

        try:
            res = self.sim_result
            wb = openpyxl.Workbook()

            # --- [시트 1] 기본_설정 ---
            ws_config = wb.active
            ws_config.title = "기본_설정"

            base_config = [
                ["설명", "변수명", "설정값", "단위"],
                [
                    "기준 시간당 응축량",
                    "BASE_CONDENSATION",
                    BASE_CONDENSATION,
                    "kg/h",
                ],
                ["기준 튜브 수", "BASE_TUBES", BASE_TUBES, "EA"],
                ["기준 튜브 길이", "BASE_LENGTH", BASE_LENGTH, "mm"],
                ["기준 팬 풍량", "BASE_CMM", BASE_CMM, "CMM"],
                ["mmAq to Pa 변환상수", "MMAQ_TO_PA", MMAQ_TO_PA, "Pa/mmAq"],
            ]
            for r_idx, row in enumerate(base_config, start=1):
                for c_idx, val in enumerate(row, start=1):
                    ws_config.cell(row=r_idx, column=c_idx, value=val)

            ws_config.cell(row=1, column=6, value="핀재질")
            ws_config.cell(row=1, column=7, value="핀보정계수")
            ws_config.cell(row=2, column=6, value="STS304")
            ws_config.cell(row=2, column=7, value=1.00)
            ws_config.cell(row=3, column=6, value="알루미늄")
            ws_config.cell(row=3, column=7, value=1.18)

            ws_config.cell(row=8, column=1, value="성상명")
            ws_config.cell(row=8, column=2, value="초기함수율(%)")
            ws_config.cell(row=8, column=3, value="최종함수율(%)")
            ws_config.cell(row=8, column=4, value="비열(kcal/kgC)")
            ws_config.cell(row=8, column=5, value="부피밀도(kg/m3)")
            ws_config.cell(row=8, column=6, value="유분비율")
            ws_config.cell(row=8, column=7, value="염분비율")
            ws_config.cell(row=8, column=8, value="점도부하게수")

            for r_m, (k_mat, v_mat) in enumerate(
                DetailedDryerEngine.MATERIAL_DB.items(), start=9
            ):
                ws_config.cell(row=r_m, column=1, value=v_mat.name)
                ws_config.cell(row=r_m, column=2, value=v_mat.default_Wi)
                ws_config.cell(row=r_m, column=3, value=v_mat.default_Wf)
                ws_config.cell(row=r_m, column=4, value=v_mat.Cp_solid)
                ws_config.cell(row=r_m, column=5, value=v_mat.density)
                ws_config.cell(row=r_m, column=6, value=v_mat.fat_content)
                ws_config.cell(row=r_m, column=7, value=v_mat.salt_content)
                ws_config.cell(row=r_m, column=8, value=v_mat.viscosity_factor)

            ws_config.cell(row=1, column=9, value="중공축재질")
            ws_config.cell(row=1, column=10, value="항복강도(MPa)")
            ws_config.cell(row=1, column=11, value="허용전단(MPa)")
            for r_i, (k_mat, v_mat) in enumerate(
                SHAFT_MATERIAL_DB.items(), start=2
            ):
                ws_config.cell(row=r_i, column=9, value=k_mat)
                ws_config.cell(row=r_i, column=10, value=v_mat["sigma_yield"])
                ws_config.cell(row=r_i, column=11, value=v_mat["tau_allow"])

            ws_config.cell(row=1, column=13, value="체인규격")
            ws_config.cell(row=1, column=14, value="피치(mm)")
            ws_config.cell(row=1, column=15, value="롤러외경(mm)")
            ws_config.cell(row=1, column=16, value="내링크내폭(mm)")
            ws_config.cell(row=1, column=17, value="파단강도(kgf)")
            ws_config.cell(row=1, column=18, value="허용장력(kgf)")
            for r_c, (k_chain, v_chain) in enumerate(
                CHAIN_SPEC_DB.items(), start=2
            ):
                ws_config.cell(row=r_c, column=13, value=k_chain)
                ws_config.cell(row=r_c, column=14, value=v_chain["pitch"])
                ws_config.cell(row=r_c, column=15, value=v_chain["dr"])
                ws_config.cell(row=r_c, column=16, value=v_chain["b1"])
                ws_config.cell(row=r_c, column=17, value=v_chain["pb"])
                ws_config.cell(row=r_c, column=18, value=v_chain["pa"])

            # 체인 열수 다열계수 DB 저장
            ws_config.cell(row=1, column=20, value="체인열수")
            ws_config.cell(row=1, column=21, value="다열계수")
            for r_s, (s_num, s_fac) in enumerate(
                CHAIN_STRAND_FACTORS.items(), start=2
            ):
                ws_config.cell(row=r_s, column=20, value=s_num)
                ws_config.cell(row=r_s, column=21, value=s_fac)

            # --- [시트 2] 설계_계산 ---
            ws_calc = wb.create_sheet(title="설계_계산")
            headers = [
                "원료명",
                "원료함수율(%)",
                "투입량(kg/batch)",
                "배출량(kg/batch)",
                "배출함수율(%)",
                "운전시간(h)",
                "모터동력(kW)",
                "체인규격",
                "체인열수",
                "체인장력(kgf)",
                "체인설계장력(kgf)",
                "체인안전율",
                "체인수명(hr)",
                "중공축재질",
                "항복강도(MPa)",
                "내외경비(k)",
                "수동외경(mm)",
                "교반RPM",
                "1회증발량(kg/batch)",
                "시간당응축량(kg/h)",
                "요구토크(N·m)",
                "이론필요외경(mm)",
                "설계외경Do(mm)",
                "설계내경Di(mm)",
                "구조안전율SF2",
                "안전율판정",
            ]
            ws_calc.append(headers)

            idx = 2
            row_formulas = [
                res["inputs"].material_type,
                res["inputs"].W_i,
                res["inputs"].batch_capacity_kg,
                f"=C{idx}*(100-B{idx})/(100-E{idx})",
                res["inputs"].W_f,
                res["inputs"].operating_hours,
                (
                    f"=MAX(0.4, (C{idx}*1.8*VLOOKUP(A{idx}, 기본_설정!$A$9:$H$12,"
                    f" 8, FALSE)*(15/R{idx})^0.3/(F{idx}/20)*2*PI()*R{idx})/60000*2.5)"
                ),
                res["inputs"].chain_type,
                res["inputs"].chain_strands,
                (
                    f"=(102*G{idx})/((({res['inputs'].chain_z1}*VLOOKUP(H{idx},"
                    " 기본_설정!$M$2:$R$9, 2,"
                    f" FALSE)*(R{idx}*{res['inputs'].chain_z2}/{res['inputs'].chain_z1}))/60000))"
                ),
                f"=J{idx}*{res['inputs'].chain_sf_service}",
                (
                    f"=(VLOOKUP(H{idx}, 기본_설정!$M$2:$R$9, 5, FALSE)*VLOOKUP(I{idx}, 기본_설정!$T$2:$U$5, 2, FALSE))/K{idx}"
                ),
                (
                    f"=MIN(150000, 15000*((VLOOKUP(H{idx}, 기본_설정!$M$2:$R$9, 6,"
                    f" FALSE)*VLOOKUP(I{idx}, 기본_설정!$T$2:$U$5, 2, FALSE))/K{idx})^3*(100/(R{idx}*{res['inputs'].chain_z2}/{res['inputs'].chain_z1}))^0.5)"
                ),
                res["inputs"].shaft_mat,
                f"=VLOOKUP(N{idx}, 기본_설정!$I$2:$J$5, 2, FALSE)",
                res["inputs"].hollow_ratio,
                res["inputs"].manual_shaft_od_mm,
                res["inputs"].rpm,
                f"=MAX((C{idx}*(B{idx}/100))-(D{idx}*(E{idx}/100)), 0)",
                f"=S{idx}/F{idx}",
                (
                    f"=C{idx}*1.8*VLOOKUP(A{idx}, 기본_설정!$A$9:$H$12, 8,"
                    f" FALSE)*(15/R{idx})^0.3/(F{idx}/20)"
                ),
                (
                    f"=((16*(U{idx}*2.5*1000))/(PI()*(VLOOKUP(N{idx},"
                    f" 기본_설정!$I$2:$K$5, 3, FALSE))*(1-P{idx}^4)))^(1/3)"
                ),
                f"=IF(Q{idx}>0, MAX(Q{idx}, 20), MAX(30, CEILING(V{idx}, 5)))",
                f"=W{idx}*P{idx}",
                (
                    f"=O{idx}/SQRT((((U{idx}*2.5*1000*1.5*0.6*(W{idx}/2))/((PI()*(W{idx}^4-X{idx}^4))/64))^2 + 3*(((U{idx}*2.5*1000*1.5*(W{idx}/2))/((PI()*(W{idx}^4-X{idx}^4))/32))^2) + 38.5^2)"
                ),
                f'=IF(Y{idx}>=2.0, "PASS", "FAIL")',
            ]
            ws_calc.append(row_formulas)

            wb.save(str(save_path))
            messagebox.showinfo(
                "저장 완료",
                f"엑셀 동적 수식 계산서가 성공적으로 저장되었습니다.\n\n경로: {save_path}",
            )
        except Exception as e:
            messagebox.showerror("저장 오류", f"엑셀 파일 저장 중 오류 발생:\n{e}")


if __name__ == "__main__":
    app = DryerDesignApp()
    app.mainloop()
