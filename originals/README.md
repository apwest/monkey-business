# originals/

Untouched copies of the Monte and Mortimer images as Woot originally shipped
them in the daily-digest emails. These files are **not deployed** to the public
site — they live here as an archival reference.

The production copies in `static/img/` were all transparified (white background
flood-filled to alpha=0 via `png_tools.py transparify`); the originals here
preserve the as-shipped opaque-background versions.

## File mapping

| Original (this folder) | Source URL                                                                                        | Production (`static/img/`)  | Transformations applied to production copy                                                                |
| ---------------------- | ------------------------------------------------------------------------------------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `mortimer-v1.png`      | `https://d2w0pyk7viytzg.cloudfront.net/monkey_left.png`                                           | `mortimer-v1.png`           | Flood-fill from all 4 corners (background fully white, character does not touch edges)                       |
| `monte-v1.png`         | `https://d2w0pyk7viytzg.cloudfront.net/monkey_right.png`                                          | `monte-v1.png`              | Flood-fill from all 4 corners                                                                                |
| `mortimer-v2-alt.png`  | `https://d3rqdbvvokrlbl.cloudfront.net/images/email/monkey-left.2.png`                            | `mortimer-v2-alt.png`       | Flood-fill from all 4 corners                                                                                |
| `monte-v2-alt.png`     | `https://d3rqdbvvokrlbl.cloudfront.net/images/email/monkey-right.2.png`                           | `monte-v2-alt.png`          | Flood-fill from all 4 corners                                                                                |
| `mortimer-v3.png`      | `http://g-ec2.images-amazon.com/images/G/01/woot/emails/acquisition/mortimer-2.png` (also seen via Gmail proxy) | `mortimer-v3.png`           | Flood-fill from **top corners only** (`TL,TR`) — character touches the bottom edge of the frame             |
| `monte-v3.png`         | `http://g-ec2.images-amazon.com/images/G/01/woot/emails/acquisition/monte-2.png`                  | `monte-v3.png`              | Flood-fill from **top corners only** (`TL,TR`)                                                              |

## Style → file mapping in the build

`build.py` picks the production image pair based on each clip's `style` field
in `data/clips.jsonl`:

| Style    | Date range in archive    | Mortimer image           | Monte image           | Clip count |
| -------- | ------------------------ | ------------------------ | --------------------- | ---------- |
| `v1`     | 2011-07-04 – 2015-11-19  | `mortimer-v1.png`        | `monte-v1.png`        | 1,537      |
| `v2`     | 2015-11-20 – 2015-12-23  | `mortimer-v2-alt.png` ¹  | `monte-v2-alt.png` ¹  | 34         |
| `v2-alt` | 2015-12-24 – 2017-09-28  | `mortimer-v2-alt.png`    | `monte-v2-alt.png`    | 628        |
| `v3`     | 2017-09-20 – present     | `mortimer-v3.png`        | `monte-v3.png`        | 2,528      |

¹ The actual v2 originals (`monkey-left.png` / `monkey-right.png`, no `.2`
suffix) 404 at the CDN with no Wayback Machine snapshot. The build falls back
to the v2-alt images, which are the literal `.2.png` refresh of the same era —
almost certainly the same illustration visually. See [build.py](../build.py)
`STYLE_IMAGES`.

## Regenerating the production copies

If a production image is ever lost or needs to be re-transparified:

```bash
# Restore from this folder
cp originals/<name>.png static/img/<name>.png

# Re-apply the transformation
python png_tools.py transparify static/img/<name>.png            # v1 / v2-alt
python png_tools.py transparify --corners TL,TR static/img/<name>.png  # v3
```
