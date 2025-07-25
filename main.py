import torch
import numpy as np
import joblib
import pandas as pd
import tkinter as tk
from tkinter import messagebox

from src.model import MLP

MODEL_PATH = "model/credit_model.pt"
SCALER_PATH = "model/scaler.pkl"

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

def load_scaler(path=SCALER_PATH):
    scaler = joblib.load(path)
    return scaler

def load_model(input_dim, path=MODEL_PATH):
    model = MLP(input_dim)
    model.load_state_dict(torch.load(path, map_location=torch.device('cpu')))
    model.eval()
    return model

scaler = load_scaler()
model = load_model(len(feature_names_rus))
LABEL_COLOR = "#343361"
COLORS = {
    "main_bg": "#F1EEDD",
    "panel_bg": "#343361",
    "panel_fg": "#F1EEDD",
    "entry_bg": "#8788AC",
    "entry_fg": "#FFFFFF",
    "field_bg": "#89A894",
    "button_bg": "#343361",
    "button_fg": "#F1EEDD",
    "button_active_bg": "#8788AC",
    "button_active_fg": "#F1EEDD",
    "result_high": "#c0362c",
    "result_low": "#337a6a",
}

class CreditApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Кредитный скоринг")
        self.geometry("740x600")
        self.resizable(False, False)
        self.configure(bg=COLORS["main_bg"])

        # Верхняя панель
        panel = tk.Frame(self, bg=COLORS["panel_bg"], height=90)
        panel.pack(fill=tk.X)
        tk.Label(panel, text="💳 Кредитный скоринг",
                 bg=COLORS["panel_bg"], fg=COLORS["panel_fg"],
                 font=("Arial", 26, "bold")).pack(pady=(20, 0))

        # ---- Scrollable Canvas ----
        container = tk.Frame(self, bg=COLORS["main_bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=0, pady=(5,0))

        canvas = tk.Canvas(container, bg=COLORS["main_bg"], bd=0, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        form = tk.Frame(canvas, bg=COLORS["main_bg"])
        form.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.entries = []

        LABEL_WIDTH = 37  # кол-во символов
        ENTRY_WIDTH = 21  # кол-во символов для Entry
        WRAPLEN = 350     # ширина в пикселях для переноса текста

        for i, name in enumerate(feature_names_rus):
            field = tk.Frame(form, bg=COLORS["main_bg"])
            field.pack(fill=tk.X, padx=32, pady=10)
            label = tk.Label(field, anchor='w', text=name+":",
font=("Arial", 13, "bold"),
                             bg=COLORS["field_bg"], fg=COLORS["panel_bg"],
                             relief="flat", padx=10, pady=9,
                             wraplength=WRAPLEN, justify='left', width=LABEL_WIDTH)
            label.grid(row=0, column=0, sticky="wens")
            entry = tk.Entry(field, font=("Arial", 14), bg=COLORS["entry_bg"], fg=COLORS["entry_fg"],
                             width=ENTRY_WIDTH, relief="flat", insertbackground=COLORS["panel_bg"], bd=2,
                             highlightthickness=0, justify='center')
            entry.grid(row=0, column=1, padx=(14, 0), ipadx=4, ipady=5, sticky="e")
            self.entries.append(entry)

            # Гарантированно одинаковая высота полей
            field.grid_columnconfigure(0, minsize=WRAPLEN+18)
            field.grid_columnconfigure(1, minsize=182)

        # Результат
        self.result_label = tk.Label(self, text="", font=("Arial", 18, "bold"), bg=COLORS["main_bg"])
        self.result_label.pack(pady=22)

        # Крупная кнопка
        self.button = tk.Button(
            self,
            text="Рассчитать вероятность дефолта",
            font=("Arial", 16, "bold"),
            command=self.predict,
            bg=COLORS["button_bg"],  # оставить как есть (фон)
            fg=LABEL_COLOR,  # цвет текста кнопки (уже как у лейблов)
            activebackground=COLORS["button_active_bg"],
            activeforeground=LABEL_COLOR,  # цвет текста при наведении
            disabledforeground=LABEL_COLOR,  # если кнопка неактивна
            bd=0,
            relief="flat",
            padx=20,
            pady=10,
            cursor="hand2"
        )
        self.button.pack(pady=10)

        # Mousewheel scroll for entries
        def _on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def predict(self):
        try:
            values = []
            for i, entry in enumerate(self.entries):
                val = entry.get().replace(",", ".").strip()
                if not val:
                    raise ValueError(f"Заполните поле: {feature_names_rus[i]}")
                val = float(val)
                values.append(val)
            input_nd = np.array(values).reshape(1, -1)
            df = pd.DataFrame(input_nd, columns=feature_names_orig)
            input_scaled = scaler.transform(df)
            X_tensor = torch.tensor(input_scaled, dtype=torch.float32)
            with torch.no_grad():
                prediction = model(X_tensor).item()
            percent = prediction * 100
            if prediction > 0.5:
                verdict = "⚠️ Высокий риск дефолта"
                color = COLORS["result_high"]
            else:
                verdict = "✅ Риск дефолта низкий"
                color = COLORS["result_low"]
            text = f"Вероятность дефолта: {percent:.2f}%\n{verdict}"
            self.result_label.config(text=text, fg=color)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    app = CreditApp()
    app.mainloop()