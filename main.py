import torch
import numpy as np
import joblib
import pandas as pd
from src import config
from src.model import MLP
from src.preprocess import load_data, prepare_features
from sklearn.preprocessing import StandardScaler

MODEL_PATH = "model/credit_model.pt"
SCALER_PATH = "model/scaler.pkl"

def load_scaler(path=SCALER_PATH):
    """
    Загружает сохранённый StandardScaler.
    """
    scaler = joblib.load(path)
    return scaler

def load_model(input_dim, path=MODEL_PATH):
    """
    Загружает сохранённую модель.
    """
    model = MLP(input_dim)
    model.load_state_dict(torch.load(path))
    model.eval()
    return model

def get_user_input(feature_names_rus):
    """
    Получает ввод пользователя по всем признакам.
    """
    print("Введите значения признаков через запятую (в порядке):")
    for name in feature_names_rus:
        print(f" - {name}")
    raw = input("\n> ")
    values = list(map(float, raw.strip().split(',')))
    if len(values) != len(feature_names_rus):
        raise ValueError(f"Ожидалось {len(feature_names_rus)} значений, получено {len(values)}.")
    return np.array(values).reshape(1, -1)

def main():
    # Русские названия признаков (порядок должен совпадать с обучением)
    feature_names_rus = [
        "Коэффициент использования незаблокированных кредитных линий",
        "Возраст",
        "Количество просрочек 30-59 дней",
        "Долговая нагрузка (Debt Ratio)",
        "Ежемесячный доход",
        "Количество открытых кредитных линий",
        "Количество просрочек более 90 дней",
        "Количество кредитов на недвижимость",
        "Количество просрочек 60-89 дней",
        "Количество иждивенцев"
    ]

    # Названия колонок в исходном датасете и scaler-е
    feature_names_orig = [
        "RevolvingUtilizationOfUnsecuredLines",
        "age",
        "NumberOfTime30-59DaysPastDueNotWorse",
        "DebtRatio",
        "MonthlyIncome",
        "NumberOfOpenCreditLinesAndLoans",
        "NumberOfTimes90DaysLate",
        "NumberRealEstateLoansOrLines",
        "NumberOfTime60-89DaysPastDueNotWorse",
        "NumberOfDependents"
    ]

    try:
        scaler = load_scaler()
        input_dim = len(feature_names_rus)
        model = load_model(input_dim)

        user_input = get_user_input(feature_names_rus)

        # Создаём DataFrame с правильными названиями колонок для scaler
        user_input_df = pd.DataFrame(user_input, columns=feature_names_orig)

        user_input_scaled = scaler.transform(user_input_df)
        input_tensor = torch.tensor(user_input_scaled, dtype=torch.float32)

        with torch.no_grad():
            prediction = model(input_tensor).item()

        print(f"\n🔮 Вероятность дефолта: {prediction * 100:.2f}%")
        if prediction > 0.5:
            print("⚠️ Высокий риск дефолта!")
        else:
            print("✅ Риск дефолта низкий.")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")

if __name__ == "__main__":
    main()
