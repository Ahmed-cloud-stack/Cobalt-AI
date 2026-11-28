import pickle
import sys
sys.path.insert(0, "/tests")
from verify import suite
with open("/cache-run/cases.tmp", "wb") as out:
    for case in suite():
        pickle.dump(case, out, protocol=5)
        print(case[0], flush=True)
