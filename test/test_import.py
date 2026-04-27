def test_import():
    import nuvem_de_som
    from nuvem_de_som import SoundCloud


def test_version():
    from nuvem_de_som.version import __version__
    assert __version__
