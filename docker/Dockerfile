FROM python:3.13-slim

# Основні пакети
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Робоча папка
WORKDIR /app

# Встановлюємо Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Копіюємо тільки залежності для кешування
COPY pyproject.toml poetry.lock ./

# Встановлюємо залежності через Poetry (venv поза /app, щоб bind-mount не затирав)
ENV POETRY_VIRTUALENVS_IN_PROJECT=false \
    POETRY_VIRTUALENVS_PATH=/opt/venv
RUN poetry install --no-root --no-interaction --no-ansi

# Копіюємо весь код
COPY . .

# Вхідна точка
ENTRYPOINT ["bash", "docker/entrypoint.sh"]
