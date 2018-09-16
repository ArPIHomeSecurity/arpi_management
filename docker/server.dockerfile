FROM debian:stretch

RUN apt-get update && apt-get -y install \
  python-virtualenv \
  python3-dev \
  python3-gi \
  python3 \
  gcc \
  netbase

WORKDIR /root/server

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

ADD server/src ./src
ADD server/scripts ./scripts
ADD server/etc/*.dev.* ./etc/
ADD docker/secrets.env ./etc/
ADD server/requirements.txt ./

RUN bash -c "source etc/common.dev.env && ./scripts/install.sh dev"

ADD webapplication/dist-development /root/webapplication/dist-development

CMD ./scripts/start_server.sh dev