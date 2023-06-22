FROM python:3.12.0b3-bullseye as builder

RUN python -m pip install poetry==1.5.1
WORKDIR /tmp/app
COPY . /tmp/app
RUN poetry build


FROM python:3.12.0b3-slim

COPY --from=builder /tmp/app/dist/ /tmp/dist
RUN python -m pip install /tmp/dist/*.whl

USER 255999
ENTRYPOINT [ "generic_k8s_webhook" ]
