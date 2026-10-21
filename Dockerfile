FROM python:3.15-slim-bookworm AS builder

RUN python -m pip install poetry==2.5.1
WORKDIR /tmp/app
COPY . /tmp/app
RUN poetry build


FROM python:3.15-slim-bookworm

COPY --from=builder /tmp/app/dist/ /tmp/dist
RUN python -m pip install /tmp/dist/*.whl
# Check the binary is available
RUN generic_k8s_webhook --help

USER 255999
ENTRYPOINT [ "generic_k8s_webhook" ]
