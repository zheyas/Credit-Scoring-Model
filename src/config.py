import os
from setting import BASE_DIR

# Корневая папка проекта
DATA_DIR = os.path.join(BASE_DIR, "data")

TRAIN_PATH = os.path.join(DATA_DIR, "train.csv")
TEST_PATH  = os.path.join(DATA_DIR, "test.csv")
TARGET     = "SeriousDlqin2yrs"
RANDOM_SEED = 42
