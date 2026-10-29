"""Утилиты сервиса заказов."""


def slugify(text):
    return text.strip().lower().replace(" ", "-")


def chunked(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]
