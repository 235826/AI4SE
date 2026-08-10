FROM python:3.11-slim

WORKDIR /workspace

COPY . .
RUN python -m pip install --no-cache-dir ".[dev,openai]"

ENTRYPOINT ["patchpilot"]
