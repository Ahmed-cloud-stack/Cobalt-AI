import sys
from pathlib import Path
import runpy
import random
BASE=Path('/workspace/scratch/shutter-panels-final')
sys.path.insert(0,str(BASE/'frozen-task/tests'))
from dense import dense
from verify import comparison
codes={'ref':runpy.run_path(str(BASE/'frozen-task/solution/reference.py'))['render']}
for index in (1,2,3,4,5):
    codes[index]=runpy.run_path(str(BASE/f'sealed/{index}/shutter.py'))['render']
for seed in range(18):
    rng=random.Random(8052 + seed)
    rows=[]
    start=-10**18
    for i in range(8):
        end=start + (i+1)*((seed+1)*10**5 if seed%2 else 1)
        center=-80 if seed%3 else 90
        sd=[1.,1.3,2.0,.001,1.1,1.2,2.4,1.9][i]
        loading=(4 - 10**(-5-seed%5)*rng.random())*(1 if (i%2) else -1)
        g=4 - 10**(-4-seed%4)*rng.random()
        offset=.05
        row=dict(start=start if (i<=4 and seed%6==0) else end,end=end,gain=g,bias_loading=loading,sd=sd,
                 offset=offset,value=center+offset+.001*rng.random(),audit=True,sensitivity=i%2==0)
        if i!=3:row['panel']='left' if i%2 else 'right'
        rows.append(row)
    rng.shuffle(rows)
    request=dict(parameters=dict(rate=1e-18,signal_variance=10000,bias_variance=10000,noise_scale=.01),rows=rows)
    expected=dense(request)
    if any(abs(r['value']-f['mean'])>128*f['variance']**.5 for r,f in zip(rows,expected['forecasts'])): continue
    print(seed,[(k,comparison(solve(request),expected)) for k,solve in codes.items()],flush=True)
