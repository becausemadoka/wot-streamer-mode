# -*- coding: utf-8 -*-
"""Re-extract client bytecode fixtures from the INSTALLED client.

The test suites (notably test_real_client.py) load real client classes from
_wot/extracted/*.pyc rather than importing them, so they can run outside the
game.  Those fixtures are snapshots: after the client updates they are stale and
must be refreshed, or the tests are validating the OLD client and will happily
pass while the shipped mod is already incompatible.

Run this after every client update, before trusting the test suite:

    py -2.7 refresh_fixtures.py                      # uses $WOT_GAME
    py -2.7 refresh_fixtures.py "D:\Games\<your WoT>"

The client path comes from the WOT_GAME environment variable; there is no
built-in default because the install location and the region-specific folder
name differ per machine.

It only writes under _wot/extracted/ and never touches the game install.
Note: it prints before/after sizes so a silent "file unchanged" is visible.
"""
from __future__ import print_function

import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GAME = None
OUT_DIR = os.path.join(os.path.dirname(HERE), '_wot', 'extracted')

# module path inside scripts.pkg  ->  flat filename the tests expect
FIXTURES = {
    'scripts/client/gui/battle_control/arena_info/arena_vos.pyc': 'arena_vos.pyc',
    'scripts/client/gui/battle_control/arena_info/player_format.pyc': 'player_format.pyc',
    'scripts/client/gui/battle_results/reusable/players.pyc': 'players.pyc',
    'scripts/client/gui/battle_results/reusable/avatars.pyc': 'avatars.pyc',
    'scripts/client/gui/battle_results/components/vehicles.pyc': 'vehicles.pyc',
    'scripts/client/gui/battle_results/components/shared.pyc': 'br_shared.pyc',
    'scripts/client/gui/battle_results/presenters/packers/user_info.pyc': 'user_info.pyc',
    'scripts/client/gui/battle_results/templates/regular.pyc': 'br_regular.pyc',
    'scripts/client/gui/battle_results/components/base.pyc': 'br_base.pyc',
    'scripts/client/gui/Scaleform/daapi/view/battle/shared/stats_exchange/vehicle.pyc': 'vehicle.pyc',
    'scripts/client/gui/Scaleform/daapi/view/battle/shared/postmortem_panel.pyc': 'postmortem_panel.pyc',
    'scripts/client/gui/impl/battle/battle_page/tab_view.pyc': 'tab_view.pyc',
    'scripts/client/gui/Scaleform/daapi/view/lobby/profile/ProfileWindow.pyc': 'ProfileWindow.pyc',
    'scripts/client/gui/doc_loaders/badges_loader.pyc': 'badges_loader.pyc',
    'scripts/client/gui/shared/badges.pyc': 'shared_badges.pyc',
    'scripts/client/gui/lobby_context.pyc': 'lobby_context.pyc',
    'scripts/client/helpers/__init__.pyc': 'helpers_init.pyc',
    'scripts/client/gui/mods/__init__.pyc': 'mods_init.pyc',
    'scripts/client/gui/Scaleform/daapi/view/battle/classic/player_menu_handler.pyc': 'battle_player_menu_handler.pyc',
}


def main(argv):
    game = argv[1] if len(argv) > 1 else os.environ.get('WOT_GAME')
    if not game:
        print('ERROR: no client path given.\n'
              '  Pass it as an argument, or set WOT_GAME:\n'
              '    py -2.7 refresh_fixtures.py "D:\\Games\\World_of_Tanks_XX"\n'
              '    set WOT_GAME=D:\\Games\\World_of_Tanks_XX')
        return 2
    pkg = os.path.join(game, 'res', 'packages', 'scripts.pkg')
    if not os.path.isfile(pkg):
        print('ERROR: scripts.pkg not found: %s' % pkg)
        return 1
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    version_xml = os.path.join(game, 'version.xml')
    if os.path.isfile(version_xml):
        raw = open(version_xml, 'rb').read().decode('utf-8', 'replace')
        for line in raw.splitlines():
            if '<version>' in line:
                print('client version: %s' % line.strip())
                break

    z = zipfile.ZipFile(pkg)
    names = set(z.namelist())
    missing, written = [], 0
    for src, flat in sorted(FIXTURES.items()):
        if src not in names:
            missing.append(src)
            continue
        data = z.read(src)
        if data[:4] != b'\x03\xf3\r\n':
            print('  WARN %-28s not a 2.7 pyc (magic %r)' % (flat, data[:4]))
        dest = os.path.join(OUT_DIR, flat)
        old_len = os.path.getsize(dest) if os.path.isfile(dest) else -1
        with open(dest, 'wb') as fh:
            fh.write(data)
        written += 1
        print('  %-28s %7d -> %7d bytes' % (flat, old_len, len(data)))

    print('\n%d fixtures refreshed into %s' % (written, OUT_DIR))
    if missing:
        print('%d module(s) no longer present in this client:' % len(missing))
        for m in missing:
            print('  MISSING %s' % m)
        print('If a missing one is a hook target, the mod needs updating for this version.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
