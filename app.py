import os

import setting
from flask import Flask, render_template, request, jsonify
from model import predict
from database import (
    create_application,
    get_application,
    get_dashboard_stats,
    get_default_employee_id,
    init_db,
    list_applications,
    list_departments,
    list_employees,
    upsert_borrower,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "credit-scoring-diploma-demo")
init_db()

forms_label = setting.FEATURES_RU
PRODUCT_NAMES = {
    "consumer": "Потребительский кредит",
    "credit_card": "Кредитная карта",
    "auto": "Автокредит",
    "mortgage": "Ипотечный кредит",
}
EMPLOYMENT_STATUS = {
    "employed": "Работа по найму",
    "self_employed": "Самозанятый / ИП",
    "unemployed": "Не работает",
    "retired": "Пенсионер",
}
STATUS_LABELS = {
    "pending": "На проверке",
    "approved": "Одобрена",
    "rejected": "Отказ",
}


def parse_float(v):
    s = str(v or '').strip().replace(',', '.')
    if s == '':
        raise ValueError('Пустое значение')
    return float(s)


def format_result_text(value):
    # Принимаем либо долю 0..1, либо уже проценты
    try:
        prob = float(value)
        pct = prob * 100 if prob <= 1 else prob
        pct = max(0.0, min(100.0, pct))
        if pct < 33:
            level = "Низкий риск дефолта"
            emoji = "✅"
        elif pct < 66:
            level = "Средний риск дефолта"
            emoji = "⚠️"
        else:
            level = "Высокий риск дефолта"
            emoji = "⛔"
        return f"Вероятность дефолта: {pct:.2f}%\n{emoji} {level}"
    except Exception:
        return str(value)


def normalize_prediction(raw_result):
    if isinstance(raw_result, dict) and "error" in raw_result:
        raise RuntimeError(raw_result["error"])
    if isinstance(raw_result, dict):
        prob = raw_result.get("prob", raw_result.get("probability"))
        level = raw_result.get("level")
    else:
        prob = raw_result
        level = None

    prob = max(0.0, min(1.0, float(prob)))
    if not level:
        if prob < 0.33:
            level = "Низкий"
        elif prob < 0.66:
            level = "Средний"
        else:
            level = "Высокий"
    return {"prob": prob, "level": level}


def build_credit_offer(probability, requested_amount, product_type):
    requested_amount = max(0.0, float(requested_amount or 0))
    product_addon = {
        "consumer": 1.0,
        "credit_card": 3.0,
        "auto": 0.5,
        "mortgage": -0.5,
    }.get(product_type, 1.0)

    if probability < 0.33:
        approved_share = 1.0
        status = "approved"
        comment = "Низкий риск: заявка может быть одобрена в полном объеме."
    elif probability < 0.66:
        approved_share = 0.65
        status = "pending"
        comment = "Средний риск: требуется проверка документов сотрудником банка."
    else:
        approved_share = 0.0
        status = "rejected"
        comment = "Высокий риск: автоматическая рекомендация отказа."

    return {
        "requested_amount": requested_amount,
        "amount": round(requested_amount * approved_share, 2),
        "rate": round(10.5 + product_addon + probability * 18, 1),
        "status": status,
        "comment": comment,
        "product_name": PRODUCT_NAMES.get(product_type, "Кредитный продукт"),
    }


@app.route("/", methods=["GET", "POST"])
def index():
    robot_text = None  # текст для робота

    if request.method == "POST":
        try:
            form_data = request.form.to_dict()

            # Проверяем наличие всех признаков
            missing = [k for k in setting.FEATURES if k not in form_data]
            if missing:
                robot_text = f"⚠️ Отсутствуют поля: {', '.join(missing)}"
            else:
                # Собираем и парсим по порядку
                features = [parse_float(form_data[k]) for k in setting.FEATURES]

                raw_result = predict(features)

                # Нормализуем к строке
                if isinstance(raw_result, (int, float)):
                    robot_text = format_result_text(raw_result)
                elif isinstance(raw_result, dict):
                    prob = None
                    for k in ("prob", "probability", "score", "pd", "default_probability"):
                        if k in raw_result:
                            try:
                                prob = float(raw_result[k])
                                break
                            except Exception:
                                pass
                    if prob is not None:
                        robot_text = format_result_text(prob)
                    else:
                        text = (raw_result.get("result") or raw_result.get("text")
                                or str(raw_result))
                        robot_text = format_result_text(text)
                else:
                    robot_text = str(raw_result)

        except ValueError as e:
            robot_text = f"Ошибка данных: {e}"
        except Exception as e:
            robot_text = f"Серверная ошибка: {e}"

    # GET или POST — всегда рендерим index.html
    return render_template(
        "index.html",
        forms_label=forms_label,
        feature_keys=setting.FEATURES,
        robot_text=robot_text
    )


@app.route("/apply", methods=["GET", "POST"])
def apply():
    features_meta = list(zip(setting.FEATURES, setting.FEATURES_RU))
    employees = list_employees()

    if request.method == "POST":
        values = request.form.to_dict()
        try:
            missing = [key for key in setting.FEATURES if key not in values]
            if missing:
                raise ValueError(f"Отсутствуют поля модели: {', '.join(missing)}")

            feature_values = [parse_float(values[key]) for key in setting.FEATURES]
            prediction = normalize_prediction(predict(feature_values))
            requested_amount = parse_float(values.get("requested_amount"))
            offer = build_credit_offer(
                prediction["prob"],
                requested_amount,
                values.get("product_type", "consumer"),
            )

            borrower_id = upsert_borrower(values)
            employee_id = int(values.get("employee_id") or get_default_employee_id())
            features = [
                (name, label, value)
                for name, label, value in zip(setting.FEATURES, setting.FEATURES_RU, feature_values)
            ]
            application_id = create_application(
                borrower_id,
                employee_id,
                values,
                prediction,
                offer,
                features,
            )

            return render_template(
                "result.html",
                application_id=application_id,
                result=prediction,
                offer=offer,
                status_label=status_label(offer["status"]),
            )
        except Exception as exc:
            return render_template(
                "apply.html",
                features=features_meta,
                employees=employees,
                product_names=PRODUCT_NAMES,
                employment_status=EMPLOYMENT_STATUS,
                values=values,
                error=str(exc),
            ), 400

    return render_template(
        "apply.html",
        features=features_meta,
        employees=employees,
        product_names=PRODUCT_NAMES,
        employment_status=EMPLOYMENT_STATUS,
        values={},
        error=None,
    )


@app.route("/history")
def history():
    return render_template(
        "history.html",
        applications=list_applications(),
        product_names=PRODUCT_NAMES,
        status_labels=STATUS_LABELS,
    )


@app.route("/applications/<int:application_id>")
def application_detail(application_id):
    application, features = get_application(application_id)
    if application is None:
        return "Заявка не найдена", 404
    return render_template(
        "application_detail.html",
        application=application,
        features=features,
        product_names=PRODUCT_NAMES,
        status_label=status_label(application["status"]),
    )


@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        stats=get_dashboard_stats(),
        departments=list_departments(),
        employees=list_employees(),
        applications=list_applications(limit=10),
        status_labels=STATUS_LABELS,
    )


@app.route("/api/applications")
def api_applications():
    rows = list_applications()
    return jsonify([dict(row) for row in rows])


def status_label(status):
    return STATUS_LABELS.get(status, status)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/faq")
def faq():
    return render_template("FaQ.html")


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
