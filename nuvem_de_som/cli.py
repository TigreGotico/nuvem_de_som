"""nds — nuvem_de_som terminal client.

Browse and play SoundCloud from the terminal::

    nds search "nuclear chill"
    nds browse https://soundcloud.com/acidkid
    nds play   https://soundcloud.com/acidkid/piratech-nuclear-chill
    nds download https://soundcloud.com/acidkid/piratech-nuclear-chill
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Iterator, List, Optional

import click

from nuvem_de_som import SoundCloud, SoundCloudAPI, SoundCloudHTML, SoundCloudYTDLP

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BACKENDS = {
    "auto": SoundCloud,
    "api": SoundCloudAPI,
    "html": SoundCloudHTML,
    "ytdlp": SoundCloudYTDLP,
}

_PLAYERS = ["mpv", "vlc", "ffplay", "mplayer"]


def _player() -> Optional[str]:
    for p in _PLAYERS:
        if shutil.which(p):
            return p
    return None


def _fmt_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _print_tracks(tracks: List[dict], offset: int = 0) -> None:
    """Print a numbered track list."""
    width = shutil.get_terminal_size().columns
    for i, t in enumerate(tracks, start=offset + 1):
        dur = _fmt_duration(t.get("duration"))
        artist = t.get("artist") or ""
        title = t.get("title") or t.get("url", "")
        label = f"  {i:>3}. {title}"
        if artist:
            label += f"  [{artist}]"
        right = f"  {dur}"
        pad = width - len(label) - len(right)
        if pad > 0:
            label += " " * pad + right
        else:
            label += right
        click.echo(label)


def _print_people(people: List[dict], offset: int = 0) -> None:
    for i, p in enumerate(people, start=offset + 1):
        name = p.get("artist") or ""
        url = p.get("artist_url") or ""
        click.echo(f"  {i:>3}. {name}  <{url}>")


def _resolve_and_play(sc, track_url: str) -> None:
    player = _player()
    if not player:
        click.echo("No audio player found (install mpv, vlc, or ffplay).", err=True)
        return
    click.echo(f"Resolving stream …")
    try:
        if isinstance(sc, (SoundCloudHTML,)):
            # HTML backend can't stream — use API for resolution
            stream_url = SoundCloudAPI().resolve_stream(track_url)
        else:
            stream_url = sc.resolve_stream(track_url)
    except NotImplementedError:
        stream_url = SoundCloudAPI().resolve_stream(track_url)
    if not stream_url:
        click.echo("Could not resolve a stream URL.", err=True)
        return
    click.echo(f"Playing via {player} …")
    _player_cmd(player, stream_url)


def _player_cmd(player: str, url: str) -> None:
    args: List[str]
    if player == "mpv":
        args = ["mpv", "--no-video", "--really-quiet", url]
    elif player == "vlc":
        args = ["vlc", "--intf", "dummy", "--play-and-exit", url]
    elif player == "ffplay":
        args = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", url]
    else:
        args = [player, url]
    subprocess.run(args)


# ---------------------------------------------------------------------------
# Interactive session — used by search and browse
# ---------------------------------------------------------------------------

def _interactive_session(sc, tracks: List[dict], people: List[dict],
                         title: str) -> None:
    """Show results, let user pick tracks to play/download."""
    if not tracks and not people:
        click.echo("No results.")
        return

    click.echo(f"\n{title}")
    if people:
        click.echo("\nArtists:")
        _print_people(people)
    if tracks:
        click.echo("\nTracks:")
        _print_tracks(tracks)

    while True:
        click.echo()
        choice = click.prompt(
            "Enter track # to select, 'q' to quit",
            default="q",
            show_default=False,
        ).strip().lower()

        if choice in ("q", "quit", "exit", ""):
            break

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(tracks)):
                click.echo("Number out of range.")
                continue
        except ValueError:
            click.echo("Type a number or 'q'.")
            continue

        track = tracks[idx]
        click.echo(f"\n  {track['title']}  [{track.get('artist', '')}]  "
                   f"{_fmt_duration(track.get('duration'))}")
        click.echo("  [p]lay  [d]ownload  [b]ack")
        action = click.prompt("  Action", default="p", show_default=False).strip().lower()

        if action in ("p", "play"):
            _resolve_and_play(sc, track["url"])
        elif action in ("d", "download"):
            out = click.prompt("  Output dir", default=".", show_default=True)
            try:
                path = sc.download_track(track["url"], output_dir=out)
                click.echo(f"  Saved: {path}")
            except Exception as exc:
                click.echo(f"  Download failed: {exc}", err=True)
        # 'b' or anything else → back to list


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.group()
@click.option("--backend", "-b",
              type=click.Choice(list(BACKENDS)), default="auto", show_default=True,
              help="Which backend to use.")
@click.pass_context
def cli(ctx: click.Context, backend: str) -> None:
    """nds — browse and play SoundCloud from the terminal."""
    ctx.ensure_object(dict)
    ctx.obj["sc"] = BACKENDS[backend]()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=25, show_default=True, help="Max results.")
@click.option("--people", "mode", flag_value="people", help="Search artists.")
@click.option("--sets", "mode", flag_value="sets", help="Search playlists/sets.")
@click.option("--tracks", "mode", flag_value="tracks", default=True,
              help="Search tracks (default).")
@click.pass_context
def search(ctx: click.Context, query: str, limit: int, mode: str) -> None:
    """Search SoundCloud and browse results interactively."""
    sc = ctx.obj["sc"]

    if mode == "people":
        people = list(sc.search_people(query, limit=limit))
        _print_people(people)
        return

    if mode == "sets":
        sets = list(sc.search_sets(query, limit=limit))
        if not sets:
            click.echo("No sets found.")
            return
        for i, s in enumerate(sets, 1):
            click.echo(f"  {i:>3}. {s['title']}  [{s.get('artist', '')}]  <{s['url']}>")
        return

    click.echo(f"Searching for '{query}' …")
    tracks = list(sc.search_tracks(query, limit=limit))
    _interactive_session(sc, tracks, [], f"Results for '{query}'")


# ---------------------------------------------------------------------------
# browse
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("url")
@click.option("--limit", "-n", default=50, show_default=True,
              help="Max tracks to load.")
@click.pass_context
def browse(ctx: click.Context, url: str, limit: int) -> None:
    """Browse an artist or set page interactively."""
    sc = ctx.obj["sc"]
    click.echo(f"Loading {url} …")
    tracks = list(sc.get_tracks(url, limit=limit))
    _interactive_session(sc, tracks, [], url)


# ---------------------------------------------------------------------------
# play
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("url")
@click.pass_context
def play(ctx: click.Context, url: str) -> None:
    """Play a track URL directly."""
    sc = ctx.obj["sc"]
    _resolve_and_play(sc, url)


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("url")
@click.option("--output-dir", "-o", default=".", show_default=True,
              help="Directory to save the file.")
@click.option("--playlist", "-p", is_flag=True,
              help="Treat URL as artist/set page and download all tracks.")
@click.pass_context
def download(ctx: click.Context, url: str, output_dir: str, playlist: bool) -> None:
    """Download a track (or full playlist) to disk."""
    sc = ctx.obj["sc"]
    if playlist:
        click.echo(f"Downloading playlist {url} → {output_dir}")
        sc.download_playlist(url, output_dir=output_dir)
    else:
        click.echo(f"Downloading {url} → {output_dir}")
        path = sc.download_track(url, output_dir=output_dir)
        if path:
            click.echo(f"Saved: {path}")
        else:
            click.echo("Download failed.", err=True)
            sys.exit(1)


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
