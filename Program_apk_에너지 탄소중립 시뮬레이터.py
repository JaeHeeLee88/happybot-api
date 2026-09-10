import os
import sys
import platform
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib import rc
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# =====================================
# PyInstaller exe 경로 해소 및 폰트 자동 등록
# =====================================

def get_resource_path(relative_path):
    """ PyInstaller exe 실행 시 임시 폴더(sys._MEIPASS) 및 일반 파일 경로를 자동 추적 """
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def init_korean_font():
    """ 어디서든 한글 폰트가 깨지지 않도록 강제 등록 및 설정 """
    font_name = None
    
    # 검색할 폰트 경로 우선순위
    font_candidates = [
        get_resource_path(os.path.join('fonts', 'malgun.ttf')),
        get_resource_path(os.path.join('fonts', 'NanumGothic.ttf')),
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/gulim.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    ]
    
    for path in font_candidates:
        if os.path.exists(path):
            try:
                fm.fontManager.addfont(path)
                font_name = fm.FontProperties(fname=path).get_name()
                break
            except Exception:
                continue

    if font_name:
        plt.rcParams['font.family'] = font_name
        rc('font', family=font_name)
    else:
        font_name = 'Malgun Gothic' if platform.system() == "Windows" else 'AppleGothic'
        plt.rcParams['font.family'] = font_name
        rc('font', family=font_name)

    plt.rcParams['axes.unicode_minus'] = False
    return font_name

# 한글 폰트 초기화 실행
font_family_base = init_korean_font()

# =====================================
# 연도별 데이터셋 (최신/과거 기준 연도 관리)
# =====================================

ENERGY_DATA_BY_YEAR = {
    "2025~2026년 최신 통계 (KEEI/KESIS/GIR 최신자료)": {
        "data_year": "2025~2026년",
        "country_energy": {
            "대한민국": 5240,  # KESIS / IEA 최신 반영
            "일본": 2880,
            "독일": 2650,
            "중국": 3120,
            "인도": 890,
            "캐나다": 6950,
            "미국": 6420
        },
        "region_factor": {
            "도시": 1.12,
            "산업지역": 1.35,
            "농촌": 0.82,
            "해안지역": 1.03
        },
        "age_factor": {
            "0~19세": 0.72,
            "20~39세": 0.88,
            "40~64세": 1.22,
            "65세 이상": 1.08
        },
        "job_factor": {
            "학생": 0.68,
            "사무직": 1.00,
            "IT직군": 1.10,
            "제조업": 1.65,
            "건설업": 1.48,
            "운수업": 1.85,
            "농림어업": 1.28,
            "무직": 0.88
        },
        "sources_note": "KESIS 국가에너지통계포털(2025) / GIR 국가 배출계수(2024~2025) / 국립산림과학원(2024)"
    },
    "2018~2020년 과거 통계 (기존 Benchmark 데이터)": {
        "data_year": "2018~2020년",
        "country_energy": {
            "대한민국": 5439,
            "일본": 3006,
            "독일": 2825,
            "중국": 2851,
            "인도": 763,
            "캐나다": 7161,
            "미국": 6800
        },
        "region_factor": {
            "도시": 1.10,
            "산업지역": 1.30,
            "농촌": 0.85,
            "해안지역": 1.05
        },
        "age_factor": {
            "0~19세": 0.75,
            "20~39세": 0.90,
            "40~64세": 1.20,
            "65세 이상": 1.05
        },
        "job_factor": {
            "학생": 0.70,
            "사무직": 1.00,
            "IT직군": 1.05,
            "제조업": 1.60,
            "건설업": 1.50,
            "운수업": 1.80,
            "농림어업": 1.30,
            "무직": 0.90
        },
        "sources_note": "World Bank / 에너지경제연구원 에너지총조사(2017~2020)"
    }
}

# =====================================
# 검증된 계산근거 세부 URL 목록
# =====================================

data_sources = {
    "KESIS 국가에너지통계포털 (최신 지역/용도별 소비 가중치)": "https://kesis.keei.re.kr",
    "GIR 온실가스종합정보센터 (2024~2025 최신 국가 온실가스 배출계수)": "https://www.gir.go.kr/home/index.do?menuId=36",
    "Our World in Data (글로벌 1인당 에너지 소비 최신 통계)": "https://ourworldindata.org/per-capita-energy",
    "IEA Data and Statistics (국제에너지기구 최신 데이터)": "https://www.iea.org/data-and-statistics",
    "IPCC EFDB (국제 온실가스 배출계수 DB 검색)": "https://www.ipcc-nggip.iges.or.jp/EFDB/find_ef.php",
    "한국에너지공단 (석유환산톤/열량 환산 최신 기준표)": "https://www.energy.or.kr/web/kem_home_new/energy_issue/data/conversion/energy_conversion.asp",
    "한국지역난방공사 (열요금 단가 및 최신 계산 기준)": "https://www.kdhc.or.kr/content.do?method=content&cd=020101",
    "에너지경제연구원 (에너지총조사 보고서 및 데이터)": "https://www.keei.re.kr/main.nsf/index.html?open&p=board/RD_KEEI_01",
    "국립산림과학원 (주요 수종별 탄소흡수량 표준)": "https://nifos.forest.go.kr/kfsweb/cop/bbs/selectBoardList.do?bbsId=BBSMSTR_1037&mn=NKFS_04_02_01"
}

def open_selected_url():
    selected_name = source_var.get()
    if selected_name in data_sources:
        webbrowser.open_new(data_sources[selected_name])
    else:
        messagebox.showwarning("알림", "이동할 출처 사이트를 선택해 주세요.")

# =====================================
# 연산 및 가중치 반영 산출 함수
# =====================================

latest_results = []

def compute_metrics(year_key, country, region, age, job, population, renewable_ratio):
    dataset = ENERGY_DATA_BY_YEAR[year_key]
    data_year_str = dataset["data_year"]

    base_energy = dataset["country_energy"][country]
    w_region = dataset["region_factor"][region]
    w_age = dataset["age_factor"][age]
    w_job = dataset["job_factor"][job]

    combined_weight = w_region * w_age * w_job
    per_capita_weighted = base_energy * combined_weight
    total_kgOE = per_capita_weighted * population

    total_toe = total_kgOE / 1000.0
    total_gcal = total_kgOE / 100.0
    total_mcal = total_kgOE * 10.0
    total_gj = total_kgOE * 0.041868

    total_kwh = total_kgOE * 11.63
    total_mwh = total_kwh / 1000.0

    renewable_kwh = total_kwh * (renewable_ratio / 100)
    fossil_kwh = total_kwh - renewable_kwh

    fossil_oil_kwh = fossil_kwh * 0.40
    fossil_coal_kwh = fossil_kwh * 0.35
    fossil_gas_kwh = fossil_kwh * 0.25

    oil_liter = fossil_oil_kwh / 10
    coal_kg = fossil_coal_kwh / 6.7
    gas_m3 = fossil_gas_kwh / 10.5

    co2_oil = oil_liter * 2.31
    co2_coal = coal_kg * 2.42
    co2_gas = gas_m3 * 2.0

    total_co2_kg = co2_oil + co2_coal + co2_gas
    total_co2_ton = total_co2_kg / 1000.0

    solar_panels = renewable_kwh / 800
    smartphone_charge = total_kwh / 0.015
    ev_distance = total_kwh / 0.15
    trees = total_co2_kg / 22

    return {
        "data_year": data_year_str,
        "sources_note": dataset["sources_note"],
        "inputs": {
            "country": country, "region": region, "age": age,
            "job": job, "pop": population, "renewable": renewable_ratio,
            "base_energy": base_energy
        },
        "weights": {
            "w_region": w_region,
            "w_age": w_age,
            "w_job": w_job,
            "combined": combined_weight,
            "per_capita": per_capita_weighted
        },
        "kgOE": total_kgOE,
        "toe": total_toe,
        "gcal": total_gcal,
        "mcal": total_mcal,
        "gj": total_gj,
        "kwh": total_kwh,
        "mwh": total_mwh,
        "renewable_kwh": renewable_kwh,
        "fossil_kwh": fossil_kwh,
        "oil_liter": oil_liter,
        "coal_kg": coal_kg,
        "gas_m3": gas_m3,
        "co2_oil": co2_oil,
        "co2_coal": co2_coal,
        "co2_gas": co2_gas,
        "co2_kg": total_co2_kg,
        "co2_ton": total_co2_ton,
        "trees": trees,
        "solar": solar_panels,
        "ev": ev_distance,
        "phone": smartphone_charge
    }

# =====================================
# 상세 계산과정 팝업 창
# =====================================

def show_detail_window(index):
    if not latest_results or index >= len(latest_results):
        messagebox.showinfo("알림", "먼저 시뮬레이션을 실행해 주세요.")
        return

    res = latest_results[index]
    inp = res["inputs"]
    w = res["weights"]

    detail_win = tk.Toplevel(root)
    detail_win.title(f"조건 {index + 1} 가중치 연산 및 상세 계산과정 ({res['data_year']} 기준)")
    detail_win.geometry("740x760")

    frame = ttk.Frame(detail_win, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL)
    txt = tk.Text(frame, font=font_mono, yscrollcommand=scrollbar.set)
    scrollbar.config(command=txt.yview)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    proc_str = f"===========================================================\n"
    proc_str += f"   [조건 {index + 1}] 가중치 연산 및 상세 계산과정 ({res['data_year']})\n"
    proc_str += f"   - 데이터 출처: {res['sources_note']}\n"
    proc_str += f"===========================================================\n\n"

    proc_str += f"1. 입력 조건 및 기준 데이터 ({res['data_year']} 통계)\n"
    proc_str += f" - 국가 : {inp['country']} (기초 1인당 소비량: {inp['base_energy']:,} kgOE/년)\n"
    proc_str += f" - 지역 : {inp['region']}  |  연령 : {inp['age']}  |  직업 : {inp['job']}\n"
    proc_str += f" - 적용 인구 : {inp['pop']:,} 명  |  재생에너지 목표 비율 : {inp['renewable']}%\n\n"

    proc_str += f"2. 입력 조건별 가중치(Weight Factors) 상세 산출\n"
    proc_str += f" - [지역 가중치] {inp['region']}   : {w['w_region']:.2f} (근거: KESIS 국가에너지통계)\n"
    proc_str += f" - [연령 가중치] {inp['age']}   : {w['w_age']:.2f} (근거: 에너지총조사 연령별 계수)\n"
    proc_str += f" - [직업 가중치] {inp['job']} : {w['w_job']:.2f} (근거: KEEI 산업계수)\n"
    proc_str += f" -----------------------------------------------------------\n"
    proc_str += f" - [통합 가중치] W_total = {w['w_region']:.2f} × {w['w_age']:.2f} × {w['w_job']:.2f} = {w['combined']:.4f}\n"
    proc_str += f" - [1인당 가중 소비량] {inp['base_energy']:,} kgOE × {w['combined']:.4f} = {w['per_capita']:,.2f} kgOE/인\n"
    proc_str += f" - [총 1차 에너지 소비량] {w['per_capita']:,.2f} kgOE × {inp['pop']}명 = {res['kgOE']:,.2f} kgOE\n"
    proc_str += f" ☞ 석유환산톤(TOE) : {res['toe']:,.4f} TOE (1 TOE = 1,000 kgOE)\n\n"

    proc_str += f"3. 열에너지(Heat Energy) 환산 데이터 (근거: 한국에너지공단 기준)\n"
    proc_str += f" - [지역난방/산업열원] 총 열량 : {res['gcal']:,.2f} Gcal (1 kgOE = 0.01 Gcal)\n"
    proc_str += f" - [가구 난방계량기]   총 열량 : {res['mcal']:,.0f} Mcal (1 kgOE = 10 Mcal)\n"
    proc_str += f" - [국가 표준 열량단위] 총 열량 : {res['gj']:,.2f} GJ   (1 kgOE = 0.041868 GJ)\n\n"

    proc_str += f"4. 전력량 환산 및 에너지 믹스\n"
    proc_str += f" - 산출식 : 총 소비량({res['kgOE']:,.2f} kgOE) × 11.63 kWh/kgOE\n"
    proc_str += f" - 총 전력 소비량 : {res['kwh']:,.2f} kWh ({res['mwh']:,.3f} MWh)\n"
    proc_str += f" - 재생에너지 전력 : {res['renewable_kwh']:,.1f} kWh ({inp['renewable']}%)\n"
    proc_str += f" - 화석연료 전력   : {res['fossil_kwh']:,.1f} kWh ({100-inp['renewable']:.1f}%)\n\n"

    proc_str += f"5. 화석연료 연소 소모량 및 온실가스 배출량 (근거: IPCC/GIR 계수)\n"
    proc_str += f" - 석유 (40%) : {res['fossil_kwh']*0.4:,.1f} kWh ÷ 10 = {res['oil_liter']:,.2f} L  (배출: {res['co2_oil']:,.2f} kgCO₂)\n"
    proc_str += f" - 석탄 (35%) : {res['fossil_kwh']*0.35:,.1f} kWh ÷ 6.7 = {res['coal_kg']:,.2f} kg (배출: {res['co2_coal']:,.2f} kgCO₂)\n"
    proc_str += f" - 가스 (25%) : {res['fossil_kwh']*0.25:,.1f} kWh ÷ 10.5 = {res['gas_m3']:,.2f} m³ (배출: {res['co2_gas']:,.2f} kgCO₂)\n"
    proc_str += f" -----------------------------------------------------------\n"
    proc_str += f" - 총 온실가스 배출량 : {res['co2_ton']:,.4f} tCO₂eq ({res['co2_kg']:,.1f} kgCO₂)\n"
    proc_str += f" - 소나무 흡수 필요량 : 약 {res['trees']:,.0f} 그루 (국립산림과학원 기준, 22 kgCO₂/년)\n\n"

    proc_str += f"==========================================================="

    txt.insert(tk.END, proc_str)
    txt.config(state=tk.DISABLED)

# =====================================
# 메인 계산 및 시각화 함수
# =====================================

def calculate():
    global latest_results
    try:
        results = []
        selected_year_key = data_year_var.get()

        for i in range(3):
            country = cond_vars[i]['country'].get()
            region = cond_vars[i]['region'].get()
            age = cond_vars[i]['age'].get()
            job = cond_vars[i]['job'].get()
            pop = int(cond_vars[i]['pop'].get())
            renewable = float(cond_vars[i]['renewable'].get())

            res = compute_metrics(selected_year_key, country, region, age, job, pop, renewable)
            res['label'] = f"조건 {i+1}\n({country}/{renewable}%)"
            results.append(res)

        latest_results = results

        result_text.config(state=tk.NORMAL)
        result_text.delete("1.0", tk.END)

        text_str = "===========================================================\n"
        text_str += f"  3개 조건 비교 시뮬레이션 요약 (기준: {results[0]['data_year']})\n"
        text_str += "  (아래 조건 항목을 클릭하면 상세 가중치 계산과정을 확인합니다)\n"
        text_str += "===========================================================\n\n"
        result_text.insert(tk.END, text_str)

        for i, r in enumerate(results):
            c = cond_vars[i]['country'].get()
            ren = cond_vars[i]['renewable'].get()
            w_comb = r['weights']['combined']

            tag_name = f"cond_{i}"

            header_text = f"■ [조건 {i+1}] {c} / {cond_vars[i]['region'].get()} / 재생 {ren}% ▶ [가중치 계산과정 보기]\n"
            result_text.insert(tk.END, header_text, tag_name)

            body_text = f" - 통합가중치 : {w_comb:.4f}배 (지역 × 연령 × 직업)\n"
            body_text += f" - 1차에너지 : {r['toe']:,.3f} TOE ({r['kgOE']:,.0f} kgOE)\n"
            body_text += f" - 열 에 너 지 : {r['gcal']:,.2f} Gcal ({r['mcal']:,.0f} Mcal / {r['gj']:,.2f} GJ)\n"
            body_text += f" - 전력/배출 : {r['mwh']:,.2f} MWh | 탄소배출 {r['co2_ton']:,.3f} tCO₂\n\n"
            result_text.insert(tk.END, body_text)

            result_text.tag_config(tag_name, foreground="#0055FF", font=font_mono, underline=True)
            result_text.tag_bind(tag_name, "<Button-1>", lambda e, idx=i: show_detail_window(idx))

        draw_chart(results)

    except KeyError:
        messagebox.showerror("오류", "모든 항목을 올바르게 선택해 주세요.")
    except ValueError:
        messagebox.showerror("오류", "인구수와 재생에너지 비율에 올바른 숫자를 입력해 주세요.")

def draw_chart(results):
    fig.clear()

    labels = [r['label'] for r in results]
    co2_vals = [r['co2_ton'] for r in results]
    fossil_vals = [r['fossil_kwh'] for r in results]
    renew_vals = [r['renewable_kwh'] for r in results]

    ax1 = fig.add_subplot(121)
    ax2 = fig.add_subplot(122)

    colors = ['#FF6B6B', '#4D96FF', '#2ED573']
    bars = ax1.bar(labels, co2_vals, color=colors, width=0.45)
    ax1.set_title(f"CO₂ 배출량 비교 (tCO₂) [{results[0]['data_year']}]", fontsize=9, fontweight='bold')
    ax1.set_ylabel("탄소배출량 (tCO₂)")
    ax1.grid(axis='y', linestyle='--', alpha=0.5)

    for bar in bars:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval, f"{yval:,.2f}", ha='center', va='bottom', fontsize=8)

    ax2.bar(labels, fossil_vals, label='화석연료', color='#808080', width=0.45)
    ax2.bar(labels, renew_vals, bottom=fossil_vals, label='재생에너지', color='#2ED573', width=0.45)
    ax2.set_title(f"에너지 믹스 구성 (kWh) [{results[0]['data_year']}]", fontsize=9, fontweight='bold')
    ax2.set_ylabel("kWh")
    ax2.legend(loc='upper right', fontsize=8)
    ax2.grid(axis='y', linestyle='--', alpha=0.5)

    fig.tight_layout()
    canvas.draw()

def on_year_change(event=None):
    selected_year = data_year_var.get()
    country_list = list(ENERGY_DATA_BY_YEAR[selected_year]["country_energy"].keys())
    
    for i in range(3):
        country_combos[i]['values'] = country_list
        if cond_vars[i]['country'].get() not in country_list:
            cond_vars[i]['country'].set(country_list[0])
            
    calculate()

# =====================================
# GUI 화면 구성 및 폰트 관리
# =====================================

root = tk.Tk()
root.title("에너지·탄소중립 시뮬레이터")
root.geometry("1160x780")

font_delta = 0

font_default = tkfont.Font(family=font_family_base, size=9)
font_title = tkfont.Font(family=font_family_base, size=11, weight="bold")
font_mono = tkfont.Font(family="Consolas", size=9)
font_footer = tkfont.Font(family=font_family_base, size=8)

style = ttk.Style()
style.configure(".", font=font_default)
style.configure("Header.TLabel", font=font_title)

def adjust_font_size(delta):
    global font_delta
    new_delta = font_delta + delta
    if -3 <= new_delta <= 7:
        font_delta = new_delta
        font_default.configure(size=9 + font_delta)
        font_title.configure(size=11 + font_delta)
        font_mono.configure(size=9 + font_delta)
        font_footer.configure(size=8 + font_delta)

def reset_font_size():
    global font_delta
    font_delta = 0
    font_default.configure(size=9)
    font_title.configure(size=11)
    font_mono.configure(size=9)
    font_footer.configure(size=8)

# 상단 레이아웃
top_header_frame = ttk.Frame(root, padding=(10, 6, 10, 2))
top_header_frame.pack(side=tk.TOP, fill=tk.X)

app_title_label = ttk.Label(top_header_frame, text="에너지·탄소중립 시뮬레이터", style="Header.TLabel")
app_title_label.pack(side=tk.LEFT, anchor="w")

font_bar = ttk.Frame(top_header_frame)
font_bar.pack(side=tk.RIGHT, anchor="e")

font_bar_label = ttk.Label(font_bar, text="Font Size Control:")
font_bar_label.pack(side=tk.LEFT, padx=(0, 6))

btn_font_sub = ttk.Button(font_bar, text=" - 폰트 축소 ", command=lambda: adjust_font_size(-1), width=11)
btn_font_sub.pack(side=tk.LEFT, padx=2)

btn_font_reset = ttk.Button(font_bar, text=" 폰트 초기화 ", command=reset_font_size, width=11)
btn_font_reset.pack(side=tk.LEFT, padx=2)

btn_font_add = ttk.Button(font_bar, text=" + 폰트 확대 ", command=lambda: adjust_font_size(1), width=11)
btn_font_add.pack(side=tk.LEFT, padx=2)

year_select_frame = ttk.LabelFrame(root, text=" 통계 기준 연도 선택 ", padding=(10, 4))
year_select_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=2)

ttk.Label(year_select_frame, text="계산근거 통계 기준:").pack(side=tk.LEFT, padx=(0, 6))

data_year_var = tk.StringVar(value=list(ENERGY_DATA_BY_YEAR.keys())[0])
year_combo = ttk.Combobox(year_select_frame, textvariable=data_year_var, values=list(ENERGY_DATA_BY_YEAR.keys()), state="readonly", width=50)
year_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
year_combo.bind("<<ComboboxSelected>>", on_year_change)

footer_frame = ttk.Frame(root)
footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 2))

copyright_label = tk.Label(
    footer_frame,
    text="Copyright © Lee Jae-Hee, 2026.09.02. All rights reserved.",
    font=font_footer,
    fg="#666666"
)
copyright_label.pack(side=tk.RIGHT, anchor="e")

main_container = ttk.Frame(root)
main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

cond_vars = []
default_defaults = [
    {"country": "대한민국", "region": "도시", "age": "20~39세", "job": "사무직", "pop": "1", "renewable": "20"},
    {"country": "대한민국", "region": "도시", "age": "20~39세", "job": "사무직", "pop": "1", "renewable": "50"},
    {"country": "대한민국", "region": "도시", "age": "20~39세", "job": "사무직", "pop": "1", "renewable": "80"},
]

for i in range(3):
    d = default_defaults[i]
    cond_vars.append({
        'country': tk.StringVar(value=d['country']),
        'region': tk.StringVar(value=d['region']),
        'age': tk.StringVar(value=d['age']),
        'job': tk.StringVar(value=d['job']),
        'pop': tk.StringVar(value=d['pop']),
        'renewable': tk.StringVar(value=d['renewable']),
    })

left_frame = ttk.Frame(main_container, padding=10)
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

right_frame = ttk.Frame(main_container, padding=10)
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

input_master = ttk.LabelFrame(left_frame, text=" 3개 비교 조건 설정 ", padding=8)
input_master.pack(fill=tk.X, pady=2)

country_combos = []
initial_country_list = list(ENERGY_DATA_BY_YEAR[data_year_var.get()]["country_energy"].keys())
initial_region_list = list(ENERGY_DATA_BY_YEAR[data_year_var.get()]["region_factor"].keys())
initial_age_list = list(ENERGY_DATA_BY_YEAR[data_year_var.get()]["age_factor"].keys())
initial_job_list = list(ENERGY_DATA_BY_YEAR[data_year_var.get()]["job_factor"].keys())

for i in range(3):
    sub_frame = ttk.LabelFrame(input_master, text=f" 조건 {i+1} ", padding=5)
    sub_frame.grid(row=0, column=i, padx=4, pady=2, sticky=tk.N)

    ttk.Label(sub_frame, text="국가:").grid(row=0, column=0, sticky=tk.W, pady=1)
    cb_country = ttk.Combobox(sub_frame, textvariable=cond_vars[i]['country'], values=initial_country_list, state="readonly", width=9)
    cb_country.grid(row=0, column=1)
    country_combos.append(cb_country)

    ttk.Label(sub_frame, text="지역:").grid(row=1, column=0, sticky=tk.W, pady=1)
    ttk.Combobox(sub_frame, textvariable=cond_vars[i]['region'], values=initial_region_list, state="readonly", width=9).grid(row=1, column=1)

    ttk.Label(sub_frame, text="연령:").grid(row=2, column=0, sticky=tk.W, pady=1)
    ttk.Combobox(sub_frame, textvariable=cond_vars[i]['age'], values=initial_age_list, state="readonly", width=9).grid(row=2, column=1)

    ttk.Label(sub_frame, text="직업:").grid(row=3, column=0, sticky=tk.W, pady=1)
    ttk.Combobox(sub_frame, textvariable=cond_vars[i]['job'], values=initial_job_list, state="readonly", width=9).grid(row=3, column=1)

    ttk.Label(sub_frame, text="인구(명):").grid(row=4, column=0, sticky=tk.W, pady=1)
    ttk.Entry(sub_frame, textvariable=cond_vars[i]['pop'], width=11).grid(row=4, column=1)

    ttk.Label(sub_frame, text="재생(%):").grid(row=5, column=0, sticky=tk.W, pady=1)
    ttk.Entry(sub_frame, textvariable=cond_vars[i]['renewable'], width=11).grid(row=5, column=1)

ttk.Button(left_frame, text="3개 조건 시뮬레이션 및 비교 계산", command=calculate).pack(fill=tk.X, pady=6)

result_text = tk.Text(left_frame, width=64, height=12, font=font_mono, cursor="hand2")
result_text.pack(fill=tk.BOTH, expand=True, pady=2)

detail_btn_frame = ttk.LabelFrame(left_frame, text=" 조건별 상세 계산과정 확인 버튼 ", padding=4)
detail_btn_frame.pack(fill=tk.X, pady=4)

ttk.Button(detail_btn_frame, text="조건 1 계산과정", command=lambda: show_detail_window(0)).pack(side=tk.LEFT, expand=True, padx=2)
ttk.Button(detail_btn_frame, text="조건 2 계산과정", command=lambda: show_detail_window(1)).pack(side=tk.LEFT, expand=True, padx=2)
ttk.Button(detail_btn_frame, text="조건 3 계산과정", command=lambda: show_detail_window(2)).pack(side=tk.LEFT, expand=True, padx=2)

link_frame = ttk.LabelFrame(left_frame, text=" 검증된 세부 계산근거 출처 사이트 ", padding=6)
link_frame.pack(fill=tk.X, pady=2)

source_var = tk.StringVar()
source_combo = ttk.Combobox(link_frame, textvariable=source_var, values=list(data_sources.keys()), state="readonly", width=42)
source_combo.current(0)
source_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 4), pady=2)

open_btn = ttk.Button(link_frame, text="사이트 이동", command=open_selected_url, width=10)
open_btn.pack(side=tk.RIGHT, padx=(2, 2), pady=2)

fig = matplotlib.figure.Figure(figsize=(6, 6), dpi=100)
canvas = FigureCanvasTkAgg(fig, master=right_frame)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

calculate()

root.mainloop()
