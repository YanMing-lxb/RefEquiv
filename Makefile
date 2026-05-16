.PHONY: clean build

UV_RUN = @uv run python

clean:
	$(UV_RUN) tools/pack.py --clean

build: clean
	$(UV_RUN) tools/pack.py
