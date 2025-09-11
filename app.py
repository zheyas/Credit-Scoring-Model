import setting
from flask import Flask, render_template, request, jsonify
from model import predict

app = Flask(__name__)

forms_label = setting.FEATURES_RU


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
                        text = raw_result.get("result") or raw_result.get("text") or str(raw_result)
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
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/faq")
def faq():
    return render_template("FaQ.html")


if __name__ == "__main__":
    app.run(debug=True)