from pathlib import Path

import harbor.constants

cache = Path("/workspace/scratch/harbor-cache")
harbor.constants.CACHE_DIR = cache
harbor.constants.TASK_CACHE_DIR = cache / "tasks"
harbor.constants.PACKAGE_CACHE_DIR = cache / "tasks" / "packages"
harbor.constants.DATASET_CACHE_DIR = cache / "datasets"
harbor.constants.NOTIFICATIONS_PATH = cache / "notifications.json"

from harbor.cli.main import app

app()
