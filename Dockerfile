FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
RUN pip install --no-cache-dir -e .
CMD ["python", "-m", "mtap.cli.run_dut"]
