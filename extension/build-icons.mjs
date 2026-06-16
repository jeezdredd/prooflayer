import sharp from "sharp";
import { readFileSync } from "fs";

const svg = readFileSync("assets/icon.svg");
const sizes = [16, 32, 48, 128];

await Promise.all(
  sizes.map((size) =>
    sharp(svg)
      .resize(size, size)
      .png()
      .toFile(`assets/icon${size}.png`)
  )
);
