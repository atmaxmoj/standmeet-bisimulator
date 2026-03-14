.PHONY: setup start stop status logs

setup:
	bash scripts/setup.sh

start:
	@pgrep -f "python -m capture" >/dev/null 2>&1 || { cd capture && uv run python -m capture > /tmp/bisimulator-capture.log 2>&1 & echo "capture daemon started"; }
	docker compose up -d

stop:
	docker compose down
	@pkill -f "python -m capture" 2>/dev/null && echo "capture daemon stopped" || true

status:
	@echo "--- capture daemon ---"
	@pgrep -f "python -m capture" >/dev/null 2>&1 && echo "running (pid $$(pgrep -f 'python -m capture'))" || echo "not running"
	@ls -la ~/.bisimulator/capture.db 2>/dev/null || echo "capture DB not found"
	@echo ""
	@echo "--- bisimulator engine ---"
	@docker compose ps 2>/dev/null
	@echo ""
	@curl -s http://localhost:5001/engine/status 2>/dev/null || echo "API not reachable"

logs:
	docker compose logs -f

logs-capture:
	@tail -f /tmp/bisimulator-capture.log
