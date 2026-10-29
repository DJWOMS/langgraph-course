"""Долгий файл, который печатает строку о ходе работы."""

import time

for step in range(1, 5):
    time.sleep(0.25)
    print(f"step {step}", flush=True)
