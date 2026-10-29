"""Доступ к базе заказов."""

from config import SETTINGS


class Connection:
    def __init__(self, dsn):
        self.dsn = dsn

    def fetch(self, query):
        return [(query, SETTINGS["retries"])]


def connect(dsn):
    return Connection(dsn)
