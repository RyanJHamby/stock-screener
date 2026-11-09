set shell := ["bash", "-c"]

# check the setup (dependencies, config)
setup-check:
	python scripts/check_setup.py

# small test-mode scan to confirm everything works
scan-test:
	python run_optimized_scan.py --test-mode

# full market scan, conservative rate limits
scan:
	python run_optimized_scan.py --conservative

# local results dashboard on port 5050
dashboard:
	python dashboard.py
