from flask import Flask, render_template
from sqlalchemy.exc import SQLAlchemyError

from app.config import Config, INSTANCE_DIR
from app.extensions import csrf, db
from app.models import Area, Table


def create_empty_dashboard_data():
    return {
        "total_tables": 0,
        "occupied_tables": 0,
        "empty_tables": 0,
        "general_occupancy_rate": 0,
        "area_cards": [],
        "recommended_tables": [],
    }


def build_table_view_model(table):
    return {
        "id": table.id,
        "code": table.code,
        "area_key": table.area.slug,
        "area_name": table.area.name,
        "capacity": table.capacity,
        "status": table.status,
        "customer_count": None,
        "duration": "-",
    }


def calculate_dashboard_data(tables, areas):
    active_tables = [table for table in tables if table["status"] != Table.STATUS_INACTIVE]
    occupied_tables = [
        table
        for table in active_tables
        if table["status"] in [Table.STATUS_OCCUPIED, Table.STATUS_LONG]
    ]
    empty_tables = [
        table for table in active_tables if table["status"] == Table.STATUS_EMPTY
    ]

    total_active = len(active_tables)
    occupied_count = len(occupied_tables)
    empty_count = len(empty_tables)

    general_occupancy_rate = 0

    if total_active > 0:
        general_occupancy_rate = round((occupied_count / total_active) * 100, 1)

    area_cards = []

    for area in areas:
        area_tables = [
            table
            for table in tables
            if table["area_key"] == area.slug and table["status"] != Table.STATUS_INACTIVE
        ]
        area_occupied_tables = [
            table
            for table in area_tables
            if table["status"] in [Table.STATUS_OCCUPIED, Table.STATUS_LONG]
        ]
        area_empty_tables = [
            table for table in area_tables if table["status"] == Table.STATUS_EMPTY
        ]

        area_total = len(area_tables)
        area_occupied = len(area_occupied_tables)
        area_empty = len(area_empty_tables)

        area_occupancy_rate = 0

        if area_total > 0:
            area_occupancy_rate = round((area_occupied / area_total) * 100, 1)

        area_cards.append(
            {
                "key": area.slug,
                "name": area.name,
                "total": area_total,
                "occupied": area_occupied,
                "empty": area_empty,
                "occupancy_rate": area_occupancy_rate,
            }
        )

    recommended_tables = [
        table
        for table in tables
        if table["status"] == Table.STATUS_EMPTY and table["capacity"] >= 4
    ][:6]

    return {
        "total_tables": total_active,
        "occupied_tables": occupied_count,
        "empty_tables": empty_count,
        "general_occupancy_rate": general_occupancy_rate,
        "area_cards": area_cards,
        "recommended_tables": recommended_tables,
    }


def get_dashboard_context():
    areas = Area.query.filter_by(is_active=True).order_by(Area.display_order.asc()).all()

    table_records = (
        Table.query.join(Area)
        .order_by(Area.display_order.asc(), Table.sort_order.asc())
        .all()
    )

    tables = [build_table_view_model(table_record) for table_record in table_records]
    dashboard_data = calculate_dashboard_data(tables, areas)

    return tables, dashboard_data


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
        database_not_ready = False

        try:
            tables, dashboard_data = get_dashboard_context()
        except SQLAlchemyError:
            db.session.rollback()
            tables = []
            dashboard_data = create_empty_dashboard_data()
            database_not_ready = True

        return render_template(
            "dashboard.html",
            app_name=app.config["APP_NAME"],
            tables=tables,
            dashboard_data=dashboard_data,
            database_not_ready=database_not_ready,
        )

    return app