import core
import prints
try:
	import WEBapp
except Exception:
	WEBapp = None
# print(resource.resource(config).show_all_version())
if __name__ == "__main__":
	print(core.core().download("release","1.21.7","挽回你"))
	# if WEBapp is not None:
	# 	WEBapp.app.run()