FROM apache/airflow:3.3.1-python3.12

USER root
WORKDIR /opt/dataforge
COPY requirements.txt /tmp/dataforge-requirements.txt
RUN chown airflow:0 /tmp/dataforge-requirements.txt

USER airflow
RUN pip install --no-cache-dir -r /tmp/dataforge-requirements.txt

WORKDIR /opt/airflow
