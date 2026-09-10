.PHONY: help doctor test demo preview
help:
	@./ambiance --help

doctor:
	@./ambiance doctor

test:
	@./ambiance test

demo:
	@./ambiance project init projects/last-lantern --template last-lantern --title "The Last Lantern"

preview:
	@./ambiance --project projects/last-lantern preview
