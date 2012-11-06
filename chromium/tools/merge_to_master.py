#!/usr/bin/env python
#
# Copyright (C) 2012 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Merge Chromium from the master-chromium branch to the master branch within the
Android tree. See the output of --help for details.

"""
import optparse
import os
import re
import shutil
import sys

import merge_common


AUTOGEN_MESSAGE = 'This commit was generated by merge_to_master.py.'


def _MergeProjects(svn_revision):
  """Merges the Chromium projects from the tip of the master-chromium branch
  into master, flattening the history of the larger projects in the process.
  Args:
    svn_revision: The SVN revision for the main Chromium repository
  """

  for path in merge_common.PROJECTS_WITH_FLAT_HISTORY:
    dest_dir = os.path.join(merge_common.REPOSITORY_ROOT, path)
    merge_common.GetCommandStdout(['git', 'checkout',
                                   '-b', 'merge-to-master',
                                   '-t', 'goog/master'], cwd=dest_dir)
    merge_sha1 = merge_common.GetCommandStdout(['git', 'rev-parse',
                                                'goog/master-chromium'],
                                               cwd=dest_dir).strip()
    old_sha1 = merge_common.GetCommandStdout(['git', 'rev-parse', 'HEAD'],
                                             cwd=dest_dir).strip()
    # Make the previous merges into grafts so we can do a correct merge.
    merge_log = os.path.join(dest_dir, '.merged-revisions')
    if os.path.exists(merge_log):
      shutil.copyfile(merge_log,
                      os.path.join(dest_dir, '.git', 'info', 'grafts'))
    if merge_common.GetCommandStdout(['git', 'rev-list', '-1',
                                      'HEAD..' + merge_sha1], cwd=dest_dir):
      print 'Merging project %s ...' % path
      # Merge conflicts cause 'git merge' to return 1, so ignore errors
      merge_common.GetCommandStdout(['git', 'merge', '--no-commit', '--squash',
                                     merge_sha1],
                                    cwd=dest_dir, ignore_errors=True)
      dirs_to_prune = merge_common.PRUNE_WHEN_FLATTENING.get(path, [])
      if dirs_to_prune:
        merge_common.GetCommandStdout(['git', 'rm', '--ignore-unmatch', '-rf'] +
                                      dirs_to_prune, cwd=dest_dir)
      merge_common.CheckNoConflictsAndCommitMerge(
          'Merge from Chromium at DEPS revision r%s\n\n%s' %
          (svn_revision, AUTOGEN_MESSAGE), cwd=dest_dir)
      new_sha1 = merge_common.GetCommandStdout(['git', 'rev-parse', 'HEAD'],
                                               cwd=dest_dir).strip()
      with open(merge_log, 'a+') as f:
        f.write('%s %s %s\n' % (new_sha1, old_sha1, merge_sha1))
      merge_common.GetCommandStdout(['git', 'add', '.merged-revisions'],
                                    cwd=dest_dir)
      merge_common.GetCommandStdout(['git', 'commit', '-m',
                         'Record Chromium merge at DEPS revision r%s\n\n%s' %
                         (svn_revision, AUTOGEN_MESSAGE)], cwd=dest_dir)
    else:
      print 'No new commits to merge in project %s' % path

  for path in merge_common.PROJECTS_WITH_FULL_HISTORY:
    dest_dir = os.path.join(merge_common.REPOSITORY_ROOT, path)
    merge_common.GetCommandStdout(['git', 'checkout',
                                   '-b', 'merge-to-master',
                                   '-t', 'goog/master'], cwd=dest_dir)
    if merge_common.GetCommandStdout(['git', 'rev-list', '-1',
                                      'HEAD..goog/master-chromium'],
                                     cwd=dest_dir):
      print 'Merging project %s ...' % path
      # Merge conflicts cause 'git merge' to return 1, so ignore errors
      merge_common.GetCommandStdout(['git', 'merge', '--no-commit', '--no-ff',
                                     'goog/master-chromium'],
                                    cwd=dest_dir, ignore_errors=True)
      merge_common.CheckNoConflictsAndCommitMerge(
          'Merge from Chromium at DEPS revision r%s\n\n%s' %
          (svn_revision, AUTOGEN_MESSAGE), cwd=dest_dir)
    else:
      print 'No new commits to merge in project %s' % path

  return True


def _GetSVNRevision():
  print 'Getting SVN revision ...'
  commit = merge_common.GetCommandStdout([
      'git', 'log', '-n1', '--grep=git-svn-id:', '--format=%H%n%b',
      'goog/master-chromium'])
  sha1 = commit.split()[0]
  svn_revision = re.search(r'^git-svn-id: .*@([0-9]+)', commit,
                           flags=re.MULTILINE).group(1)
  return svn_revision


def _Publish(autopush):
  """Takes the current master-chromium branch of the Chromium projects in
  Android and merges them into master to publish them.
  """
  svn_revision = _GetSVNRevision()
  _MergeProjects(svn_revision)
  merge_common.PushToServer(autopush, 'merge-to-master', 'master')


def main():
  parser = optparse.OptionParser(usage='%prog [options]')
  parser.epilog = ('Takes the current master-chromium branch of the Chromium '
                   'projects in Android and merges them into master to publish '
                   'them.')
  parser.add_option(
    '', '--autopush',
    default=False, action='store_true',
    help=('Automatically push the result to the server without prompting if'
          'the merge was successful.'))
  (options, args) = parser.parse_args()
  if args:
    parser.print_help()
    return 1

  if 'ANDROID_BUILD_TOP' not in os.environ:
    print >>sys.stderr, 'You need to run the Android envsetup.sh and lunch.'
    return 1

  _Publish(options.autopush)
  return 0

if __name__ == '__main__':
  sys.exit(main())
