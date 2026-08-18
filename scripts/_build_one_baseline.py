"""Build and save numerical accuracy baseline for ONE project"""
import sys, os, json, time
sys.path.insert(0, r'D:\opensource\arch-quality\src')
from arch_quality.arch_metrics_numerical_accuracy import NumericalAccuracyMetrics

snapshot_dir = r'D:\opensource\arch-quality\tests\regression\snapshots\numerical_baselines'
os.makedirs(snapshot_dir, exist_ok=True)

project_name = sys.argv[1]
project_path = sys.argv[2]

print(f'[RUN] {project_name} @ {project_path}...', flush=True)
t0 = time.time()
m = NumericalAccuracyMetrics(project_path)
r = m.all_metrics()
elapsed = time.time() - t0
print(f'OK ({elapsed:.0f}s, overall={r["overall"]})', flush=True)

snapshot = {
    'project': project_name,
    'path': project_path,
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    'tool_version': f'guide={r["version_info"]["guide_version"]}, skill={r["version_info"]["skill_version"]}',
    'overall': r['overall'],
    'dimensions': r['dimensions'],
    'nvr_violations': [
        {'rule': v['rule'], 'output_level': v['output_level'], 'count': v['count']}
        for v in r.get('nvr_violations', [])
    ],
    'dimension_details': {},
}
for dk, dv in r['dimensions'].items():
    if dv['detail']:
        snapshot['dimension_details'][dk] = dict(dv['detail'])
        snapshot['dimension_details'][dk].pop('score', None)

snap_path = os.path.join(snapshot_dir, f'{project_name}.json')
with open(snap_path, 'w', encoding='utf-8') as f:
    json.dump(snapshot, f, ensure_ascii=False, indent=2)
print(f'saved: {snap_path}', flush=True)
