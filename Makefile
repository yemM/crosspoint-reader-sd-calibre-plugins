.PHONY: zip install clean test

PLUGIN_DIR = calibre_crosspoint
PLUGIN_ZIP = crosspoint_plugin.zip

# Build the plugin ZIP (Calibre loads plugins from ZIP files)
zip:
	rm -f $(PLUGIN_ZIP)
	cd $(PLUGIN_DIR) && zip -r ../$(PLUGIN_ZIP) . --exclude "*.pyc" --exclude "__pycache__/*" --exclude "*.DS_Store"
	@echo "Built: $(PLUGIN_ZIP)"

# Install the plugin into the local Calibre instance
install: zip
	calibre-customize -a $(PLUGIN_ZIP)
	@echo "Installed. Run 'make debug' to launch Calibre with debug output."

# Launch Calibre with debug output
debug:
	calibre-debug -g

# Remove build artifacts
clean:
	rm -f $(PLUGIN_ZIP)
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# Run unit tests (requires pytest)
test:
	python -m pytest tests/ -v
