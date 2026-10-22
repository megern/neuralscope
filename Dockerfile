FROM python:3.12-alpine@sha256:92abd2ba1bdfb48b1e2ac224b582dd1558d0d4bb11c903b126b5bf9c448fd656 AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
RUN apk add --no-cache build-base=0.5-r4 ninja-build=1.13.2-r1 ninja-is-really-ninja=1.13.2-r1
WORKDIR /build
COPY requirements.lock requirements-build.lock ./
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-build.lock
RUN pip wheel --no-cache-dir --no-build-isolation --no-deps --require-hashes --only-binary=:all: --no-binary=scikit-learn --config-settings=compile-args=-j2 --wheel-dir /wheels -r requirements.lock
COPY tools/build_wheel_lock.py /build/build_wheel_lock.py
RUN python /build/build_wheel_lock.py /wheels

FROM python:3.12-alpine@sha256:92abd2ba1bdfb48b1e2ac224b582dd1558d0d4bb11c903b126b5bf9c448fd656
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
RUN apk add --no-cache libgomp=15.2.0-r5 libstdc++=15.2.0-r5
WORKDIR /service
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels --require-hashes -r /wheels/built-requirements.lock && cp /wheels/built-requirements.lock /service/built-requirements.lock && rm -rf /wheels && python -m pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip && adduser -D -u 10001 runner
COPY app ./app
USER runner
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD ["/bin/busybox", "wget", "-q", "-T", "3", "-O", "/dev/null", "http://127.0.0.1:8000/health"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "16"]
