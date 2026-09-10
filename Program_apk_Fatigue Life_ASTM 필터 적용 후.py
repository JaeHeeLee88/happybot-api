import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import ctypes
import os

# --- Windows 11 고해상도(DPI) 디스플레이 최적화 ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
# --------------------------------------------------

def calculate_fatigue():
    # 1. 파일 다중 선택
    filepaths = filedialog.askopenfilenames(
        title="데이터 파일 다중 선택 (여러 파일 선택 가능)",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if not filepaths:
        return

    # 2. 파라미터 가져오기 (재료, 스케일, 필터 수치)
    material = material_var.get()
    
    if material == "Carbon steel":
        Su, Sf_prime, b = 580.0, 850.0, -0.09
    elif material == "STS304":
        Su, Sf_prime, b = 505.0, 750.0, -0.10
    elif material == "STS310S":
        Su, Sf_prime, b = 515.0, 760.0, -0.10
    elif material == "SS400":
        Su, Sf_prime, b = 400.0, 600.0, -0.09
    else:
        messagebox.showerror("Error", "재료를 선택해주세요.")
        return

    try:
        scale_factor = float(scale_var.get())
        ma_window = int(ma_var.get())
        threshold_stress = float(threshold_var.get())
    except ValueError:
        messagebox.showerror("Error", "입력값(Scale, Window, Threshold)에는 숫자만 입력해주세요.")
        return

    summary_results = []

    # 3. 선택된 각 파일에 대해 반복 해석 수행
    for filepath in filepaths:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # 스케일 팩터 적용 (응력 단위로 변환)
                raw_data = [float(line.strip()) * scale_factor for line in lines if line.strip()]
        except Exception as e:
            messagebox.showwarning("Warning", f"{os.path.basename(filepath)} 파일을 읽는 중 오류 발생.\n{e}")
            continue

        if len(raw_data) < 2:
            continue

        # ---------------------------------------------------------
        # [신호 전처리 1] Moving Average (이동 평균) - 앨리어싱 노이즈 평활화
        # ---------------------------------------------------------
        if ma_window > 1:
            series = pd.Series(raw_data)
            # min_periods=1을 통해 데이터 양끝의 유실 방지
            raw_data = series.rolling(window=ma_window, center=True, min_periods=1).mean().tolist()

        # ---------------------------------------------------------
        # [신호 전처리 2] Hysteresis Dead-band Filter (ASTM E1049-85)
        # ---------------------------------------------------------
        if threshold_stress > 0:
            filtered_data = [raw_data[0]]
            for i in range(1, len(raw_data)):
                # 이전 기록된 지점 대비 변화량이 Threshold 이상일 때만 유효 데이터로 취급
                if abs(raw_data[i] - filtered_data[-1]) >= threshold_stress:
                    filtered_data.append(raw_data[i])
            # 마지막 데이터 보존 처리
            if filtered_data[-1] != raw_data[-1]:
                filtered_data.append(raw_data[-1])
            
            raw_data = filtered_data

        if len(raw_data) < 2:
            continue

        # 4. Turning Point(TP) 추출 (변곡점 탐색)
        TP = [raw_data[0]]
        for i in range(1, len(raw_data) - 1):
            prev_val = raw_data[i - 1]
            curr_val = raw_data[i]
            next_val = raw_data[i + 1]

            if (curr_val >= prev_val and curr_val > next_val) or \
               (curr_val <= prev_val and curr_val < next_val):
                TP.append(curr_val)
        TP.append(raw_data[-1])

        # 5. Rainflow Counting 및 손상(Damage) 계산 로직
        stack = []
        total_damage = 0.0
        total_cycles_in_block = 0.0
        max_amp = 0.0
        max_mean = 0.0

        def process_cycle(range_val, mean_val, count_val):
            nonlocal total_damage, total_cycles_in_block, max_amp, max_mean
            
            amp = range_val / 2.0
            
            if amp > max_amp: max_amp = amp
            if mean_val > max_mean: max_mean = mean_val
                
            # Goodman 평균 응력 보정
            if mean_val > 0 and Su > 0:
                if mean_val >= Su:
                    eq_amp = amp * 1000.0 # 정적 파단 유도
                else:
                    eq_amp = amp / (1.0 - (mean_val / Su))
            else:
                eq_amp = amp

            # Basquin 수명 계산
            if eq_amp > 0:
                nf = 0.5 * ((eq_amp / Sf_prime) ** (1.0 / b))
                damage = count_val / nf
            else:
                nf = 1e30
                damage = 0.0

            total_damage += damage
            total_cycles_in_block += count_val

        # 닫힌 루프 처리
        for tp in TP:
            stack.append(tp)
            while len(stack) >= 3:
                S1 = abs(stack[-2] - stack[-3])
                S2 = abs(stack[-1] - stack[-2])

                if S2 < S1:
                    break

                range_val = S1
                mean_val = (stack[-2] + stack[-3]) / 2.0
                count_val = 0.5 if len(stack) == 3 else 1.0

                process_cycle(range_val, mean_val, count_val)

                if len(stack) == 3:
                    stack.pop(0)
                else:
                    stack.pop(-2)
                    stack.pop(-2)

        # 잔여 스택 (열린 루프) 처리
        for j in range(len(stack) - 1):
            range_val = abs(stack[j + 1] - stack[j])
            mean_val = (stack[j + 1] + stack[j]) / 2.0
            count_val = 0.5
            process_cycle(range_val, mean_val, count_val)

        # 개별 파일 해석 결과 산출
        predicted_life_blocks = 1.0 / total_damage if total_damage > 0 else float('inf')
        fatigue_life_cycles = predicted_life_blocks * total_cycles_in_block if total_damage > 0 else float('inf')
        filename_without_ext = os.path.splitext(os.path.basename(filepath))[0]

        summary_results.append([
            filename_without_ext, max_amp, max_mean, 
            total_cycles_in_block, total_damage, 
            predicted_life_blocks, fatigue_life_cycles
        ])

    # 6. 결과 요약 및 엑셀 저장
    if not summary_results:
        messagebox.showerror("Error", "유효한 분석 결과가 없습니다. (데이터 부족 또는 필터값이 너무 큼)")
        return

    columns = [
        "Measurement Date", "Max. Stress Amp. (MPa)", "Max. Mean Stress (MPa)", 
        "Total Count (cycles)", "Total Damage (-)", "Predicted Life (blocks)", "Fatigue Life (cycles)"
    ]
    df_summary = pd.DataFrame(summary_results, columns=columns)

    # 전체 데이터 평균 행 추가
    mean_row = df_summary.mean(numeric_only=True).to_frame().T
    mean_row["Measurement Date"] = "Average"
    df_summary = pd.concat([df_summary, mean_row], ignore_index=True)

    base_dir = os.path.dirname(filepaths[0])
    save_path = os.path.join(base_dir, f"Fatigue_Filtered_Results_{material}.xlsx")
    df_summary.to_excel(save_path, index=False)

    # GUI 결과창 업데이트
    result_text.delete(1.0, tk.END)
    result_text.insert(tk.END, f"--- Analysis Completed ({material}) ---\n\n")
    result_text.insert(tk.END, f"Moving Average Window : {ma_window} mins\n")
    result_text.insert(tk.END, f"Hysteresis Threshold  : {threshold_stress} MPa\n")
    result_text.insert(tk.END, f"Processed Files       : {len(filepaths)} files\n")
    result_text.insert(tk.END, f"Exported To           : {os.path.basename(save_path)}\n\n")
    result_text.insert(tk.END, "해석이 완료되어 폴더에 엑셀 파일이 생성되었습니다.")
    messagebox.showinfo("완료", f"분석 완료!\n결과 경로: {save_path}")

# --- GUI 구성 ---
root = tk.Tk()
root.title("Fatigue Life Predictor - Advanced Filtering")
root.geometry("540x480")
root.resizable(False, False)

default_font = ("Segoe UI", 10)
root.option_add("*Font", default_font)

frame = ttk.Frame(root, padding=20)
frame.pack(fill=tk.BOTH, expand=True)

# 1. 재료 선택
ttk.Label(frame, text="Material Selection:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5)
material_var = tk.StringVar()
material_cb = ttk.Combobox(frame, textvariable=material_var, state="readonly", width=25)
material_cb['values'] = ("STS304", "Carbon steel", "STS310S", "SS400")
material_cb.current(1)
material_cb.grid(row=0, column=1, sticky=tk.W, pady=5)

# 2. 스케일 팩터
ttk.Label(frame, text="Data Scale Factor:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky=tk.W, pady=5)
scale_var = tk.StringVar(value="100.0")
ttk.Entry(frame, textvariable=scale_var, width=28).grid(row=1, column=1, sticky=tk.W, pady=5)

# 3. 신호 전처리 파라미터 (Moving Average)
ttk.Label(frame, text="Moving Avg Window:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=5)
ma_var = tk.StringVar(value="5") # 기본 5분 단위 스무딩
ttk.Entry(frame, textvariable=ma_var, width=28).grid(row=2, column=1, sticky=tk.W, pady=5)

# 4. 신호 전처리 파라미터 (Hysteresis Threshold)
ttk.Label(frame, text="Hysteresis Threshold:", font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky=tk.W, pady=5)
threshold_var = tk.StringVar(value="20.0") # 20 MPa 이하의 미세진폭 무시
ttk.Entry(frame, textvariable=threshold_var, width=28).grid(row=3, column=1, sticky=tk.W, pady=5)

ttk.Label(frame, text="* Window: 데이터 평활화 구간 (1 = 적용 안함)\n* Threshold: 제거할 미세 응력 진폭 크기 (MPa)").grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

# 5. 실행 버튼
run_btn = ttk.Button(frame, text="Select Multiple Files & Calculate", command=calculate_fatigue)
run_btn.grid(row=5, column=0, columnspan=2, pady=10, ipadx=10, ipady=5)

# 6. 결과 텍스트 박스
result_text = tk.Text(frame, height=9, width=60, bg="#f4f4f4", font=("Consolas", 10))
result_text.grid(row=6, column=0, columnspan=2, pady=5)

root.mainloop()
