# physical.ide — logo files

A complete set of SVG assets for The Physical IDE. All files are pure vector, transparent background (except the app icon), and use only the brand palette.

## Files

| File | Use |
|---|---|
| `physical-ide-logo.svg` | **Primary.** Horizontal lockup for light backgrounds. Use everywhere by default — slide headers, README, demo UI, pitch deck cover. |
| `physical-ide-logo-dark.svg` | Same lockup with white wordmark. Use on dark/black backgrounds — terminal-themed slides, the dark mode of your demo UI. |
| `physical-ide-logo-tagline.svg` | Adds "A COMPILER FOR HARDWARE" below the wordmark. Use for the pitch deck title slide, the README hero, and the demo video lower-third. |
| `physical-ide-stacked.svg` | Mark above wordmark. Use in square spaces — social posts, GitHub repo banner, square slide layouts. |
| `physical-ide-mark.svg` | The bracket-and-pin symbol alone. Use as a small accent, in the corner of slides, or as a section divider. |
| `physical-ide-app-icon.svg` | Orange rounded square with inverted white symbol. Use as favicon, GitHub avatar, Slack icon, app launcher icon. |

## Color palette

- **Orange** — `#FF5722`
- **Black** — `#0F0F0F`
- **White** — `#FFFFFF`
- **Mid gray (tagline only)** — `#666666`

## Notes

The wordmark uses a system font stack: Inter → Helvetica Neue → Helvetica → Arial → sans-serif. It renders correctly in every modern browser, slide tool, and design app. For print production or guaranteed pixel-identical rendering everywhere, open any of these SVGs in Figma or Illustrator and convert the text to outlines.

The center of the pin in the mark is **transparent**, not white. The brand color shows through whatever background you place the logo on. This means the same mark works on white, black, orange, photos — anywhere.

## Exporting to PNG

If you need raster versions, the fastest path is:
1. Open the SVG in a browser
2. Use a tool like CloudConvert, or
3. Drop it into Figma/Sketch/Illustrator and export at the size you need

For favicons: open `physical-ide-app-icon.svg` and export at 16×16, 32×32, 64×64, 180×180, 192×192, and 512×512.
