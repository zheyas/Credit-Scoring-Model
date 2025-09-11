
import torch
import numpy as np
import joblib
import pandas as pd
from src.model import MLP
import setting

# Пути к файлам модели и скейлера
MODEL_PATH = "model/credit_model.pt"
SCALER_PATH = "model/scaler.pkl"

# Импорт имен признаков из настроек
feature_names_rus = setting.FEATURES_RU
feature_names_orig = setting.FEATURES

# Функция для загрузки скейлера
def load_scaler(path=SCALER_PATH):
    scaler = joblib.load(path)
    return scaler

# Функция для загрузки модели
def load_model(input_dim, path=MODEL_PATH):
    model = MLP(input_dim)
    model.load_state_dict(torch.load(path, map_location=torch.device('cpu')))
    model.eval()
    return model

# Загрузить скейлер и модель, когда модуль импортируется
scaler = load_scaler()
model = load_model(len(feature_names_rus))

# Функция для предсказания
def predict(features):
    try:
        x = np.array(features, dtype=float).reshape(1, -1)
        df = pd.DataFrame(x, columns=feature_names_orig)

        x_scaled = scaler.transform(df)
        X_tensor = torch.tensor(x_scaled, dtype=torch.float32)

        with torch.no_grad():
            prob = float(model(X_tensor).item())

        # На всякий случай зажмём в [0,1]
        prob = max(0.0, min(1.0, prob))

        # Три уровня риска
        if prob < 0.33:
            level = "Низкий"
        elif prob < 0.66:
            level = "Средний"
        else:
            level = "Высокий"

        # Flask уже умеет форматировать по полю prob
        return {"prob": prob, "level": level}

    except Exception as e:
        return {"error": str(e)}
