"""CLI client for the same durable API pipeline used by OneFL Studio.

No hardcoded project, direct database edits or alternate media implementation.
"""
import argparse
import asyncio
import os
import sys
import httpx


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--project-id', required=True)
    result.add_argument('--api-url', default='http://127.0.0.1:8000/api/v1')
    result.add_argument('--stage', choices=['pipeline', 'dub', 'burn', 'all'], default='all')
    result.add_argument('--voice')
    result.add_argument('--speed', type=float, default=1.)
    result.add_argument('--force-reprocess', action='store_true')
    return result


async def run(args):
    token = os.getenv('API_ACCESS_TOKEN')
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    async with httpx.AsyncClient(base_url=args.api_url.rstrip('/') + '/', headers=headers, timeout=60) as client:
        project_response = await client.get(f'projects/{args.project_id}')
        project_response.raise_for_status()
        project = project_response.json()
        stages = ['pipeline', 'dub', 'burn'] if args.stage == 'all' else [args.stage]
        for stage in stages:
            if stage == 'pipeline':
                path, data = f'projects/{args.project_id}/pipeline/trigger', {'force_reprocess': args.force_reprocess}
            elif stage == 'dub':
                path, data = f'tts/projects/{args.project_id}/dub', {'voice': args.voice or project['default_voice'], 'speed': args.speed}
            else:
                path, data = f'projects/{args.project_id}/pipeline/burn', {}
            response = await client.post(path, json=data)
            response.raise_for_status()
            job_id = response.json()['job_id']
            print(f'{stage}: queued {job_id}')
            while True:
                response = await client.get(f'projects/{args.project_id}/jobs/{job_id}')
                response.raise_for_status()
                job = response.json()
                if job['status'] in {'FAILED', 'CANCELLED'}:
                    raise RuntimeError(job['error'] or job['status'])
                if job['status'] == 'SUCCEEDED':
                    print(f'{stage}: completed')
                    break
                await asyncio.sleep(2)
        response = await client.get(f'projects/{args.project_id}')
        response.raise_for_status()
        result = response.json()
        print('Output:', result.get('burned_video_url') or result.get('dubbed_video_url') or result['status'])


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        asyncio.run(run(parser().parse_args()))
    except (httpx.HTTPError, RuntimeError) as error:
        print(f'Processing failed: {error}', file=sys.stderr)
        sys.exit(1)
