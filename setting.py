import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

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
    "Использование кредитного лимита по картам (%)",
    "Возраст",
    "Количество просрочек 30–59 дней",
    "Коэффициент долговой нагрузки",
    "Ежемесячный доход",
    "Количество открытых кредитных линий и займов",
    "Количество просрочек 90+ дней",
    "Количество кредитов/линий под недвижимость",
    "Количество просрочек 60–89 дней",
    "Количество иждивенцев"
]