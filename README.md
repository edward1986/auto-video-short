# Chess Shorts: Sound + YouTube

## Files
- `.github/workflows/generate-chess-video.yml` — GitHub Actions workflow
- `generate_chess_short.py` — chess render with original low-volume music, wooden move clicks, capture thumps, and check/checkmate chimes
- `upload_chess_youtube.py` — OAuth YouTube Shorts uploader
- `requirements-chess.txt` — Python requirements

## Setup
Copy **all files** into your GitHub repository's `Production` branch. Delete the older chess workflow **contents** rather than keeping two competing workflows.

Add GitHub Actions secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. OAuth refresh token must grant `youtube.upload` permission for the desired channel.

Under Actions, run **Generate Chess Video and Publish to YouTube**. Leave `publish=true`, `privacy=public`, or choose private/unlisted. Manual runs publish if requested. Push triggers only render the MP4, avoiding accidentally publishing on every code change.

The output is a vertical `720x1280` MP4 (9:16), with an AAC audio track and PGN game log. The workflow uploads files as Actions artifacts instead of committing large MP4s to Git.

### Privacy caveat
Some YouTube API projects are restricted to private uploads pending verification. OAuth authentication and API quotas must be valid. The uploader requests public visibility but YouTube ultimately controls the published status.

### Local test
```bash
sudo apt-get install ffmpeg stockfish libcairo2 fonts-dejavu-core
pip install -r requirements-chess.txt
python generate_chess_short.py --stockfish /usr/games/stockfish --moves 4 --seconds-per-move 1.65
```
