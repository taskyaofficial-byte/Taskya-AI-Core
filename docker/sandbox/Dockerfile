FROM python:3.11-slim
RUN useradd -m runner
USER runner
WORKDIR /work
RUN pip install --no-cache-dir pandas openpyxl matplotlib reportlab pypdf
ENTRYPOINT ["python"]
