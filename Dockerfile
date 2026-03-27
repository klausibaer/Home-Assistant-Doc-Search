ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip
RUN pip3 install flask requests --break-system-packages

COPY run.sh /run.sh
COPY app/server.py /app/server.py
COPY app/templates/index.html /app/templates/index.html
RUN chmod +x /run.sh

WORKDIR /app
CMD ["/run.sh"]
