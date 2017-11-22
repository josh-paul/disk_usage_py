import argparse
import datetime
import operator
import os
import sys

from dotted_dict import DottedDict
from . import utils


units = utils.UnitConverter()


class DiskUsage(object):
    def __init__(self, target):
        self._activity = ''
        self._dirs_holder = {}
        self.dir_count = 0
        self.dirs = []
        # A list of root level directores to ignore as do not contain traditional files
        self.exclude_root_dirs = ['dev', 'proc', 'selinux']
        self.file_count = 0
        self.files = []
        self.partition = DottedDict({})
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

    def _remove_activity(self):
        '''
        Clean up stdout.
        '''
        sys.stdout.write('\r')
        sys.stdout.write('')
        sys.stdout.flush()
        del self._activity

    def _show_activity(self):
        '''
        Every 5000 files, add a . to stdout to show program is still running.
        '''
        if len(self._activity) == 5:
            self._activity = ''
        if self.file_count % 5000 == 0:
            self._activity = '{0}.'.format(self._activity)
            sys.stdout.write('\r')
            sys.stdout.write(self._activity)
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
        for root, dirs, files in os.walk(target):
            dirs = self._filter_dirs(root, dirs)
            for name in files:
                filename = os.path.join(root, name)
                file_data = self._get_file_data(filename)
                self.file_count += 1
                self._show_activity()
                self._process_files(file_data)
                self._add_up_dir(root, file_data)
        self._remove_activity()
        self._sort_dirs()


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


def calculate_percent(free, total):
    '''
    Calculate percentage of free resource.
    '''
    return round((float(free) / float(total) * 100), 2)


def format_dirs_output(output, disk):
    '''
    Add the dirs info to the output list.
    '''
    output.append('Total directory count of {0}'.format(disk.dir_count))
    output.append('The {0} largest directories are:\n'.format(len(disk.dirs)))
    for item in disk.dirs:
        output.append('{0}{1}'.format(units.to_human_readable(item.size).ljust(9), item.name))
    return output


def format_files_output(output, disk):
    '''
    Add files information to output list.
    '''
    output.append('\nTotal file count of {0}'.format(disk.file_count))
    output.append('The {0} largest files are:\n'.format(len(disk.files)))
    output.append('{0}{1}File'.format('Size'.ljust(9), 'Modified'.ljust(20)))

    for item in disk.files:
        output.append(
            '{0}{1} {2}'.format(
                units.to_human_readable(item.size).ljust(9),
                datetime.datetime.fromtimestamp(item.modified),
                item.name
            )
        )
    return output


def format_partition_output(output, disk, target):
    '''
    Build the partition information of the output in the output list.
    '''
    output.append(
        '{0}% available disk space on {1}'.format(
            calculate_percent(disk.partition.free, disk.partition.total), target
        )
    )
    output.append(
        'Total: {0}\tUsed: {1}\tFree: {2}\n'.format(
            units.to_human_readable(disk.partition.total),
            units.to_human_readable(disk.partition.used),
            units.to_human_readable(disk.partition.free)
        )
    )
    output.append(
        '{0}% of Total Inodes are free.'.format(
            calculate_percent(disk.partition.inodes_free, disk.partition.inodes_total)
        )
    )
    output.append(
        'Total Inodes: {0}\tUsed: {1}\tFree: {2}\n'.format(
            disk.partition.inodes_total, disk.partition.inodes_used, disk.partition.inodes_free
        )
    )
    return output


def format_output(disk, target):
    '''
    Generate the output in list form.
    '''
    output = []
    output = format_partition_output(output, disk, target)
    output = format_dirs_output(output, disk)
    output = format_files_output(output, disk)
    return output


def cli():
    args = arguments()
    disk = DiskUsage(args.target)
    output = format_output(disk, args.target)
    print('\n'.join(output))
