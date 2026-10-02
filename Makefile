# CHIZ Booth — developer convenience targets (laptop simulator)

.PHONY: sim sim-fullscreen test seed fonts panel preview factory-test install-pi install-pi-test

# Run the kiosk UI in a 480x800 window (keyboard = booth buttons)
sim:
	.venv/bin/python -m kiosk.app

sim-fullscreen:
	.venv/bin/python -m kiosk.app --fullscreen

# Unit tests
test:
	.venv/bin/python -m pytest tests/ -q

# Seed demo products into the local DB
seed:
	.venv/bin/python scripts/seed_demo.py

# (Re)download fonts if missing
fonts:
	.venv/bin/python scripts/fetch_fonts.py

# Run the local admin panel (http://localhost:8000/admin)
panel:
	.venv/bin/python -m uvicorn admin.app:app --host 0.0.0.0 --port 8000

# Field test mode for button wiring
factory-test:
	.venv/bin/python scripts/factory_test.py

# Render every kiosk screen to data/preview/*.png (+ demo products)
preview:
	.venv/bin/python scripts/render_preview.py

# Raspberry Pi: quick try-out (no services) / full kiosk install
install-pi-test:
	bash scripts/install_pi.sh --test

install-pi:
	bash scripts/install_pi.sh
