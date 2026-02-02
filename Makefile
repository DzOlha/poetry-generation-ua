# Підняти контейнер для dev
up:
	docker compose -f docker/docker-compose.yml up -d --build

# Зайти в контейнер (з активованим Poetry virtualenv)
bash:
	docker compose -f docker/docker-compose.yml run --rm poetry bash

# Запустити пайплайн через Poetry
pipeline:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run python scripts/run_pipeline.py

# Зупинити і видалити контейнер та томи
down:
	docker compose -f docker/docker-compose.yml down --volumes --remove-orphans

# Перебудувати образ без кешу
rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache
