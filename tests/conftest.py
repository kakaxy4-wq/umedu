"""Тесты не читают .env разработчика: с CQ_THEME=public из локального .env падали проверки семейной темы,
хотя в CI (где .env нет) всё проходило. Указываем несуществующий файл до первого импорта app.config."""
import os
from pathlib import Path

os.environ["CQ_ENV_FILE"] = str(Path(__file__).resolve().parent / "no-such.env")
