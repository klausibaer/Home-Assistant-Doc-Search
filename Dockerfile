FROM python:3.11-alpine

WORKDIR /app

RUN pip install flask requests

COPY app/server.py /app/server.py
COPY app/templates/index.html /app/templates/index.html
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
