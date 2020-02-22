#!/usr/bin/env sh

cd $(dirname "$0")/..

docker build -t dar:test .
docker run --rm --mount type=bind,source=$(pwd),target=/repo dar:test sh -c '
  apk add gcc make musl-dev
  pip install -r /repo/requirements.dev.txt
  cd /repo
  make test'
