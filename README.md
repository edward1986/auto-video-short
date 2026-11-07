# Chess Shorts with randomized openings and YouTube upload

Replace the files in your GitHub repository on the Production branch.

- 16 legal opening sequences, cycling across successive GitHub runs.
- The engine chooses randomly among up to four strong legal moves after the opening.
- Modern vertical board, synthesized background music and move/check/capture sound effects.
- `chess_metadata.json` records the opening and is used for the YouTube title and description.
- Manual workflows use publish=true and privacy=public. Push triggers render only.
- YouTube secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.

Use the existing GitHub Action named Generate Chess Video and Publish to YouTube. Inspect its Publish step for the actual uploaded video URL.

No guarantee of globally unique games or 100% video upload reliability; opening selection is distinct across consecutive run numbers within each 16-run cycle.
