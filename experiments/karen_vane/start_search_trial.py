"""Select a search provider for the isolated Docker trial; never print credentials."""
import argparse
import os
import subprocess
from pathlib import Path
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('provider', choices=['tavily', 'searxng'])
    args = parser.parse_args()
    env = os.environ.copy()
    if args.provider == 'tavily' and not env.get('TAVILY_API_KEY'):
        for path in [Path('.env'), Path('.env.local'), Path('experiments/karen_vane/.env')]:
            if path.exists():
                key = dotenv_values(path).get('TAVILY_API_KEY')
                if key:
                    env['TAVILY_API_KEY'] = key
                    break
        if not env.get('TAVILY_API_KEY'):
            raise SystemExit('TAVILY_API_KEY missing')
    command = ['docker', 'compose', '-p', 'karen-vane-trial',
               '-f', 'experiments/karen_vane/compose.yaml',
               '-f', 'experiments/karen_vane/compose.patched.yaml']
    if args.provider == 'tavily':
        command += ['-f', 'experiments/karen_vane/compose.tavily.yaml']
    subprocess.run(command + ['up', '-d'], env=env, check=True)


if __name__ == '__main__':
    main()
