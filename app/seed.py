from app import create_app
from app.audit import log_action
from app.extensions import db
from app.models import Area, Table


AREA_DEFINITIONS = [
    {
        "name": "Alt Bar",
        "slug": "alt",
        "prefix": "A",
        "table_count": 100,
        "display_order": 1,
    },
    {
        "name": "Üst Bar",
        "slug": "ust",
        "prefix": "U",
        "table_count": 60,
        "display_order": 2,
    },
    {
        "name": "Ana Bar",
        "slug": "ana",
        "prefix": "M",
        "table_count": 50,
        "display_order": 3,
    },
]


def get_default_capacity(table_number):
    if table_number % 10 == 0:
        return 6

    if table_number % 4 == 0:
        return 2

    return 4


def seed_area(area_definition):
    area = Area.query.filter_by(slug=area_definition["slug"]).first()

    created = False

    if area is None:
        area = Area(
            name=area_definition["name"],
            slug=area_definition["slug"],
            prefix=area_definition["prefix"],
            table_count=area_definition["table_count"],
            display_order=area_definition["display_order"],
            is_active=True,
        )
        db.session.add(area)
        created = True
    else:
        area.name = area_definition["name"]
        area.prefix = area_definition["prefix"]
        area.table_count = area_definition["table_count"]
        area.display_order = area_definition["display_order"]
        area.is_active = True

    db.session.flush()

    return area, created


def seed_tables_for_area(area):
    created_count = 0
    updated_count = 0

    for table_number in range(1, area.table_count + 1):
        table_code = f"{area.prefix}{table_number}"

        table = Table.query.filter_by(code=table_code).first()

        if table is None:
            table = Table(
                area_id=area.id,
                code=table_code,
                number=table_number,
                capacity=get_default_capacity(table_number),
                status=Table.STATUS_EMPTY,
                sort_order=table_number,
            )
            db.session.add(table)
            created_count += 1
        else:
            table.area_id = area.id
            table.number = table_number
            table.sort_order = table_number
            updated_count += 1

    return created_count, updated_count


def seed_database():
    app = create_app()

    with app.app_context():
        db.create_all()

        created_area_count = 0
        updated_area_count = 0
        created_table_count = 0
        updated_table_count = 0

        for area_definition in AREA_DEFINITIONS:
            area, area_created = seed_area(area_definition)

            if area_created:
                created_area_count += 1
            else:
                updated_area_count += 1

            area_created_tables, area_updated_tables = seed_tables_for_area(area)

            created_table_count += area_created_tables
            updated_table_count += area_updated_tables

        log_action(
            action_type="database_seed",
            target_type="database",
            target_label="initial_lido_seed",
            username_snapshot="system",
            role_snapshot="system",
            description=(
                "Lido başlangıç verileri hazırlandı. "
                f"Oluşturulan alan: {created_area_count}, "
                f"güncellenen alan: {updated_area_count}, "
                f"oluşturulan masa: {created_table_count}, "
                f"güncellenen masa: {updated_table_count}."
            ),
            extra_data={
                "created_area_count": created_area_count,
                "updated_area_count": updated_area_count,
                "created_table_count": created_table_count,
                "updated_table_count": updated_table_count,
            },
        )

        db.session.commit()

        total_area_count = Area.query.count()
        total_table_count = Table.query.count()

        print("Veritabanı hazırlandı.")
        print(f"Toplam alan sayısı: {total_area_count}")
        print(f"Toplam masa sayısı: {total_table_count}")
        print(f"Oluşturulan alan sayısı: {created_area_count}")
        print(f"Güncellenen alan sayısı: {updated_area_count}")
        print(f"Oluşturulan masa sayısı: {created_table_count}")
        print(f"Güncellenen masa sayısı: {updated_table_count}")


if __name__ == "__main__":
    seed_database()