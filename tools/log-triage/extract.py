#!/usr/bin/env python3
"""Status of a nekRS cilia job from its SLURM .out log, as one JSON line.

Stdlib only:  python3 extract.py <job.out> [--job ID] [--summary]
Exit code = status: 0 RUNNING, 1 OK, 2 WARN, 3 FAIL, 4 STALLED, 5 QUEUED/UNKNOWN.
Test-only flags: --slurm STATE[:EXIT] (skip squeue/sacct; GONE = left the
queue with no sacct record), --age S (override seconds since last log write).
"""
import argparse, collections, json, math, os, re, subprocess, sys, time

F = r'[-+]?\d+\.\d+(?:[eE][-+]?\d+)?'
RE_STEP = re.compile(r'^step=(\d+)\s+t=\s*(\S+)\s+dt=(\S+)\s+CFL=\s*(\S+)\s*$')
RE_ELAPSED = re.compile(r'^step=(\d+)\s+elapsedStep=\s*(\S+)s\s+elapsedStepSum=\s*(\S+)s\s*$')
RE_SOLVE = re.compile(r'^step=(\d+)\s+FLUID (p|ux|uy|uz|U)\s*: iter (\d+)\s')
RE_FINISH = re.compile(r'^finished with exit code (-?\d+)$')
RE_MAXITER = re.compile(r'^cilia: .*couplingScheme = iqn .*maxIter = (\d+)')
RE_NONFINITE = re.compile(r'(?i)(?<![A-Za-z])-?(nan|inf)(?![A-Za-z])')
FATAL = [
    (re.compile(r'^Aborting in (\S+):L(\d+)$'), 'nekRS abort'),
    (re.compile(r'^Unreasonable FLUID CFL'), 'CFL blow-up'),
    (re.compile(r'^MPI_ABORT was invoked'), 'MPI_ABORT'),
    (re.compile(r'\*\*\* JOB \d+ ON \S+ CANCELLED AT \S+ DUE (?i:to) (.+?) \*\*\*'), 'SLURM cancelled'),
    (re.compile(r'^\[ERROR\] '), 'udf error'),
]
CODES = {'RUNNING': 0, 'OK': 1, 'WARN': 2, 'FAIL': 3, 'STALLED': 4, 'QUEUED': 5, 'UNKNOWN': 5}
MAX_BYTES, MAX_SUMMARY_BYTES = 4096, 8192
BEFORE, AFTER = 20, 5


def num(s):
    try:
        return float(s)
    except ValueError:
        return None


def parse(path):
    d = dict(step=None, t=None, dt=None, cfl=None, s_per_step=None, iqn_iter=None,
             iqn_maxed=0, ubar=None, vmax=None, finish=None, fatal=None, error=None)
    maxiter = 50
    prev = collections.deque(maxlen=BEFORE)
    after_left = 0
    err = []
    st = dict(s=[], iqn=[], iqn_maxed_total=0, solve={k: [] for k in ('p', 'ux', 'uy', 'uz', 'U')})
    cur_solve = {}
    with open(path, errors='replace') as fh:
        for raw in fh:
            line = raw.rstrip('\n')
            if line.startswith('<<<'):
                continue
            if after_left:
                err.append(line)
                after_left -= 1
            m = RE_ELAPSED.match(line)
            if m:
                d['step'] = int(m.group(1)); d['s_per_step'] = num(m.group(2))
                if d['s_per_step'] is not None:
                    st['s'].append(d['s_per_step'])
                for k, v in cur_solve.items():
                    st['solve'][k].append(v)
                cur_solve = {}
            elif (m := RE_STEP.match(line)):
                d['t'], d['dt'], d['cfl'] = num(m.group(2)), num(m.group(3)), num(m.group(4))
                if (d['cfl'] is None or not math.isfinite(d['cfl'])) and d['fatal'] is None:
                    d['fatal'] = 'non-finite CFL'
            elif (m := RE_SOLVE.match(line)):
                cur_solve[m.group(2)] = int(m.group(3))
            elif line.endswith('  vals') or line.endswith('  wall') or line.endswith('  iqn'):
                tok = line.split()
                if RE_NONFINITE.search(line) and d['fatal'] is None:
                    d['fatal'] = 'NaN/Inf in ' + tok[-1]
                    err = list(prev) + [line]; after_left = AFTER
                if tok[-1] == 'vals' and len(tok) == 4:
                    d['ubar'], d['vmax'] = num(tok[1]), num(tok[2])
                elif tok[-1] == 'iqn' and len(tok) == 5:
                    it = int(tok[1]); d['iqn_iter'] = it; st['iqn'].append(it)
                    if it >= maxiter:
                        d['iqn_maxed'] += 1; st['iqn_maxed_total'] += 1
                    else:
                        d['iqn_maxed'] = 0
            elif (m := RE_FINISH.match(line)):
                d['finish'] = int(m.group(1))
            elif (m := RE_MAXITER.match(line)):
                maxiter = int(m.group(1))
            elif d['fatal'] is None:
                for rx, why in FATAL:
                    if rx.search(line):
                        d['fatal'] = why
                        err = list(prev) + [line]; after_left = AFTER
                        break
            prev.append(line)
    d['error'] = err or None
    return d, st


def slurm(job, override):
    """-> (state, exit_code). state None = unknown, 'GONE' = not in queue, no sacct."""
    if override:
        s, _, e = override.partition(':')
        return s.upper(), (e or None)
    if not job:
        return None, None
    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    q = run(['squeue', '-h', '-j', job, '-o', '%T'])
    if q is None:
        return None, None
    if q:
        return q.split()[0], None
    a = run(['sacct', '-n', '-P', '-X', '-j', job, '-o', 'State,ExitCode,Elapsed,MaxRSS'])
    if a:
        f = a.splitlines()[0].split('|')
        return f[0].split()[0], (f[1] if len(f) > 1 else None)
    return 'GONE', None


def status(d, state, age, th):
    in_queue = state in ('RUNNING', 'PENDING', 'CONFIGURING', 'COMPLETING', 'SUSPENDED')
    if d['fatal']:
        return 'FAIL', d['fatal']
    if d['finish'] is not None and d['finish'] != 0:
        return 'FAIL', f"nekRS exit code {d['finish']}"
    if state in ('CANCELLED', 'TIMEOUT', 'FAILED', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE'):
        return 'FAIL', f'slurm {state}'
    if d['finish'] is None and state is not None and not in_queue:
        return 'FAIL', f'no "finished with exit code" line, job left queue ({state})'
    if state == 'RUNNING' and age is not None and age > th['stall_s']:
        return 'STALLED', f'no log write for {age:.0f} s > {th["stall_s"]}'
    warn = []
    if d['cfl'] is not None and d['cfl'] > th['cfl_warn']:
        warn.append(f"CFL {d['cfl']} > {th['cfl_warn']}")
    if d['vmax'] is not None and d['vmax'] > th['vmax_warn']:
        warn.append(f"vmax {d['vmax']:.4g} > {th['vmax_warn']}")
    if d['iqn_maxed'] >= th['iqn_maxed_warn']:
        warn.append(f"IQN at maxIter {d['iqn_maxed']} steps in a row")
    if warn:
        return 'WARN', '; '.join(warn)
    if d['finish'] == 0:
        return 'OK', 'finished with exit code 0'
    if state in ('PENDING', 'CONFIGURING'):
        return 'QUEUED', 'pending in queue'
    if in_queue:
        return 'RUNNING', 'running'
    return 'UNKNOWN', 'no slurm info and no finish line'


def stats(xs):
    return None if not xs else dict(mean=round(sum(xs) / len(xs), 4), max=max(xs), n=len(xs))


def emit(obj, cap):
    s = json.dumps(obj, separators=(',', ':'))
    while len(s.encode()) > cap and obj.get('error'):
        obj['error'] = obj['error'][1:] if len(obj['error']) > 1 else None
        s = json.dumps(obj, separators=(',', ':'))
    if len(s.encode()) > cap and obj.get('error') is None:
        obj['reason'] = (obj.get('reason') or '')[:200]
        s = json.dumps(obj, separators=(',', ':'))
    print(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log'); ap.add_argument('--job'); ap.add_argument('--summary', action='store_true')
    ap.add_argument('--slurm'); ap.add_argument('--age', type=float)
    ap.add_argument('--thresholds', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'thresholds.json'))
    a = ap.parse_args()
    with open(a.thresholds) as fh:
        th = json.load(fh)
    job = a.job or (m.group(1) if (m := re.search(r'_(\d+)\.out$', a.log)) else None)
    state, exit_code = slurm(job, a.slurm)
    if not os.path.exists(a.log):
        out = dict(job=job, status='QUEUED' if state == 'PENDING' else 'UNKNOWN',
                   reason='log not written yet', slurm_state=state, exit_code=exit_code)
        emit(out, MAX_BYTES); return CODES[out['status']]
    age = a.age if a.age is not None else time.time() - os.path.getmtime(a.log)
    d, st = parse(a.log)
    s, reason = status(d, state, age, th)
    out = dict(job=job, status=s, reason=reason, step=d['step'], t=d['t'], dt=d['dt'], cfl=d['cfl'],
               s_per_step=d['s_per_step'], iqn_iter=d['iqn_iter'], iqn_maxed=d['iqn_maxed'],
               ubar=d['ubar'], vmax=d['vmax'], slurm_state=state,
               exit_code=exit_code if exit_code is not None else d['finish'],
               last_update_age_s=round(age))
    if a.summary:
        out['summary'] = dict(s_per_step=stats(st['s']),
                              iters={k: stats(v) for k, v in st['solve'].items() if v},
                              iqn=dict(correctors=stats(st['iqn']), maxed_steps=st['iqn_maxed_total']))
        emit(out, MAX_SUMMARY_BYTES)
    else:
        if s in ('WARN', 'FAIL') and d['error']:
            out['error'] = d['error']
        emit(out, MAX_BYTES)
    return CODES[s]


if __name__ == '__main__':
    sys.exit(main())
