import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

import numpy as np

from runtime_status import read_status, serve_status, write_status
from vision_setup import VISION_SETUPS
from plotter2d import BoardPlotter2D


class StatusMetadataTests(unittest.TestCase):
    def test_every_setup_is_portable_and_reconstructs_board(self):
        for name, setup in VISION_SETUPS.items():
            metadata = json.loads(json.dumps(setup.to_dict(name), allow_nan=False))
            self.assertEqual(metadata['name'], name)
            self.assertNotIn('image', metadata['board'])
            plotter = BoardPlotter2D.from_metadata(metadata, width_px=320)
            packet = dict(board_detected=True, markers=[dict(id=1, x=0, y=0, angle=90)],
                          balls=[dict(x=.02, y=.02)])
            self.assertFalse(np.array_equal(plotter.render_packet(packet), plotter.background))
            self.assertEqual(metadata['ball_detector'] is not None, setup.ball_detector is not None)

    def test_http_status_contains_setup_and_expires_vision(self):
        with tempfile.TemporaryDirectory() as directory:
            setup = VISION_SETUPS['setup_160cm'].to_dict('setup_160cm')
            state = dict(setup=setup, vision=dict(healthy=True, stream_id='session'))
            write_status(directory, state)
            server = serve_status(directory, '127.0.0.1', 0)
            try:
                url = f'http://127.0.0.1:{server.server_port}/api/v1/status'
                with urlopen(url, timeout=2) as response:
                    body = json.load(response)
                    self.assertEqual(response.status, 200)
                self.assertEqual(body['setup']['ball_detector']['radius_m'], .02)
                self.assertEqual(body['setup']['name'], 'setup_160cm')
                self.assertTrue(body['healthy'])
                target = Path(directory) / 'vision-status.json'
                state = json.loads(target.read_text())
                state['updated_at'] -= 10
                target.write_text(json.dumps(state))
                with self.assertRaises(HTTPError) as error:
                    urlopen(url, timeout=2)
                self.assertEqual(error.exception.code, 503)
                error.exception.close()
                mismatch = read_status(directory, dict(healthy=True, session='different'))
                self.assertFalse(mismatch['vision']['healthy'])
            finally:
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main()
