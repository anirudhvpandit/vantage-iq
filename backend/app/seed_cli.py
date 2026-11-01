from .database import SessionLocal
from .seed import seed_demo_data


def main() -> None:
    """Run after applying the schema with `alembic upgrade head`."""
    with SessionLocal() as db:
        seed_demo_data(db)
    print("Synthetic Northstar Industrial Services demo data is ready.")


if __name__ == "__main__":
    main()
