.PHONY: clean build upload

UV_RUN = @uv run python
TOOLS_DIR = ./tools

clean:
	$(UV_RUN) tools/pack.py --clean

pack: clean
	$(UV_RUN) tools/pack.py

# 上传标签
upload:
	$(UV_RUN) $(TOOLS_DIR)/make.py upload
