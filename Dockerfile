ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip
RUN pip3 install flask requests --break-system-packages

COPY run.sh /run.sh
COPY app/ /app/
RUN chmod +x /run.sh

WORKDIR /app
CMD ["/run.sh"]
