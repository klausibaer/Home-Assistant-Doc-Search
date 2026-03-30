ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11
FROM $BUILD_FROM

WORKDIR /app

RUN pip3 install flask requests --break-system-packages 2>/dev/null || pip3 install flask requests

COPY app/server.py /app/server.py
COPY app/templates/index.html /app/templates/index.html

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
