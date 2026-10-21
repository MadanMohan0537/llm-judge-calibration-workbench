import argparse
import json
from pathlib import Path
import sys
import time
from .core import DEFAULT_RUBRIC, evaluate, validate_rubric
from .judges import ollama_judge
from .web import make_server
from .review import ReviewStore


def main(argv=None):
    parser = argparse.ArgumentParser(prog='verdictlens')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('evaluate')
    run.add_argument('--data', required=True)
    run.add_argument('--rubric')
    run.add_argument('--judge', choices=('mock-evidence', 'mock-length', 'ollama'), default='mock-evidence')
    run.add_argument('--model')
    run.add_argument('--out', default='report.json')
    run.add_argument('--seed', type=int, default=17)
    run.add_argument('--draws', type=int, default=500)
    web = sub.add_parser('serve')
    web.add_argument('--data', required=True)
    web.add_argument('--database', default='verdictlens.sqlite')
    web.add_argument('--port', type=int, default=8788)
    imported = sub.add_parser('import-report')
    imported.add_argument('--data', required=True)
    imported.add_argument('--report', required=True)
    imported.add_argument('--database', default='verdictlens.sqlite')
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.data).read_text())
        if args.command == 'import-report':
            report = json.loads(Path(args.report).read_text())
            store = ReviewStore(args.database)
            try:
                result = store.import_run(data, report)
            finally:
                store.close()
            print(json.dumps(result, indent=2))
            return 0
        if args.command == 'serve':
            server = make_server(data, args.database, args.port)
            print(f'VerdictLens: http://127.0.0.1:{server.server_port}', flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()
                server.store.close()
            return 0
        rubric = validate_rubric(json.loads(Path(args.rubric).read_text()) if args.rubric else DEFAULT_RUBRIC)
        if args.judge == 'ollama' and not args.model:
            raise ValueError('--model is required for Ollama; no mock fallback')
        judge = ollama_judge(args.model, rubric) if args.judge == 'ollama' else None
        start = time.perf_counter()
        report = evaluate(data, rubric, args.judge if judge is None else 'ollama:'+args.model, judge, args.seed, args.draws)
        report['execution'] = {'elapsed_seconds': time.perf_counter()-start, 'judgment_calls': len(data['pairs'])*3, 'provider_billed_cost': None, 'note': 'Local hardware/energy cost not measured; latency includes analysis.'}
        Path(args.out).write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        print(json.dumps({'report': args.out, 'summary': report['summary'], 'run_id': report['run_id']}, indent=2))
        return 0
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('VerdictLens error: '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

