# 適合試験の分割と集約を実行するCI用のイメージ（ADR-069）。
# GitHub の runner のイメージが入れ替わっても、分割の間で Python・uv・Git の版が一致するようにする。
# 版は次の3つで固定し、CI は push したイメージを digest で参照する。版を上げるときは、
# この定義と ci.yml の digest を同じ PR で更新し、Core の単体試験・適合試験・Gate A/B を通す。
FROM ubuntu:24.04@sha256:24737cef17f4e22b1977df7d9a05e77c4e28b7da5b8911f8d8ccda136bf3573c

ARG UV_VERSION=0.11.28
ARG PYTHON_VERSION=3.12.13

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

ADD --checksum=sha256:e490a6464492183c5d4534a5527fb4440f7f2bb2f228162ad7e4afe076dc0224 \
    https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz /tmp/uv.tar.gz
RUN tar -xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 \
    && rm /tmp/uv.tar.gz \
    && uv --version

# Python は焼き込んだものだけを使い、実行時にダウンロードしない。
ENV LANG=C.UTF-8 \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PYTHON=${PYTHON_VERSION}
RUN uv python install "${PYTHON_VERSION}" \
    && uv run --no-project python --version
ENV UV_PYTHON_DOWNLOADS=never
