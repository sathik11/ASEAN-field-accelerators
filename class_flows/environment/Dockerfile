# syntax=docker/dockerfile:1
FROM docker.io/continuumio/miniconda3:latest

WORKDIR /

COPY ./flow/requirements.txt /flow/requirements.txt

# gcc is for build psutil in MacOS
RUN apt-get update && apt-get install -y runit gcc
COPY autogen_core-0.3.dev0-py3-none-any.whl .
# create conda environment
RUN conda create -n promptflow-serve python=3.11.7 pip=23.0.1 -q -y && \
    conda run -n promptflow-serve \
    pip install -r /flow/requirements.txt && \
    conda run -n promptflow-serve pip install promptflow && \
    conda run -n promptflow-serve pip install keyrings.alt && \
    conda run -n promptflow-serve pip install gunicorn==20.1.0 && \
    conda run -n promptflow-serve pip install 'uvicorn>=0.27.0,<1.0.0' && \
    conda run -n promptflow-serve pip install autogen_core-0.3.dev0-py3-none-any.whl && \
    conda run -n promptflow-serve pip install opentelemetry-instrumentation-fastapi && \
    conda run -n promptflow-serve pip cache purge && \
    conda clean -a -y

COPY ./flow /flow


EXPOSE 8080

COPY ./connections /connections

# reset runsvdir
RUN rm -rf /var/runit
COPY ./runit /var/runit
# grant permission
RUN chmod -R +x /var/runit

COPY ./start.sh /
CMD ["bash", "./start.sh"]
