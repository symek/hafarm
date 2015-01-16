import hafarm


class ICompFarm(hafarm.HaFarm):
    '''This small utility class calls icomp exec, which is Python wrapper around nuke comand line mode.
        icomp has a built-in old school SGE support, which we should replace with new stuff soon.'''
    def __init__(self, command=''):
        super(ICompFarm, self).__init__()
        self._exec    = '/STUDIO/scripts/icomp/icomp'
        self.command = command


    def render(self):
        from os import popen
        result = popen(self._exec + self.command).readlines()
        return result


    def join_tiles(self, job_parent_name, filename, start, end, ntiles):
        '''Creates a command specificly for merging tiled rendering.'''
        from ha.path import padding

        # Retrive full frame name (without _tile%i)
        if "_tile" in filename:
            base, rest = filename.split("_tile")
            tmp, ext   = os.path.splitext(filename)
            filename   = base + ext
        else:
            base, ext  = os.path.splitext(filename)

        details = padding(filename, format='nuke')
        base    = os.path.splitext(details[0])[0]
        reads   = [base + '_tile%s' % str(tile) + ext for tile in range(ntiles)]

        # Reads:
        command = ' '
        for read in reads:
            command += '--Read file=%s:first=%s:last=%s ' % (read, start, end)

        # Mereges:
        command += '--Merge over,0,1 ' 
        for read in range(2, len(reads)):
            command += '--Merge over,%s ' % read

        # Final touch:
        command += '--Write file=%s ' % details[0]
        command += '--globals %s,%s,24 --hold %s -f' % (start, end, job_parent_name)
        self.command = command