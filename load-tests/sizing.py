#!/usr/bin/env python3
"""Conservative E fallback after the original half-CPU workload hit dropped-iteration safety stop."""
import argparse
import bench

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats',type=int,default=3,choices=[1,2,3])
    args=parser.parse_args()
    for size in ['half','one','two']:
        bench.bringup(size)
        for config in [bench.config('A',10),bench.config('B',5),bench.config('D',20,5,100,label='D-100')]:
            for repeat in range(1,args.repeats+1):
                result=bench.run(config,size,repeat)
                if result['safety_abort'] or result['status']=='FAIL' or result['outcomes']['dropped_iterations']:
                    raise RuntimeError('Stop: lower sizing schedule is not safe: '+result['id'])
    bench.verify_demo()

if __name__=='__main__': main()
