#!/usr/bin/env python3
"""Strong-scaling timings from nekRS cilia logs. Plain python (stdlib only).

    python3 scaling_timing.py <log.out>[:<ranks>] ...

Per log: steady-window wall time from nekRS's `elapsedStepSum` (steps A+1..B, default 11..99: skips
setup, the force ramp and the final checkpoint), IQN correctors in that window (`... iqn` lines:
t correctors residual capped), s/step, s/corrector, and the last `vals` ū (for the 1-GPU match check).
"""
import re, sys

A, B = 10, 99
RE_SUM = re.compile(r'^step=(\d+)\s+elapsedStep=\s*\S+s\s+elapsedStepSum=\s*(\S+)s')
RE_T = re.compile(r'^step=(\d+)\s+t=\s*(\S+)')


def one(path):
    tsum, step_t, iqn, ubar, last = {}, {}, {}, None, 0
    with open(path, errors='replace') as f:
        for line in f:
            if line.startswith('<<<'):          # par/udf echo
                continue
            if line.startswith('step='):
                m = RE_SUM.match(line)
                if m:
                    tsum[int(m.group(1))] = float(m.group(2)); last = max(last, int(m.group(1)))
                    continue
                m = RE_T.match(line)
                if m:
                    step_t[round(float(m.group(2)), 9)] = int(m.group(1))
            elif line.endswith(' iqn\n'):
                p = line.split()
                iqn[round(float(p[0]), 9)] = (int(p[1]), int(p[3]))
            elif line.endswith(' vals\n'):
                ubar = float(line.split()[1])
    if A not in tsum or B not in tsum:
        return dict(path=path, error=f'no elapsedStepSum at step {A} or {B} (last step {last})')
    cor = [iqn[t] for t, s in step_t.items() if A < s <= B and t in iqn]
    wall = tsum[B] - tsum[A]
    ncor = sum(c for c, _ in cor)
    return dict(path=path, steps=B - A, wall=wall, s_step=wall / (B - A), correctors=ncor,
                s_cor=wall / ncor if ncor else float('nan'), capped=sum(k for _, k in cor),
                setup=tsum[1], ubar=ubar, last=last)


def main():
    rows = []
    for arg in sys.argv[1:]:
        path, _, r = arg.partition(':')
        d = one(path); d['ranks'] = int(r or 1); rows.append(d)
    key = lambda d: re.sub(r'(_g\d.*)?\.out$', '', d['path'].split('/')[-1])   # tiled8_g4_c1.out -> tiled8
    base = {}
    for d in rows:
        if 'error' not in d and d['ranks'] == 1:
            base.setdefault(key(d), d)
    print(f"{'log':42s} {'GPUs':>4s} {'s/step':>8s} {'s/cor':>8s} {'cor':>5s} {'cap':>3s} {'step1 s':>8s} "
          f"{'speedup':>7s} {'eff':>5s} {'eff/cor':>7s} {'ubar':>16s} {'du/u vs 1':>9s}")
    for d in rows:
        if 'error' in d:
            print(f"{d['path']:42s} {d['ranks']:4d} {d['error']}"); continue
        b = base.get(key(d))
        sp = b['s_step'] / d['s_step'] if b else float('nan')
        spc = b['s_cor'] / d['s_cor'] if b else float('nan')
        du = abs(d['ubar'] - b['ubar']) / abs(b['ubar']) if b and d['ubar'] and b['ubar'] else float('nan')
        print(f"{d['path'][-42:]:42s} {d['ranks']:4d} {d['s_step']:8.4f} {d['s_cor']:8.4f} {d['correctors']:5d} "
              f"{d['capped']:3d} {d['setup']:8.2f} {sp:7.2f} {sp / d['ranks']:5.2f} {spc / d['ranks']:7.2f} "
              f"{d['ubar']:16.10f} {du:9.1e}")


if __name__ == '__main__':
    main()
