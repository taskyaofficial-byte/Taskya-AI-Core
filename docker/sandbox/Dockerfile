FROM python:3.11-slim
RUN useradd -m -u 10001 agent
WORKDIR /workspace
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
USER agent
CMD ["python","-c","print('AagyaAI sandbox ready')"]
