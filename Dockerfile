FROM python:3-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /usr/src/app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
RUN useradd --no-create-home appuser && chown -R appuser /usr/src/app
USER appuser
ENV FLASK_APP=app:create_app
EXPOSE 5000
CMD ["/usr/src/app/.venv/bin/gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:create_app()"]
