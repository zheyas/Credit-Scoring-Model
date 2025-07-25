import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

def load_data(path):
    # Читаем CSV, указывая, что первый столбец — индекс
    df = pd.read_csv(path, index_col=0)
    df = df.dropna()  # простая стратегия: удалить строки с пропусками
    return df

def prepare_features(df, target_col):
    X = df.drop(columns=[target_col])
    y = df[target_col].values.reshape(-1, 1)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return X_scaled, y, scaler

def split_data(X, y, test_size=0.2, seed=42):
    return train_test_split(X, y, test_size=test_size, random_state=seed, stratify=y)
