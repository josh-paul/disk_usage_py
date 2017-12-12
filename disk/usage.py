import argparse
import datetime
import operator
import os
import sys

from . import utils
from dotted_dict import DottedDict
from progress.spinner import Spinner


units = utils.UnitConverter()


class DiskUsage(object):
    def __init__(self, target):
        self._dirs_holder = {}
        self.dir_count = 0
        self.dirs = []
        # A list of root level directores to ignore as do not contain traditional files
        self.exclude_root_dirs = ['dev', 'proc', 'selinux']
        self.file_count = 0
        self.files = []
        self.partition = DottedDict({})
        self.target = target
        # Exec data gathering for the object
        self._get_partition_usage(target)
        self._walk_filesystem(target)

    def _add_up_dir(self, root, file_data):
        '''
        Compute the total size of the directories, helper function to add files size to dirs.
        '''
        if root in self._dirs_holder:
            self._dirs_holder[root] += file_data.size
        else:
            self._dirs_holder[root] = file_data.size

    def _filter_dirs(self, root, dirs):
        '''
        Filter out mounts and excluded root level dirs.
        '''
        # Ignore mounts
        dirs[:] = filter(lambda dir: not os.path.ismount(os.path.join(root, dir)), dirs)
        # Filter system directories that do not contain pertinent files
        if root is '/':
            dirs[:] = filter(lambda dir: dir not in self.exclude_root_dirs, dirs)
        return dirs

    def _get_file_data(self, filename):
        '''
        Get file metadata and assemble dotted dict object containing filename, size, and
        modified time.
        '''
        file_data = DottedDict({})
        # Test for broken symlinks
        try:
            file_stat = os.stat(filename)
            file_data.name = filename
            file_data.modified = file_stat.st_mtime
            file_data.size = float(file_stat.st_size)
        except OSError:
            file_data.size = 0
        return file_data

    def _get_partition_usage(self, target):
        '''
        Get total, used, and free space at the target location's partition/mount
        '''
        st = os.statvfs(target)
        self.partition.free = st.f_bavail * st.f_frsize
        self.partition.total = st.f_blocks * st.f_frsize
        self.partition.used = (st.f_blocks - st.f_bfree) * st.f_frsize
        self.partition.inodes_free = st.f_favail
        self.partition.inodes_total = st.f_files
        self.partition.inodes_used = st.f_files - st.f_favail

    def _process_files(self, file_data):
        '''
        Processes and sorts the filelist to keep the data set at the largest 20
        files.  This is for performance reasons.  By keeping a pruned data set, we
        do not face the penalties of extremely large ordered data sets in memory.
        '''
        self.files.append(file_data)
        self.files = self._sort_files_list()
        if len(self.files) >= 21:
            self.files.pop()

    def _show_activity(self, spin):
        '''
        Every 5000 files, add a . to stdout to show program is still running.
        '''
        if self.file_count % 5000 == 0:
            spin.next()
            sys.stdout.write('\r')
            sys.stdout.flush()

    def _sort_files_list(self):
        '''
        Sort self.files by the size.
        '''
        return sorted(self.files, key=lambda item: item.size, reverse=True)

    def _sort_dirs(self):
        '''
        Populate self.dirs with the 10 largest dirs.
        '''
        for k, v in sorted(self._dirs_holder.items(), key=operator.itemgetter(1), reverse=True):
            self.dirs.append(DottedDict({'name': k, 'size': v}))
        del self._dirs_holder
        self.dir_count = len(self.dirs)
        self.dirs = self.dirs[0:10]

    def _walk_filesystem(self, target):
        '''
        Get file size and modified time for all files from the target directory and
        down.
        '''
        spin = Spinner()
        spin.hide_cursor = False
        for root, dirs, files in os.walk(target):
            dirs = self._filter_dirs(root, dirs)
            for name in files:
                filename = os.path.join(root, name)
                file_data = self._get_file_data(filename)
                self.file_count += 1
                self._show_activity(spin)
                self._process_files(file_data)
                self._add_up_dir(root, file_data)
        self._sort_dirs()


class ReportSTDOUT(object):
    def __init__(self, **kwargs):
        self.dir_count = kwargs['dir_count']
        self.dirs = kwargs['dirs']
        self.file_count = kwargs['file_count']
        self.files = kwargs['files']
        self.partition = kwargs['partition']
        self.stdout_report = []
        # Populate output
        self._format_partition_output(kwargs['target'])
        self._format_dirs_output()
        self._format_files_output()

    def _format_dirs_output(self):
        '''
        Add the dirs info to the output list.
        '''
        self.stdout_report.append('Total directory count of {0}'.format(self.dir_count))
        self.stdout_report.append('The {0} largest directories are:\n'.format(len(self.dirs)))
        for item in self.dirs:
            self.stdout_report.append(
                '{0}{1}'.format(units.to_human_readable(item.size).ljust(9), item.name)
            )

    def _format_files_output(self):
        '''
        Add files information to output list.
        '''
        self.stdout_report.append('\nTotal file count of {0}'.format(self.file_count))
        self.stdout_report.append('The {0} largest files are:\n'.format(len(self.files)))
        self.stdout_report.append('{0}{1}File'.format('Size'.ljust(9), 'Modified'.ljust(20)))

        for item in self.files:
            self.stdout_report.append(
                '{0}{1} {2}'.format(
                    units.to_human_readable(item.size).ljust(9),
                    datetime.datetime.fromtimestamp(item.modified),
                    item.name
                )
            )

    def _format_partition_output(self, target):
        '''
        Build the partition information of the output in the output list.
        '''
        self.stdout_report.append(
            '{0}% available disk space on {1}'.format(
                self.calculate_percent(self.partition.free, self.partition.total), target
            )
        )
        self.stdout_report.append(
            'Total: {0}\tUsed: {1}\tFree: {2}\n'.format(
                units.to_human_readable(self.partition.total),
                units.to_human_readable(self.partition.used),
                units.to_human_readable(self.partition.free)
            )
        )
        self.stdout_report.append(
            '{0}% of Total Inodes are free.'.format(
                self.calculate_percent(self.partition.inodes_free, self.partition.inodes_total)
            )
        )
        self.stdout_report.append(
            'Total Inodes: {0}\tUsed: {1}\tFree: {2}\n'.format(
                self.partition.inodes_total, self.partition.inodes_used, self.partition.inodes_free
            )
        )

    def calculate_percent(self, free, total):
        '''
        Calculate percentage of free resource.
        '''
        return round((float(free) / float(total) * 100), 2)


def arguments():
    '''
    Parse the args.
    '''
    parser = argparse.ArgumentParser(
        description='Utility to gather disk usage information from a target location and down.'
    )

    parser.add_argument(metavar='TARGET', action='store', dest='target', type=str)

    args = parser.parse_args()

    if not args.target:
        print('You must supply filesystem location to start from.')
        parser.print_help()
        sys.exit(1)
    return args


def cli():
    args = arguments()
    disk = DiskUsage(args.target)
    print('\n'.join(ReportSTDOUT(**disk.__dict__).stdout_report))
