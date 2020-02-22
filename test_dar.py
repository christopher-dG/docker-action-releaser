from unittest.mock import patch

import dar


@patch("sys.exit")
def test_ignore(exit):
    dar.ignore("good")
    exit.assert_called_with(0)
    dar.ignore("bad", 2)
    exit.assert_called_with(2)
