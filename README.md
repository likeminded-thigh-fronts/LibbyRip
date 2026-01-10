# LibbyRip

Rip your audiobooks from Libby. Powered by [FFmpeg.js](https://github.com/PsychedelicPalimpsest/FFmpeg-js).

![Exporting audiobook](imgs/export.png)
![Showing chapters](imgs/chapters.png)

> Warning: heavy use can get library cards banned. See issues [#14](https://github.com/PsychedelicPalimpsest/LibbyRip/issues/14), [#12](https://github.com/PsychedelicPalimpsest/LibbyRip/issues/12), and [#8](https://github.com/PsychedelicPalimpsest/LibbyRip/issues/8).

## Quick Start (Browser)
- Install [TamperMonkey](https://www.tampermonkey.net/).
- Install the userscript from [GreasyFork](https://greasyfork.org/en/scripts/498782-libregrab).
- Open your audiobook in Libby and export.
- If nothing appears in Chromium-based browsers, check TamperMonkey setup in their [FAQ](https://www.tampermonkey.net/faq.php#Q209).

<a href='https://ko-fi.com/V7V81BFLAH' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi6.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

**Requirements**
- Python 3.x; install deps with `pip install -r requirements.txt`.
- ffmpeg installed.
- macOS users: install Xcode audio toolbox to enable the AAC_AT codec (faster, better quality).

**What it does**
- Reads `metadata/metadata.json` from the audiobook folder.
- Embeds chapters and cover art into each part with `eyed3`.
- Sets ID3 tags (title, artist, album, track number).

**Notes**
- Audiobook folder must include `metadata/metadata.json` and cover art.
- Assumes files are named `Part X.mp3`.
- `Lame tag CRC check failed` can be ignored; shown in the GUI log.

## Convert to M4B (`libbyrip.py`)
End-to-end conversion to a single M4B with embedded chapters.

**Quick start**
```bash
python3 libbyrip.py "/path/to/audiobook/directory"
```
Steps performed:
1. Combine all `Part *.mp3` files into one MP3.
2. Pull chapter info from `metadata/metadata.json`.
3. Pull cover from `metadata/cover.JPG`
3. Convert to M4B with AAC audio and chapters.
4. Clean up temp files (unless told to keep).

**Common options**
```bash
# Use title from metadata
python3 libbyrip.py "$HOME/Downloads/Book Title"

# Custom output name
python3 libbyrip.py "$HOME/Downloads/Book Title" --output-name "CustomName"

# Keep intermediate files
python3 libbyrip.py "$HOME/Downloads/Book Title" --keep-temp
```

**Requirements**
- FFmpeg (e.g., `brew install ffmpeg` on macOS).
- Python 3.x.

**Verify install**
```bash
make install
```

## Note on EPUBs
The EPUB downloader is **unstable**, and **unreliable**. It works with a majority of books, however Libby does some processing to the xhtml before it is sent to the client, so that needs repaired, and this is not perfect, in addition I have no experience with the EPUB format. I am always open to contributions, so if you find an issue and want to fix it, please do.

---

**Disclaimer:** This tool is intended for educational and personal research purposes only. The developers do not condone illegal activity, including unauthorized distribution of copyrighted content. Use at your own risk and comply with all applicable laws.
