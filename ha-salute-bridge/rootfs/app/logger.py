from abc import ABC
import logging

class Logger(ABC):
    @classmethod
    def init(cls, options):
        logging.basicConfig(
            level=options['log_level'].upper(),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers = [
                logging.StreamHandler()
            ],
        )
        logging.getLogger("hass_client").propagate = False
        logging.info('logger start')