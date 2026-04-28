def test_import():
    import nuvem_de_som  # noqa: F401
    from nuvem_de_som import SoundCloud  # noqa: F401


def test_version():
    from nuvem_de_som.version import __version__
    assert __version__
