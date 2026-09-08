# ruff: noqa
import subprocess

proc = subprocess.Popen([
    'uv', 'run', 'python', '-m', 'harness.arena',
    '--white', '.', '--black', 'baselines/greedy',
    '--base-ms', '120000', '--increment-ms', '500'
], stdout=subprocess.PIPE)
for line in proc.stdout:
    print(line.decode('utf-8'), end='')
