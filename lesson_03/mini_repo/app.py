"""Точка входа выдуманного сервиса заказов."""

from config import SETTINGS
from db import connect


def main():
    connection = connect(SETTINGS["dsn"])
    return connection.fetch("select count(*) from orders")


if __name__ == "__main__":
    print(main())
