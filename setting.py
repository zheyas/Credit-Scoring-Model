import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FEATURES = [
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

FEATURES_RU = [
    "Использование кредитного лимита (%)",
    "Возраст",
    "Просрочки 30–59 дней",
    "Долговая нагрузка",
    "Ежемесячный доход",
    "Открытые кредитные линии",
    "Просрочки 90+ дней",
    "Кредиты под недвижимость",
    "Просрочки 60–89 дней",
    "Количество иждивенцев"
]
