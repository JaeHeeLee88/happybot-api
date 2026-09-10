import os
import math
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np

# 시각화 백엔드
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# 머신러닝 (V3)
try:
    from sklearn.ensemble import RandomForestRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# DXF 생성 (V3)
try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False

# PDF 보고서 (V2)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


# ========================================
# DATABASES (CFD Lookup & Fan Specs)
# ========================================

# CFD Lookup DB (Tube Ratio, Length Ratio -> CFD Factor)
CFD_LOOKUP_DB = {
    (1.0, 1.0): 0.950,
    (1.2, 1.0): 0.938,
    (1.5, 1.2): 0.921,
    (2.0, 1.5): 0.895,
    (2.5, 2.0): 0.870,
}

# commercial Fan Database (Model, CMM, Static Pressure Pa, Power kW)
FAN_DATABASE = [
    {"model": "AC-FAN-300", "cmm": 20.0, "pa": 120.0, "power_kw": 0.75},
    {"model": "AC-FAN-400", "cmm": 35.0, "pa": 150.0, "power_kw": 1.50},
    {"model": "AC-FAN-550", "cmm": 60.0, "pa": 180.0, "power_kw": 2.20},
    {"model": "AC-FAN-800", "cmm": 100.0, "pa": 220.0, "power_kw": 3.70},
    {"model": "AC-FAN-1200", "cmm": 180.0, "pa": 280.0, "power_kw": 5.50},
]

BASE_CONDENSATION = 5.1
BASE_TUBES = 36
BASE_LENGTH = 580
BASE_OD = 12.7
BASE_ID = 11.1
BASE_X_PITCH = 38
BASE_Y_PITCH = 32
FIN_PITCH = 6
BASE_CMM = 35.68


# ========================================
# AI / ML ENGINE (V3)
# ========================================

class CondenserAIEngine:
    def __init__(self):
        self.model = None
        self.is_trained = False
        self._train_dummy_ml_model()

    def _train_dummy_ml_model(self):
        """실험 DB 머신러닝 보정 모델 초기화 학습"""
        if not HAS_SKLEARN:
            return
        np.random.seed(42)
        # Synthetic Experiment Data: [Px, Py, FinPitch, CMM, FeedMass]
        X = np.random.uniform(low=[30, 25, 4, 20, 100], high=[50, 45, 10, 100, 1200], size=(200, 5))
        # Actual Efficiency Correction Factor (-5% ~ +5%)
        y = 100.0 - (X[:, 0] * 0.1) - (X[:, 2] * 0.5) + np.random.normal(0, 1.5, size=200)
        y = np.clip(y, 70.0, 99.5)

        self.model = RandomForestRegressor(n_estimators=50, random_state=42)
        self.model.fit(X, y)
        self.is_trained = True

    def predict_efficiency(self, px, py, fin_p, cmm, feed_mass):
        if self.is_trained and HAS_SKLEARN:
            features = np.array([[px, py, fin_p, cmm, feed_mass]])
            pred = self.model.predict(features)[0]
            return round(float(pred), 2)
        return 92.5  # Fallback default


ai_engine = CondenserAIEngine()


# ========================================
# DETAILED CALCULATIONS ENGINE
# ========================================

def get_cfd_factor(tube_ratio, length_ratio):
    """CFD Lookup DB 적용 (가장 가까운 노드 검색)"""
    best_key = min(CFD_LOOKUP_DB.keys(), key=lambda k: math.hypot(k[0]-tube_ratio, k[1]-length_ratio))
    return CFD_LOOKUP_DB[best_key]

def select_fan(required_cmm, required_pa):
    """팬 선정 DB 연동"""
    for fan in FAN_DATABASE:
        if fan["cmm"] >= required_cmm and fan["pa"] >= required_pa:
            return fan
    return {"model": "Custom High-Capacity Fan", "cmm": required_cmm*1.2, "pa": required_pa*1.2, "power_kw": 7.5}

def calculate_detailed_pressure_drop(length, tube_count, px, py, fin_pitch):
    """압력손실 상세 계산식"""
    v_max = 4.5  # m/s (기본 유속 가정)
    air_density = 1.205  # kg/m3
    rows = math.ceil(tube_count / 6)
    
    # 튜브 관군 손실 + 핀 마찰 손실 상세
    f_t = 0.25 * ((px / BASE_OD) ** -0.6)
    dp_tube = f_t * rows * (air_density * (v_max ** 2) / 2)
    dp_fin = (2.0 / fin_pitch) * (length / 1000.0) * (air_density * (v_max ** 2) / 2)
    
    total_dp = (dp_tube + dp_fin) * (length / 580.0) ** 0.5
    return round(total_dp, 1)

def calculate_full_condenser(material, moisture_in, feed_mass_day, discharge_mass_day, moisture_out, operating_hours_day, px=38, py=32, fin_p=6):
    """V2/V3 통합 종합 계산 수식"""
    wi_day = feed_mass_day * (moisture_in / 100.0)
    wf_day = discharge_mass_day * (moisture_out / 100.0)
    evaporated_day = max(wi_day - wf_day, 0.0)
    
    condensation_rate = evaporated_day / operating_hours_day
    load_ratio = condensation_rate / BASE_CONDENSATION
    
    tube_count = math.ceil(BASE_TUBES * (load_ratio ** 0.95))
    length = round(BASE_LENGTH * (load_ratio ** 0.60))
    
    tube_ratio = tube_count / BASE_TUBES
    length_ratio = length / BASE_LENGTH
    
    # CFD Lookup DB 적용
    cfd_factor = get_cfd_factor(tube_ratio, length_ratio)
    
    # AI 응축효율 예측 모델 적용
    fan_cmm = round(BASE_CMM * (load_ratio ** 0.85), 1)
    efficiency = ai_engine.predict_efficiency(px, py, fin_p, fan_cmm, feed_mass_day)
    
    # 압력손실 상세 계산
    pressure_drop = calculate_detailed_pressure_drop(length, tube_count, px, py, fin_p)
    
    # 팬 선정
    selected_fan = select_fan(fan_cmm, pressure_drop)
    
    return {
        "원료명": material,
        "1일투입량(kg/day)": feed_mass_day,
        "1일증발량(kg/day)": round(evaporated_day, 2),
        "시간당응축량(kg/h)": round(condensation_rate, 2),
        "부하율": round(load_ratio, 2),
        "튜브수": tube_count,
        "길이(mm)": length,
        "PitchX": px,
        "PitchY": py,
        "FinPitch": fin_p,
        "CFD보정": cfd_factor,
        "응축효율(%)": efficiency,
        "팬용량(CMM)": fan_cmm,
        "압력손실(Pa)": pressure_drop,
        "선정팬모델": selected_fan["model"],
        "팬동력(kW)": selected_fan["power_kw"]
    }


# ========================================
# GUI APPLICATION
# ========================================

class MainAppV3:
    def __init__(self, root):
        self.root = root
        self.root.title("공랭식 응축열교환기 AI 자동설계 시스템 (V2 + V3)")
        self.root.geometry("1100x750")

        self.results = []

        # Notebook (Tab) 구성
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.tab1 = ttk.Frame(self.notebook)
        self.tab2 = ttk.Frame(self.notebook)
        self.tab3 = ttk.Frame(self.notebook)
        self.tab4 = ttk.Frame(self.notebook)

        self.notebook.add(self.tab1, text="단일/다중 Batch 계산")
        self.notebook.add(self.tab2, text="Excel 일괄 처리")
        self.notebook.add(self.tab3, text="Pitch 최적화 & AI 모델")
        self.notebook.add(self.tab4, text="도면/HeatMap/보고서")

        self._build_tab1()
        self._build_tab2()
        self._build_tab3()
        self._build_tab4()

    # ----------------------------------------------------
    # TAB 1: 단일 설계 및 100~1200kg Batch 계산
    # ----------------------------------------------------
    def _build_tab1(self):
        frame = ttk.LabelFrame(self.tab1, text="설계 조건 입력")
        frame.pack(padx=10, pady=10, fill="x")

        labels = ["원료명", "원료함수율(%)", "투입량(kg/day)", "배출량(kg/day)", "배출함수율(%)", "일운전시간(h/day)"]
        self.entries1 = {}

        defaults = ["슬러지", "80", "1000", "200", "20", "20"]
        for i, (lbl, def_val) in enumerate(zip(labels, defaults)):
            ttk.Label(frame, text=lbl).grid(row=i//2, column=(i%2)*2, padx=5, pady=5, sticky="w")
            entry = ttk.Entry(frame, width=20)
            entry.insert(0, def_val)
            entry.grid(row=i//2, column=(i%2)*2+1, padx=5, pady=5)
            self.entries1[lbl] = entry

        btn_frame = ttk.Frame(self.tab1)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="단일 계산 추가", command=self.add_single_calc).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="100kg~1200kg 다중 Batch 실행", command=self.run_multi_batch).pack(side="left", padx=5)

        # 결과 Treeview
        cols = ("원료명", "1일투입량", "시간당응축량", "튜브수", "길이(mm)", "팬용량(CMM)", "압력손실(Pa)", "응축효율(%)", "선정팬")
        self.tree1 = ttk.Treeview(self.tab1, columns=cols, show="headings", height=10)
        for c in cols:
            self.tree1.heading(c, text=c)
            self.tree1.column(c, width=110, anchor="center")
        self.tree1.pack(padx=10, pady=10, fill="both", expand=True)

    def add_single_calc(self):
        try:
            res = calculate_full_condenser(
                self.entries1["원료명"].get(),
                float(self.entries1["원료함수율(%)"].get()),
                float(self.entries1["투입량(kg/day)"].get()),
                float(self.entries1["배출량(kg/day)"].get()),
                float(self.entries1["배출함수율(%)"].get()),
                float(self.entries1["일운전시간(h/day)"].get())
            )
            self.results.append(res)
            self._update_tree(self.tree1, res)
        except Exception as e:
            messagebox.showerror("오류", f"입력값 오류: {e}")

    def run_multi_batch(self):
        """100kg~1200kg 다중 Batch 자동 계산 연산"""
        try:
            mat = self.entries1["원료명"].get()
            m_in = float(self.entries1["원료함수율(%)"].get())
            m_out = float(self.entries1["배출함수율(%)"].get())
            op_h = float(self.entries1["일운전시간(h/day)"].get())

            for feed in range(100, 1300, 100):
                discharge = feed * 0.2  # 비례 배출량 가정
                res = calculate_full_condenser(f"{mat}_{feed}kg", m_in, feed, discharge, m_out, op_h)
                self.results.append(res)
                self._update_tree(self.tree1, res)
            messagebox.showinfo("완료", "100kg~1200kg Batch 계산이 완료되었습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"Batch 계산 실패: {e}")

    # ----------------------------------------------------
    # TAB 2: Excel 일괄 읽기 & Export
    # ----------------------------------------------------
    def _build_tab2(self):
        frame = ttk.Frame(self.tab2)
        frame.pack(pady=10)

        ttk.Button(frame, text="Excel 파일 읽기 (Batch Import)", command=self.import_excel).pack(side="left", padx=5)
        ttk.Button(frame, text="전체 결과 Excel 저장", command=self.export_excel).pack(side="left", padx=5)

        cols = ("원료명", "1일증발량(kg/day)", "시간당응축량(kg/h)", "튜브수", "길이(mm)", "팬용량(CMM)", "응축효율(%)")
        self.tree2 = ttk.Treeview(self.tab2, columns=cols, show="headings", height=15)
        for c in cols:
            self.tree2.heading(c, text=c)
            self.tree2.column(c, width=120, anchor="center")
        self.tree2.pack(padx=10, pady=10, fill="both", expand=True)

    def import_excel(self):
        filepath = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if filepath:
            try:
                df = pd.read_excel(filepath)
                for _, row in df.iterrows():
                    res = calculate_full_condenser(
                        str(row["원료명"]), float(row["원료함수율"]), float(row["투입량"]),
                        float(row["배출량"]), float(row["배출함수율"]), float(row["운전시간"])
                    )
                    self.results.append(res)
                    self._update_tree(self.tree2, res)
                messagebox.showinfo("성공", f"{len(df)}개 항목을 읽어 계산을 완료했습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"Excel 처리 실패: {e}\n(열이름: 원료명, 원료함수율, 투입량, 배출량, 배출함수율, 운전시간)")

    def export_excel(self):
        if not self.results:
            messagebox.showwarning("경고", "저장할 데이터가 없습니다.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if filepath:
            pd.DataFrame(self.results).to_excel(filepath, index=False)
            messagebox.showinfo("완료", "Excel 저장이 완료되었습니다.")

    # ----------------------------------------------------
    # TAB 3: Pitch 최적화 & AI 모델
    # ----------------------------------------------------
    def _build_tab3(self):
        frame = ttk.LabelFrame(self.tab3, text="Tube & Fin Pitch 최적화 탐색")
        frame.pack(padx=10, pady=10, fill="x")

        ttk.Button(frame, text="Pitch 최적화 계산 실행", command=self.optimize_pitches).pack(padx=5, pady=5)
        self.lbl_opt = ttk.Label(frame, text="최적화 결과: 미실행")
        self.lbl_opt.pack(pady=5)

        # Matplotlib Graph Frame (응축량 예측 그래프)
        self.fig_frame = ttk.Frame(self.tab3)
        self.fig_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def optimize_pitches(self):
        """Tube Pitch & Fin Pitch 최적화 계산 알고리즘"""
        best_score = float("inf")
        best_params = None

        for px in range(30, 50, 2):
            for py in range(25, 45, 2):
                for fp in range(4, 10, 1):
                    res = calculate_full_condenser("최적화용", 80, 1000, 200, 20, 20, px, py, fp)
                    # Objective: Pressure drop Minimization + Efficiency Maximization
                    score = res["압력손실(Pa)"] * 0.7 - res["응축효율(%)"] * 1.2
                    if score < best_score:
                        best_score = score
                        best_params = (px, py, fp, res)

        px, py, fp, res = best_params
        self.lbl_opt.config(text=f"최적 PitchX: {px}mm | PitchY: {py}mm | FinPitch: {fp}mm -> 압력손실: {res['압력손실(Pa)']}Pa, AI예측효율: {res['응축효율(%)']}%")
        self._plot_prediction_graph()

    def _plot_prediction_graph(self):
        """응축량 예측 그래프 출력"""
        for child in self.fig_frame.winfo_children():
            child.destroy()

        fig, ax = plt.subplots(figsize=(6, 3), dpi=100)
        batches = [r["1일투입량(kg/day)"] for r in self.results if isinstance(r["1일투입량(kg/day)"], (int, float))]
        rates = [r["시간당응축량(kg/h)"] for r in self.results if isinstance(r["시간당응축량(kg/h)"], (int, float))]

        if not batches:
            batches = [100, 300, 600, 900, 1200]
            rates = [3.5, 11.2, 22.5, 34.0, 45.2]

        ax.plot(batches, rates, "ro-", label="Condensation Rate (kg/h)")
        ax.set_title("Condensation Rate vs Feed Mass")
        ax.set_xlabel("Feed Mass (kg/day)")
        ax.set_ylabel("Rate (kg/h)")
        ax.grid(True)
        ax.legend()

        canvas = FigureCanvasTkAgg(fig, master=self.fig_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ----------------------------------------------------
    # TAB 4: 도면 / HeatMap / PDF 보고서
    # ----------------------------------------------------
    def _build_tab4(self):
        btn_frame = ttk.Frame(self.tab4)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Tube Layout PNG 생성", command=self.generate_layout_png).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="CFD Heat Map 출력", command=self.generate_heatmap).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="DXF 도면 생성 (V3)", command=self.generate_dxf).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="PDF 보고서 자동 작성 (V2)", command=self.generate_pdf).pack(side="left", padx=5)

        self.disp_frame = ttk.Frame(self.tab4)
        self.disp_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def generate_layout_png(self):
        """Tube Layout PNG 자동 생성"""
        for child in self.disp_frame.winfo_children():
            child.destroy()

        fig, ax = plt.subplots(figsize=(5, 4), dpi=100)
        rows, cols_count = 6, 6
        px, py = 38, 32

        for r in range(rows):
            for c in range(cols_count):
                offset = (py / 2) if r % 2 == 1 else 0
                circle = plt.Circle((c * px + offset, r * py), BASE_OD/2, color="blue", fill=False, lw=1.5)
                ax.add_patch(circle)

        ax.set_xlim(-10, cols_count * px + 20)
        ax.set_ylim(-10, rows * py + 10)
        ax.set_aspect("equal")
        ax.set_title("Tube Layout Cross Section (PNG)")

        plt.savefig("tube_layout.png", bbox_inches="tight")

        canvas = FigureCanvasTkAgg(fig, master=self.disp_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        messagebox.showinfo("완료", "tube_layout.png 생성 완료!")

    def generate_heatmap(self):
        """CFD 결과 Heat Map 생성"""
        for child in self.disp_frame.winfo_children():
            child.destroy()

        fig, ax = plt.subplots(figsize=(5, 4), dpi=100)
        data = np.random.rand(10, 10) * 40 + 20  # 온도 분포 Simulation Data

        cax = ax.imshow(data, cmap="jet", interpolation="nearest")
        fig.colorbar(cax)
        ax.set_title("CFD Temperature Heat Map (°C)")

        canvas = FigureCanvasTkAgg(fig, master=self.disp_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def generate_dxf(self):
        """DXF 자동 생성 (V3)"""
        if not HAS_EZDXF:
            messagebox.showerror("오류", "ezdxf 라이브러리가 설치되어 있지 않습니다.")
            return

        doc = ezdxf.new("R2010")
        msp = doc.modelspace()

        # 프레임 및 튜브 그리기
        msp.add_rect((0, 0), (400, 300))
        for r in range(6):
            for c in range(6):
                msp.add_circle((c * 40 + 30, r * 40 + 30), radius=BASE_OD/2)

        filepath = filedialog.asksaveasfilename(defaultextension=".dxf", filetypes=[("DXF Files", "*.dxf")])
        if filepath:
            doc.saveas(filepath)
            messagebox.showinfo("성공", "DXF 도면이 성공적으로 생성되었습니다.")

    def generate_pdf(self):
        """PDF 보고서 자동 작성 (V2)"""
        if not HAS_REPORTLAB:
            messagebox.showerror("오류", "reportlab 라이브러리가 설치되어 있지 않습니다.")
            return

        filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if filepath:
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("Air-Cooled Condenser Design Report", styles["Title"]))
            story.append(Spacer(1, 12))

            if self.results:
                res = self.results[-1]
                table_data = [[k, str(v)] for k, v in res.items()]
                t = Table(table_data, colWidths=[200, 200])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ]))
                story.append(t)

            doc.build(story)
            messagebox.showinfo("완료", "PDF 보고서가 정상적으로 발행되었습니다.")

    def _update_tree(self, tree, res):
        tree.insert("", "end", values=(
            res.get("원료명"), res.get("1일증발량(kg/day)"), res.get("시간당응축량(kg/h)"),
            res.get("튜브수"), res.get("길이(mm)"), res.get("팬용량(CMM)"),
            res.get("압력손실(Pa)"), res.get("응축효율(%)"), res.get("선정팬모델")
        ))


if __name__ == "__main__":
    root = tk.Tk()
    app = MainAppV3(root)
    root.mainloop()
