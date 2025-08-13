import core
import prints
try:
	import gui
except Exception:
	gui = None

if __name__ == "__main__":
	if gui is not None:
		gui.main()
	else:
		# CLI fallback: simple one-shot download example
		print(core.core().download("release","1.21.7","挽回你"))