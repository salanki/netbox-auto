FROM python:3.6-alpine3.7
MAINTAINER Peter Salanki <peter@salanki.st>

RUN apk add --no-cache postgresql-client postgresql-dev gcc python3-dev musl-dev

RUN mkdir -p /app
ADD requirements.txt /app
WORKDIR /app

RUN pip install -r requirements.txt

ADD . /app

CMD gunicorn --bind=0.0.0.0 netbox_serve:app
