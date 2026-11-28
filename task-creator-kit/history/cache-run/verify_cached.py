import pickle
import sys
sys.path.insert(0, "/tests")
import verify

with open("/cache-ro/cases.bin", "rb") as cache:
    def cases():
        while True:
            try:
                yield pickle.load(cache)
            except EOFError:
                return

    verify.suite = cases
    sys.exit(verify.main())
