default:
    echo 'Hello, world!'

test:
    uv run --group test django-admin test -v 2 --settings=tests.settings

test-coverage:
    uv run --group test coverage run -m django test -v 2 --settings=tests.settings

coverage-html:
    coverage html

lint:
    uvx pre-commit run --all-files --hook-stage manual

typing:
    uv run --group test pyright

pre-commit:
    uvx pre-commit run --all-files --hook-stage manual

docs:
    cd docs && uv run --group docs sphinx-build -n -b html . _build/html
