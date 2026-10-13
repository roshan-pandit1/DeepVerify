"""Default application launcher; media/Telegram/blockchain are deliberately absent."""
import argparse
import os
import runpy

from .runtime import validate_storage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=['api', 'worker'], nargs='?', default='api')
    args = parser.parse_args()
    try:
        validate_storage()
    except ValueError as exc:
        parser.exit(1, str(exc) + '\n')
    if args.role == 'worker':
        # worker's parser should not receive the launch role argument.
        import sys
        sys.argv = [sys.argv[0]]
        runpy.run_module('investigation.worker', run_name='__main__')
    else:
        import uvicorn
        uvicorn.run('investigation.api:app', host=os.getenv('INVESTIGATION_HOST', '127.0.0.1'),
                    port=int(os.getenv('PORT', '8000')), proxy_headers=False, access_log=False)


if __name__ == '__main__':
    main()
