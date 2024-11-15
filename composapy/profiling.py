from loader import load_init
import cProfile
cProfile.run("load_init()", "loader.prof")
