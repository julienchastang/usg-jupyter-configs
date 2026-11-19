ARG BASE_CONTAINER=pangeo/base-notebook:2026.10.21
FROM $BASE_CONTAINER

LABEL maintainer="Unidata <support-gateway@unidata.ucar.edu>"

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        vim curl wget csh git \
        graphviz \
        build-essential \
        libnetcdf-dev \
        netcdf-bin && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN . /srv/conda/etc/profile.d/conda.sh && conda activate notebook && \
    mamba install -y pip dask && \
    pip install --no-cache-dir \
        distributed \
        dask-gateway \
        dask-kubernetes==2026.3.0 \
        graphviz \
        h5netcdf \
        ipywidgets \
        matplotlib \
        netcdf4 \
        numpy \
        pandas \
        pydap \
        scipy \
        siphon \
        xarray && \
    conda clean --all -f -y

ENV MPLCONFIGDIR=/home/jovyan/.mplconfig
ENV PYTHONPATH=/opt/unidata:${PYTHONPATH}
RUN mkdir -p /home/jovyan/.mplconfig \
 && chown -R jovyan:users /home/jovyan/.mplconfig

COPY unidata_dask.py /opt/unidata/unidata_dask.py
COPY ERA5_data_fetcher.ipynb Dask.ipynb wrf.ipynb Acknowledgements.ipynb /

USER $NB_UID
