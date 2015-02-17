import logging

class Logger(object):
    def __init__(self, name=None):
        import os
        import getpass
        import tempfile

        if not name: name = ''

        user = getpass.getuser()
        tmp  = tempfile.gettempdir()

        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                            datefmt='%m-%d %H:%M',
                            filename=os.path.join(tmp, 'hafarm_%s.log' % user),
                            filemode='w')

        # define a Handler which writes INFO messages or higher to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)

        # set a format which is simpler for console use
        formatter = logging.Formatter('%(levelname)-4s: %(name)-8s: %(message)s')

        # tell the handler to use this format
        console.setFormatter(formatter)
        
        # add the handler to the root logger
        logging.getLogger(name).addHandler(console)
        self.logger = logging.getLogger(name)

    def info(self, message):
        self.logger.info(message)

    def debug(self, message):
        self.logger.debug(message)
