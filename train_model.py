import os
import torch
import joblib
from src import config
from src.preprocess import load_data, prepare_features, split_data
from src.dataset import CreditDataset
from src.model import MLP
from src.train import train_model
from torch.utils.data import DataLoader

MODEL_PATH = "model/credit_model.pt"
SCALER_PATH = "model/scaler.pkl"

def save_model(model, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(model.state_dict(), path)
    print(f"✅ Модель сохранена в {path}")

def save_scaler(scaler, path=SCALER_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(scaler, path)
    print(f"✅ Масштабатор сохранён в {path}")

def load_model(input_dim, path):
    model = MLP(input_dim)
    model.load_state_dict(torch.load(path))
    model.eval()
    return model

def main(train_mode=True):
    df = load_data(config.TRAIN_PATH)
    X, y, scaler = prepare_features(df, config.TARGET)
    X_train, X_val, y_train, y_val = split_data(X, y)

    train_ds = CreditDataset(X_train, y_train)
    val_ds = CreditDataset(X_val, y_val)
    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=32)

    input_dim = X.shape[1]
    model = MLP(input_dim)

    if train_mode:
        train_model(model, train_loader, val_loader, epochs=10)
        save_model(model, MODEL_PATH)
        save_scaler(scaler)
    else:
        model = load_model(input_dim, MODEL_PATH)
        # Пример инференса на валидационной выборке
        sample = torch.tensor(X_val[:5], dtype=torch.float32)
        with torch.no_grad():
            predictions = model(sample)
        print("📊 Прогнозы на первых 5 записях:", predictions.numpy().reshape(-1))

if __name__ == "__main__":
    main(train_mode=True)  # поменяй на False для инференса
