.PHONY: setup start stop status logs logs-capture logs-audio

setup:
	bash scripts/setup.sh

start:
	@pgrep -f "python -m capture" >/dev/null 2>&1 || { cd capture && uv run python -m capture > /tmp/bisimulator-capture.log 2>&1 & echo "capture daemon started"; }
	@pgrep -f "python -m audio" >/dev/null 2>&1 || { cd audio && uv run python -m audio > /tmp/bisimulator-audio.log 2>&1 & echo "audio daemon started"; }
	docker compose up -d

stop:
	docker compose down
	@pkill -f "python -m capture" 2>/dev/null && echo "capture daemon stopped" || true
	@pkill -f "python -m audio" 2>/dev/null && echo "audio daemon stopped" || true

status:
	@echo "--- capture daemon ---"
	@pgrep -f "python -m capture" >/dev/null 2>&1 && echo "running (pid $$(pgrep -f 'python -m capture'))" || echo "not running"
	@ls -la ~/.bisimulator/capture.db 2>/dev/null || echo "capture DB not found"
	@echo ""
	@echo "--- audio daemon ---"
	@pgrep -f "python -m audio" >/dev/null 2>&1 && echo "running (pid $$(pgrep -f 'python -m audio'))" || echo "not running"
	@echo ""
	@echo "--- bisimulator engine ---"
	@docker compose ps 2>/dev/null
	@echo ""
	@curl -s http://localhost:5001/engine/status 2>/dev/null || echo "API not reachable"

logs:
	docker compose logs -f

logs-capture:
	@tail -f /tmp/bisimulator-capture.log

logs-audio:
	@tail -f /tmp/bisimulator-audio.log
