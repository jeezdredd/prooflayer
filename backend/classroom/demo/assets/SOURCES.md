# Demo asset sources

Files not listed here are built from the texts in `demo_data.json` by `scripts/build_demo_assets.py`.

## anna_petropavlovskaya_krepost.jpg

- What it shows: the Peter and Paul Fortress in Saint Petersburg (Anna's photo from a summer trip, the authentic control picture).
- Source: Wikimedia Commons, "Петропавловская крепость. Санкт-Петербург 20.08.2025.jpg",
  https://commons.wikimedia.org/wiki/File:Петропавловская_крепость._Санкт-Петербург_20.08.2025.jpg
- Author: SmallSonMarex (Wikimedia Commons user), own work.
- Licence: CC0 1.0 (public domain dedication), https://creativecommons.org/publicdomain/zero/1.0/
- The file is the original upload, unchanged (SHA-1 5f1f6eb47f5aecc100ad61b20e42ab795c58d901), so the camera EXIF
  (Panasonic DMC-FZ18, 2025-08-20 18:44) is kept.

## polina_risunok_zimnyaya_derevnya.png

- What it shows: a snowy village street in watercolour (Polina hands it in as her own drawing).
- Source: DiffusionDB (poloclub/diffusiondb, large part 1, image 88a8239e-1df6-48c2-928f-a88abded0ca5), generated with
  Stable Diffusion 1.x from the prompt "abstract watercolor painting of village, magic diamond crystal winter, cinematic
  light, national romanticism by anders zorn, by greg rutkowski, by greg manchess".
- Licence: CC0 1.0 (DiffusionDB is released under CC0), https://creativecommons.org/publicdomain/zero/1.0/
- Changes: the Stable Diffusion 1.x invisible watermark ("StableDiffusionV1", the DWT max-coefficient scheme of the
  invisible-watermark library that the reference SD 1.x scripts apply) was embedded in the U and V channels, the picture
  was then re-saved as JPEG at quality 80 with 4:4:4 chroma and stored as PNG. `analyzers.watermarks.find_known_watermark`
  reads it as Stable Diffusion 1.x, 136 bits, match 0.846, state "damaged", so the metadata check reports a damaged AI
  trace.

## foto_ekskursiya_usadba.png

- Olga's "photo from a costumed excursion": an AI picture carrying an intact Stable Diffusion XL watermark (added
  2026-10-17).
