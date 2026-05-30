import os
from functools import wraps

import setting
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from model import predict
from database import (
    create_employee_account,
    create_application,
    get_connection,
    get_application,
    get_dashboard_stats,
    get_default_employee_id,
    get_user_by_id,
    get_user_by_username,
    init_db,
    list_applications,
    list_departments,
    list_employees,
    list_users,
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
ROLE_LABELS = {
    "admin": "Администратор",
    "manager": "Кредитный менеджер",
    "analyst": "Риск-аналитик",
}


def current_user():
    user_id = session.get("user_id")
    return get_user_by_id(user_id) if user_id else None


@app.context_processor
def inject_global_context():
    return {
        "current_user": current_user(),
        "role_labels": ROLE_LABELS,
        "admin_choices": admin_choices,
        "admin_models": ADMIN_MODELS,
        "status_labels": STATUS_LABELS,
        "product_names": PRODUCT_NAMES,
    }


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Войдите в систему, чтобы открыть этот раздел.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Для входа в админ-панель нужна авторизация.", "warning")
            return redirect(url_for("login", next=request.path))
        if user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def log_action(action, entity_type, entity_id=None):
    user = current_user()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (user_id, action, entity_type, entity_id)
            VALUES (?, ?, ?, ?)
            """,
            (user["id"] if user else None, action, entity_type, entity_id),
        )


def role_home_endpoint(role):
    return "admin_index" if role == "admin" else "dashboard"


ADMIN_MODELS = {
    "departments": {
        "title": "Отделы",
        "table": "departments",
        "order": "name",
        "search": ["code", "name", "description"],
        "list_columns": [
            ("id", "ID"),
            ("code", "Код"),
            ("name", "Название"),
            ("description", "Описание"),
            ("created_at", "Создано"),
        ],
        "fields": [
            {"name": "code", "label": "Код", "type": "text", "required": True},
            {"name": "name", "label": "Название", "type": "text", "required": True},
            {"name": "description", "label": "Описание", "type": "textarea"},
        ],
        "can_add": True,
        "can_edit": True,
    },
    "employees": {
        "title": "Сотрудники",
        "table": "employees",
        "list_from": "employees e JOIN departments d ON d.id = e.department_id",
        "list_select": "e.id, e.full_name, e.position, d.name AS department_name, e.email, e.phone, e.is_active",
        "order": "e.full_name",
        "search": ["e.full_name", "e.position", "e.email", "d.name"],
        "list_columns": [
            ("id", "ID"),
            ("full_name", "ФИО"),
            ("position", "Должность"),
            ("department_name", "Отдел"),
            ("email", "Email"),
            ("phone", "Телефон"),
            ("is_active", "Активен"),
        ],
        "fields": [
            {"name": "department_id", "label": "Отдел", "type": "department", "required": True},
            {"name": "full_name", "label": "ФИО", "type": "text", "required": True},
            {"name": "position", "label": "Должность", "type": "text", "required": True},
            {"name": "email", "label": "Email", "type": "email", "required": True},
            {"name": "phone", "label": "Телефон", "type": "text"},
            {"name": "is_active", "label": "Активен", "type": "boolean"},
        ],
        "can_add": True,
        "can_edit": True,
    },
    "users": {
        "title": "Пользователи",
        "table": "users",
        "list_from": "users u LEFT JOIN employees e ON e.id = u.employee_id",
        "list_select": "u.id, u.username, u.role, u.is_active, e.full_name AS employee_name, u.created_at",
        "order": "u.username",
        "search": ["u.username", "u.role", "e.full_name"],
        "list_columns": [
            ("id", "ID"),
            ("username", "Логин"),
            ("role", "Роль"),
            ("employee_name", "Сотрудник"),
            ("is_active", "Активен"),
            ("created_at", "Создан"),
        ],
        "fields": [
            {"name": "employee_id", "label": "Сотрудник", "type": "employee"},
            {"name": "username", "label": "Логин", "type": "text", "required": True},
            {"name": "password", "label": "Новый пароль", "type": "password", "password": True},
            {"name": "role", "label": "Роль", "type": "role", "required": True},
            {"name": "is_active", "label": "Активен", "type": "boolean"},
        ],
        "can_add": True,
        "can_edit": True,
    },
    "borrowers": {
        "title": "Заемщики",
        "table": "borrowers",
        "order": "full_name",
        "search": ["full_name", "email", "phone", "passport_hash"],
        "list_columns": [
            ("id", "ID"),
            ("full_name", "ФИО"),
            ("email", "Email"),
            ("phone", "Телефон"),
            ("passport_hash", "ID заемщика"),
            ("created_at", "Создан"),
        ],
        "fields": [
            {"name": "full_name", "label": "ФИО", "type": "text", "required": True},
            {"name": "email", "label": "Email", "type": "email", "required": True},
            {"name": "phone", "label": "Телефон", "type": "text", "required": True},
            {"name": "passport_hash", "label": "ID заемщика / хэш паспорта", "type": "text", "required": True},
        ],
        "can_add": True,
        "can_edit": True,
    },
    "applications": {
        "title": "Кредитные заявки",
        "table": "applications",
        "list_from": "applications a JOIN borrowers b ON b.id = a.borrower_id LEFT JOIN employees e ON e.id = a.employee_id",
        "list_select": "a.id, b.full_name, e.full_name AS employee_name, a.product_type, a.requested_amount, a.risk_probability, a.risk_level, a.status, a.created_at",
        "order": "a.created_at DESC",
        "search": ["b.full_name", "e.full_name", "a.product_type", "a.status", "a.risk_level"],
        "list_columns": [
            ("id", "ID"),
            ("full_name", "Заемщик"),
            ("employee_name", "Сотрудник"),
            ("product_type", "Продукт"),
            ("requested_amount", "Сумма"),
            ("risk_probability", "PD"),
            ("risk_level", "Риск"),
            ("status", "Статус"),
            ("created_at", "Создана"),
        ],
        "fields": [
            {"name": "employee_id", "label": "Ответственный", "type": "employee"},
            {"name": "product_type", "label": "Продукт", "type": "product", "required": True},
            {"name": "requested_amount", "label": "Запрошенная сумма", "type": "number", "required": True},
            {"name": "approved_amount", "label": "Одобренная сумма", "type": "number", "required": True},
            {"name": "interest_rate", "label": "Ставка", "type": "number", "required": True},
            {"name": "risk_probability", "label": "Вероятность дефолта", "type": "number", "required": True},
            {"name": "risk_level", "label": "Уровень риска", "type": "risk", "required": True},
            {"name": "status", "label": "Статус", "type": "status", "required": True},
            {"name": "employment_status", "label": "Занятость", "type": "employment", "required": True},
            {"name": "decision_comment", "label": "Комментарий", "type": "textarea"},
        ],
        "can_add": False,
        "can_edit": True,
    },
    "audit_log": {
        "title": "Журнал аудита",
        "table": "audit_log",
        "list_from": "audit_log l LEFT JOIN users u ON u.id = l.user_id",
        "list_select": "l.id, u.username, l.action, l.entity_type, l.entity_id, l.created_at",
        "order": "l.created_at DESC",
        "search": ["u.username", "l.action", "l.entity_type"],
        "list_columns": [
            ("id", "ID"),
            ("username", "Пользователь"),
            ("action", "Действие"),
            ("entity_type", "Сущность"),
            ("entity_id", "ID сущности"),
            ("created_at", "Дата"),
        ],
        "fields": [],
        "can_add": False,
        "can_edit": False,
    },
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


def model_config_or_404(model_name):
    config = ADMIN_MODELS.get(model_name)
    if not config:
        abort(404)
    return config


def admin_choices(field_type):
    if field_type == "department":
        return [(row["id"], row["name"]) for row in list_departments()]
    if field_type == "employee":
        return [(row["id"], row["full_name"]) for row in list_employees()]
    if field_type == "role":
        return list(ROLE_LABELS.items())
    if field_type == "status":
        return list(STATUS_LABELS.items())
    if field_type == "product":
        return list(PRODUCT_NAMES.items())
    if field_type == "employment":
        return list(EMPLOYMENT_STATUS.items())
    if field_type == "risk":
        return [("Низкий", "Низкий"), ("Средний", "Средний"), ("Высокий", "Высокий")]
    if field_type == "boolean":
        return [(1, "Да"), (0, "Нет")]
    return []


def get_admin_rows(config, query):
    table = config["table"]
    select = config.get("list_select", "*")
    source = config.get("list_from", table)
    order = config.get("order", "id DESC")
    params = []
    where = ""

    if query:
        clauses = [f"{field} LIKE ?" for field in config.get("search", [])]
        if clauses:
            where = "WHERE " + " OR ".join(clauses)
            params = [f"%{query}%"] * len(clauses)

    with get_connection() as conn:
        return conn.execute(
            f"SELECT {select} FROM {source} {where} ORDER BY {order} LIMIT 200",
            params,
        ).fetchall()


def get_admin_row(config, object_id):
    with get_connection() as conn:
        return conn.execute(
            f"SELECT * FROM {config['table']} WHERE id = ?",
            (object_id,),
        ).fetchone()


def collect_admin_form_data(config, is_edit=False):
    data = {}
    password_value = None

    for field in config["fields"]:
        name = field["name"]
        if field.get("password"):
            password_value = request.form.get(name, "")
            continue
        if field["type"] == "boolean":
            data[name] = int(request.form.get(name, "0"))
            continue
        value = request.form.get(name)
        if field.get("required") and not str(value or "").strip():
            raise ValueError(f"Поле «{field['label']}» обязательно для заполнения.")
        data[name] = value

    if config["table"] == "users" and password_value:
        data["password_hash"] = generate_password_hash(password_value)
    if config["table"] == "users" and not is_edit and not password_value:
        raise ValueError("Для нового пользователя нужно указать пароль.")

    return data


def insert_admin_object(config, data):
    columns = list(data.keys())
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO {config['table']} ({', '.join(columns)}) VALUES ({placeholders})"
    with get_connection() as conn:
        cursor = conn.execute(sql, [data[column] for column in columns])
        return cursor.lastrowid


def update_admin_object(config, object_id, data):
    if not data:
        return object_id
    assignments = ", ".join([f"{column} = ?" for column in data])
    sql = f"UPDATE {config['table']} SET {assignments} WHERE id = ?"
    with get_connection() as conn:
        conn.execute(sql, [data[column] for column in data] + [object_id])
    return object_id


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username)

        if not user or not user["is_active"] or not check_password_hash(user["password_hash"], password):
            flash("Неверный логин или пароль.", "danger")
            return render_template("login.html", username=username), 400

        session.clear()
        session["user_id"] = user["id"]
        log_action("login", "users", user["id"])
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for(role_home_endpoint(user["role"])))

    return render_template("login.html", username="")


@app.route("/logout")
def logout():
    log_action("logout", "users", session.get("user_id"))
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    departments = list_departments()
    role_options = {key: ROLE_LABELS[key] for key in ("manager", "analyst")}

    if request.method == "POST":
        values = request.form.to_dict()
        try:
            if values.get("password") != values.get("password2"):
                raise ValueError("Пароли не совпадают.")
            if values.get("role") not in role_options:
                raise ValueError("Для самостоятельной регистрации доступны роли менеджера и аналитика.")
            user_id = create_employee_account(values)
            session.clear()
            session["user_id"] = user_id
            log_action("register", "users", user_id)
            flash("Аккаунт создан. Вы вошли в личный кабинет.", "success")
            return redirect(url_for("dashboard"))
        except Exception as exc:
            return render_template(
                "register.html",
                departments=departments,
                role_options=role_options,
                values=values,
                error=str(exc),
            ), 400

    return render_template(
        "register.html",
        departments=departments,
        role_options=role_options,
        values={},
        error=None,
    )


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    employee_id = user["employee_id"]
    applications = list_applications(limit=20, employee_id=employee_id) if employee_id else []
    return render_template(
        "dashboard.html",
        stats=get_dashboard_stats(),
        applications=applications,
        product_names=PRODUCT_NAMES,
        status_labels=STATUS_LABELS,
    )


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")


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
@login_required
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
            user = current_user()
            employee_id = int(values.get("employee_id") or user["employee_id"] or get_default_employee_id())
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
                user["id"],
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
@login_required
def history():
    user = current_user()
    employee_id = None if user["role"] in ("admin", "analyst") else user["employee_id"]
    return render_template(
        "history.html",
        applications=list_applications(employee_id=employee_id),
        product_names=PRODUCT_NAMES,
        status_labels=STATUS_LABELS,
    )


@app.route("/applications/<int:application_id>")
@login_required
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
@admin_required
def admin_index():
    return render_template(
        "admin.html",
        stats=get_dashboard_stats(),
        departments=list_departments(),
        employees=list_employees(),
        users=list_users(),
        applications=list_applications(limit=10),
        status_labels=STATUS_LABELS,
        admin_models=ADMIN_MODELS,
    )


@app.route("/admin/<model_name>")
@admin_required
def admin_changelist(model_name):
    config = model_config_or_404(model_name)
    query = request.args.get("q", "").strip()
    rows = get_admin_rows(config, query)
    return render_template(
        "admin_changelist.html",
        model_name=model_name,
        config=config,
        rows=rows,
        query=query,
    )


@app.route("/admin/<model_name>/add", methods=["GET", "POST"])
@admin_required
def admin_add(model_name):
    config = model_config_or_404(model_name)
    if not config.get("can_add"):
        abort(404)

    if request.method == "POST":
        try:
            data = collect_admin_form_data(config, is_edit=False)
            object_id = insert_admin_object(config, data)
            log_action("admin_add", config["table"], object_id)
            flash("Запись добавлена.", "success")
            return redirect(url_for("admin_changelist", model_name=model_name))
        except Exception as exc:
            return render_template(
                "admin_form.html",
                model_name=model_name,
                config=config,
                row=request.form,
                mode="add",
                error=str(exc),
            ), 400

    return render_template(
        "admin_form.html",
        model_name=model_name,
        config=config,
        row={},
        mode="add",
        error=None,
    )


@app.route("/admin/<model_name>/<int:object_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit(model_name, object_id):
    config = model_config_or_404(model_name)
    if not config.get("can_edit"):
        abort(404)

    row = get_admin_row(config, object_id)
    if row is None:
        abort(404)

    if request.method == "POST":
        try:
            data = collect_admin_form_data(config, is_edit=True)
            update_admin_object(config, object_id, data)
            log_action("admin_edit", config["table"], object_id)
            flash("Изменения сохранены.", "success")
            return redirect(url_for("admin_changelist", model_name=model_name))
        except Exception as exc:
            return render_template(
                "admin_form.html",
                model_name=model_name,
                config=config,
                row=request.form,
                mode="edit",
                object_id=object_id,
                error=str(exc),
            ), 400

    return render_template(
        "admin_form.html",
        model_name=model_name,
        config=config,
        row=dict(row),
        mode="edit",
        object_id=object_id,
        error=None,
    )


@app.route("/api/applications")
@admin_required
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
