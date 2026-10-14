import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../src/", import.meta.url).pathname;
const dict = JSON.parse(readFileSync(join(root, "i18n/ru.json"), "utf8"));
const STR = String.raw`"((?:[^"\\]|\\.)*)"`;
const T_CALL = new RegExp(String.raw`\b(?:t|msg)\(\s*` + STR, "g");
const TN_CALL = new RegExp(String.raw`\btn\([^,]+,\s*` + STR + String.raw`\s*,\s*` + STR, "g");

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.tsx?$/.test(name) && !name.endsWith(".d.ts") ? [path] : [];
  });
}

function unescape(raw) {
  return JSON.parse(`"${raw}"`);
}

const missing = [];
const used = new Set();
for (const path of files(root)) {
  const source = readFileSync(path, "utf8");
  for (const m of source.matchAll(T_CALL)) {
    const key = unescape(m[1]);
    used.add(key);
    if (!(key in dict.strings)) missing.push(`${relative(root, path)}: t ${JSON.stringify(key)}`);
  }
  for (const m of source.matchAll(TN_CALL)) {
    const key = unescape(m[2]);
    used.add(key);
    const forms = dict.plural[key];
    if (!Array.isArray(forms) || forms.length !== 3) missing.push(`${relative(root, path)}: tn ${JSON.stringify(key)}`);
  }
}

const unused = [...Object.keys(dict.strings), ...Object.keys(dict.plural)].filter((k) => !used.has(k));
if (process.argv.includes("--unused")) unused.forEach((k) => console.log(`unused: ${JSON.stringify(k)}`));
if (process.argv.includes("--json")) {
  const keys = [...new Set(missing.map((line) => line.slice(line.indexOf(" ") + 1)))];
  console.log(JSON.stringify(keys, null, 1));
} else {
  missing.forEach((line) => console.log(`missing ${line}`));
}
console.log(`${used.size} keys used, ${missing.length} missing, ${unused.length} unused`);
process.exit(missing.length ? 1 : 0);
