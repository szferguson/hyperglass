FROM python:3.12.2-bookworm as base
WORKDIR /opt/hyperglass
ENV HYPERGLASS_APP_PATH=/etc/hyperglass
ENV HYPERGLASS_HOST=0.0.0.0
ENV HYPERGLASS_PORT=8001
ENV HYPERGLASS_DEBUG=false
ENV HYPERGLASS_DEV_MODE=false
ENV HYPERGLASS_REDIS_HOST=redis
ENV HYPEGLASS_DISABLE_UI=true

COPY . .
RUN pip3 install .


FROM base as ui
WORKDIR /opt/hyperglass/hyperglass/ui
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
RUN apt-get install -y nodejs
RUN npm install -g pnpm
RUN pnpm install -P

FROM ui as hyperglass
WORKDIR /opt/hyperglass

EXPOSE ${HYPERGLASS_PORT}
CMD ["python3", "-m", "hyperglass.console", "start"]
