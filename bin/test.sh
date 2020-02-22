#!/usr/bin/env sh

exit=0

checked() {
  echo "$ $@"
  "$@"
  last="$?"
  if [ "$last" -ne 0 ]; then
    echo "$@: exit $last"
    exit=1
  fi
}

cd $(dirname "$0")/..

checked pytest --cov dar
checked black --check dar.py stubs test_dar.py
checked flake8 dar.py test_dar.py
checked env MYPYPATH=stubs mypy --strict dar.py

exit "$exit"
