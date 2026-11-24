/**
 * 扫描 images/landscape/ 与 images/portrait/ 目录，生成 Functions 使用的图片清单。
 *
 * 用法：
 *   node scripts/generate-manifest.mjs
 *
 * 每次新增/删除图片后重新运行一次即可。Cloudflare Pages Functions 运行在
 * Edge 环境，无法直接读取文件系统，所以图片路径需要预先写进清单文件。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');

const IMAGE_EXTS = new Set([
  '.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.bmp', '.svg',
]);

function listImages(dirName) {
  const relDir = `images/${dirName}`;
  const dir = path.join(root, relDir);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && IMAGE_EXTS.has(path.extname(entry.name).toLowerCase()))
    .map((entry) => `${relDir}/${entry.name}`)
    // 数字自然排序：1.webp、2.webp … 11.webp（而非字符串序 1、10、100）
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

const landscape = listImages('landscape');
const portrait = listImages('portrait');
const all = [...landscape, ...portrait];

if (all.length === 0) {
  console.error('未找到任何图片，请检查 images/landscape/ 与 images/portrait/ 目录。');
  process.exit(1);
}

const banner = '// 本文件由 scripts/generate-manifest.mjs 自动生成，请勿手动修改。\n';
const content = [
  banner,
  `export const LANDSCAPE = ${JSON.stringify(landscape)};\n`,
  '\n',
  `export const PORTRAIT = ${JSON.stringify(portrait)};\n`,
  '\n',
  `export const ALL = ${JSON.stringify(all)};\n`,
  '\n',
  `export const COUNT = ${JSON.stringify({
    landscape: landscape.length,
    portrait: portrait.length,
    total: all.length,
  })};\n`,
].join('');

const outFile = path.join(root, 'functions', '_lib', 'manifest.js');
fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, content, 'utf8');

console.log(`已生成 ${path.relative(root, outFile)}`);
console.log(`横屏 ${landscape.length} 张，竖屏 ${portrait.length} 张，共 ${all.length} 张`);
