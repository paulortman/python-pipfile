import os
import json
from subprocess import run

from utils import mock_lockfile_update, mock_manifest_update, get_lockfile_fingerprint
from collect import collect_lockfile_dependencies


def act():
    # An actor will always be given a set of "input" data, so that it knows what
    # exactly it is supposed to update. That JSON data will be stored in a file
    # at /dependencies/input_data.json for you to load.
    with open('/dependencies/input_data.json', 'r') as f:
        input_data = json.load(f)

    for lockfile_path, lockfile_data in input_data.get('lockfiles', {}).items():
        # If "lockfiles" are present then it means that there are updates to
        # those lockfiles that you can make. The most basic way to handle this
        # is to use whatever "update" command is provided by the package
        # manager, and then commit and push the entire update. You can try to be
        # more granular than that if you want, but performing the entire "update"
        # at once is an easier place to start.

        # 1) Create a new branch off of the original commit we're working from
        branch_name = 'update-lockfile-{}-{}'.format(lockfile_path, os.getenv('JOB_ID'))
        run(['git', 'checkout', os.getenv('GIT_SHA')], check=True)
        run(['git', 'checkout', '-b', branch_name], check=True)

        # 2) Do the lockfile update
        #    Since lockfile can change frequently, you'll want to "collect" the
        #    exact update that you end up making, in case it changed slightly from
        #    the original update that it was asked to make.
        updated_lockfile_data = mock_lockfile_update(lockfile_path)
        lockfile_data['updated']['dependencies'] = collect_lockfile_dependencies(updated_lockfile_data)
        lockfile_data['updated']['fingerprint'] = get_lockfile_fingerprint(lockfile_path)

        # 3) Add and commit the changes
        run(['git', 'add', lockfile_path], check=True)
        run(['git', 'commit', '-m', 'Update ' + lockfile_path], check=True)

        if os.getenv('DEPENDENCIES_ENV') != 'test':
            # There are occasionally scenarios where you need to skip
            # certain steps if in a development or CI environment.
            # Use DEPENDENCIES_ENV to check if it is "test".
            run(['git', 'push', '--set-upstream', 'origin', branch_name], check=True)

        # 4) Shell out to `pullrequest` to make the actual pull request.
        #    It will automatically use the existing env variables and JSON schema
        #    to submit a pull request, or simulate one a test mode.
        run(
            [
                'pullrequest',
                '--branch', branch_name,
                '--dependencies-json', json.dumps({'lockfiles': {lockfile_path: lockfile_data}}),
            ],
            check=True
        )

    for manifest_path, manifest_data in input_data.get('manifests', {}).items():
        for dependency_name, dependency_data in manifest_data['current']['dependencies'].items():
            branch_name = 'update-{}-{}'.format(dependency_name, os.getenv('JOB_ID'))
            run(['git', 'checkout', os.getenv('GIT_SHA')], check=True)
            run(['git', 'checkout', '-b', branch_name], check=True)

            installed = dependency_data['installed']['name']
            version_to_update_to = dependency_data['available'][-1]['name']
            mock_manifest_update(manifest_path, dependency_name, version_to_update_to)

            run(['git', 'add', manifest_path], check=True)
            run(['git', 'commit', '-m', 'Update {} from {} to {}'.format(dependency_name, installed, version_to_update_to)], check=True)

            if os.getenv('DEPENDENCIES_ENV') != 'test':
                run(['git', 'push', '--set-upstream', 'origin', branch_name], check=True)

            # we can update the original manifest data
            if 'updated' not in manifest_data:
                manifest_data['updated'] = {}

            manifest_data['updated'] = {
                'dependencies': {
                    dependency_name: {
                        'source': dependency_data['source'],
                        'installed': {'name': version_to_update_to},
                        'constraint': version_to_update_to,
                    }
                }
            }

            # then pluck off the specific information for the dependency we're updating
            update_data = {
                'manifests': {
                    manifest_path: {
                        'current': {
                            'dependencies': {
                                dependency_name: manifest_data['current']['dependencies'][dependency_name],
                            },
                        },
                        'updated': {
                            'dependencies': {
                                dependency_name: manifest_data['updated']['dependencies'][dependency_name],
                            },
                        },
                    }
                }
            }
            run(
                [
                    'pullrequest',
                    '--branch', branch_name,
                    '--dependencies-json', json.dumps(update_data),
                ],
                check=True
            )
