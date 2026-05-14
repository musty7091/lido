from flask import Flask, render_template

from app.config import Config, INSTANCE_DIR
from app.extensions import csrf, db


def create_demo_tables():
    tables = []

    area_definitions = [
        {
            "area_key": "alt",
            "area_name": "Alt Bar",
            "prefix": "A",
            "count": 100,
        },
        {
            "area_key": "ust",
            "area_name": "Üst Bar",
            "prefix": "U",
            "count": 60,
        },
        {
            "area_key": "ana",
            "area_name": "Ana Bar",
            "prefix": "M",
            "count": 50,
        },
    ]

    for area in area_definitions:
        for number in range(1, area["count"] + 1):
            table_code = f"{area['prefix']}{number}"

            if number % 17 == 0:
                status = "inactive"
            elif number % 11 == 0:
                status = "long"
            elif number % 3 == 0:
                status = "occupied"
            else:
                status = "empty"

            if number % 10 == 0:
                capacity = 6
            elif number % 4 == 0:
                capacity = 2
            else:
                capacity = 4

            tables.append(
                {
                    "code": table_code,
                    "area_key": area["area_key"],
                    "area_name": area["area_name"],
                    "capacity": capacity,
                    "status": status,
                    "customer_count": capacity if status in ["occupied", "long"] else None,
                    "duration": "1 sa 25 dk" if status in ["occupied", "long"] else "-",
                }
            )

    return tables


def calculate_dashboard_data(tables):
    active_tables = [table for table in tables if table["status"] != "inactive"]
    occupied_tables = [
        table for table in active_tables if table["status"] in ["occupied", "long"]
    ]
    empty_tables = [table for table in active_tables if table["status"] == "empty"]

    total_active = len(active_tables)
    occupied_count = len(occupied_tables)
    empty_count = len(empty_tables)

    general_occupancy_rate = 0
    if total_active > 0:
        general_occupancy_rate = round((occupied_count / total_active) * 100, 1)

    area_cards = []

    for area_key, area_name in [
        ("alt", "Alt Bar"),
        ("ust", "Üst Bar"),
        ("ana", "Ana Bar"),
    ]:
        area_tables = [
            table
            for table in tables
            if table["area_key"] == area_key and table["status"] != "inactive"
        ]
        area_occupied_tables = [
            table for table in area_tables if table["status"] in ["occupied", "long"]
        ]
        area_empty_tables = [table for table in area_tables if table["status"] == "empty"]

        area_total = len(area_tables)
        area_occupied = len(area_occupied_tables)
        area_empty = len(area_empty_tables)

        area_occupancy_rate = 0
        if area_total > 0:
            area_occupancy_rate = round((area_occupied / area_total) * 100, 1)

        area_cards.append(
            {
                "key": area_key,
                "name": area_name,
                "total": area_total,
                "occupied": area_occupied,
                "empty": area_empty,
                "occupancy_rate": area_occupancy_rate,
            }
        )

    recommended_tables = [
        table
        for table in tables
        if table["status"] == "empty" and table["capacity"] >= 4
    ][:6]

    return {
        "total_tables": total_active,
        "occupied_tables": occupied_count,
        "empty_tables": empty_count,
        "general_occupancy_rate": general_occupancy_rate,
        "area_cards": area_cards,
        "recommended_tables": recommended_tables,
    }


def create_app():
    app = Flask(
        __name__,
        instance_path=str(INSTANCE_DIR),
        instance_relative_config=True,
    )

    app.config.from_object(Config)

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    @app.route("/")
    def index():
        tables = create_demo_tables()
        dashboard_data = calculate_dashboard_data(tables)

        return render_template(
            "dashboard.html",
            app_name=app.config["APP_NAME"],
            tables=tables,
            dashboard_data=dashboard_data,
        )

    return app