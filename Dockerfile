FROM ghcr.io/home-assistant/aarch64-base:latest

RUN apk add --no-cache python3 py3-pip py3-requests && \
    pip3 install flask --break-system-packages

WORKDIR /app
COPY app/server.py /app/server.py
COPY app/templates/index.html /app/templates/index.html
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
