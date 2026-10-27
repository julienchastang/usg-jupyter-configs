ARG BASE_CONTAINER=unidata/unidata-standard:2026Aug13_175701_dfae
FROM $BASE_CONTAINER

ENV DEFAULT_ENV_NAME=fsu26f \
    EDITOR=nano \
    VISUAL=nano

LABEL maintainer="Unidata <support-gateway@unidata.ucar.edu>"

COPY environment.yaml /tmp/cluster_environment.yaml
RUN mamba env update \
      -n unidata-standard \
      -f /tmp/cluster_environment.yaml && \
    mamba clean --all -f -y && \
    conda rename -n unidata-standard $DEFAULT_ENV_NAME
