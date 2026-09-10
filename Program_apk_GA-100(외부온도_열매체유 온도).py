import tkinter as tk
from tkinter import simpledialog, messagebox

def predict_summer_performance(ambient_temp, t_oil):
    """
    5월 28일 이후(하절기) 데이터를 기반으로 
    건조성능, 건조효율, 소비전기, 운전시간을 예측하는 함수
    """
    # 1. 건조성능 예측
    perf = 1.1302 - (0.0002 * ambient_temp) + (0.0006 * t_oil)
    
    # 2. 건조효율 예측 (%)
    eff = 72.3004 - (0.1274 * ambient_temp) + (0.0384 * t_oil)
    
    # 3. 소비전기 예측 (kWh)
    elec = 97.6492 + (0.0156 * ambient_temp) - (0.0505 * t_oil)
    
    # 4. 운전시간 예측 (hr)
    time = 17.6507 + (0.0405 * ambient_temp) - (0.0062 * t_oil)
    
    return {
        "건조성능": round(perf, 4),
        "건조효율": round(eff, 2),
        "소비전기": round(elec, 2),
        "운전시간": round(time, 2)
    }

def main():
    # Tkinter 메인 윈도우 생성 후 숨김 처리
    root = tk.Tk()
    root.withdraw()
    
    # 1. 대기온도 입력
    ambient_temp = simpledialog.askfloat(
        "입력 - 하절기 모델", 
        "대기온도(℃)를 입력하세요:\n(예: 25.0 ~ 35.0)",
        minvalue=-30.0,
        maxvalue=100.0
    )
    
    if ambient_temp is None:
        return
        
    # 2. 열매체유 온도(T-oil) 입력
    t_oil = simpledialog.askfloat(
        "입력 - 하절기 모델", 
        "열매체유 온도(T-oil, ℃)를 입력하세요:",
        minvalue=-30.0,
        maxvalue=300.0
    )
    
    if t_oil is None:
        return

    # 3. 모델 예측 수행
    results = predict_summer_performance(ambient_temp, t_oil)
    
    # 4. 결과 메시지 구성
    result_msg = (
        f"--- [입력된 환경 조건] ---\n"
        f"대기온도: {ambient_temp} ℃\n"
        f"열매체유 온도: {t_oil} ℃\n\n"
        f"--- [시스템 예측 결과] ---\n"
        f"▶ 건조성능: {results['건조성능']} kg/Mcal\n"
        f"▶ 건조효율: {results['건조효율']} %\n"
        f"▶ 소비전기: {results['소비전기']} kWh\n"
        f"▶ 운전시간: {results['운전시간']} hr\n\n"
        f"※ 이 예측 모델은 5월 28일 이후 데이터를 기반으로 도출되었습니다."
    )
    
    # 5. 팝업으로 결과 출력
    messagebox.showinfo("시뮬레이션 분석 결과", result_msg)

if __name__ == "__main__":
    main()
