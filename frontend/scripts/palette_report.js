#!/usr/bin/env node
/**
 * palette_report — count the ways the UI bypasses its own design tokens.
 *
 * Measured 2026-09-28 before any cleanup: 21 Tailwind colour families in use
 * (five greys — gray 443, zinc 427, slate 211, neutral, stone; four greens —
 * emerald 951, green 447, teal, lime), 108 distinct hardcoded hex values across
 * 32 files, and 166 arbitrary-value colour classes.
 *
 * None of that shows yet, because the busy pages happen to agree with each
 * other. It will as soon as two of them disagree. The point of this script is
 * that the number is visible and can be driven down, rather than rediscovered
 * by eye every few months.
 *
 * The canonical colours are the semantic tokens, not a favourite Tailwind
 * family — see docs/design/palette.md. Run:  node scripts/palette_report.js
 * Exits non-zero only with --max-hex=<n> if distinct hex values exceed n.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', 'src');
const FAMILIES = ['slate','gray','zinc','neutral','stone','red','orange','amber','yellow','lime','green','emerald','teal','cyan','sky','blue','indigo','violet','purple','fuchsia','pink','rose'];
const GREYS = ['slate','gray','zinc','neutral','stone'];
const GREENS = ['green','emerald','teal','lime'];

const files = [];
(function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) { if (!/node_modules|__snapshots__/.test(e.name)) walk(p); }
    else if (/\.(jsx?|tsx?|css)$/.test(e.name) && !/\.test\./.test(e.name)) files.push(p);
  }
})(ROOT);

const famRe = new RegExp(`(?:bg|text|border|from|via|to|ring|fill|stroke)-(${FAMILIES.join('|')})-\\d{2,3}`, 'g');
const hexRe = /#[0-9a-fA-F]{3,8}\b/g;
const arbRe = /(?:bg|text|border|ring)-\[#[0-9a-fA-F]{3,8}\]/g;

const famCount = {}, hexSet = new Set();
let hexTotal = 0, arbTotal = 0, filesWithHex = 0;

for (const f of files) {
  const src = fs.readFileSync(f, 'utf8');
  for (const m of src.matchAll(famRe)) famCount[m[1]] = (famCount[m[1]] || 0) + 1;
  const hexes = src.match(hexRe) || [];
  if (hexes.length) filesWithHex++;
  hexTotal += hexes.length;
  hexes.forEach(h => hexSet.add(h.toLowerCase()));
  arbTotal += (src.match(arbRe) || []).length;
}

const sorted = Object.entries(famCount).sort((a, b) => b[1] - a[1]);
const sum = k => k.reduce((n, f) => n + (famCount[f] || 0), 0);

console.log('files scanned              :', files.length);
console.log('colour families in use     :', sorted.length, '(target: semantic tokens, so this trends down)');
console.log('distinct hardcoded hex     :', hexSet.size, `(${hexTotal} literals across ${filesWithHex} files)`);
console.log('arbitrary colour classes   :', arbTotal, '(bg-[#…] and friends)');
console.log('\ngrey families  :', GREYS.filter(g => famCount[g]).map(g => `${g} ${famCount[g]}`).join('  ') || 'none', `  total ${sum(GREYS)}`);
console.log('green families :', GREENS.filter(g => famCount[g]).map(g => `${g} ${famCount[g]}`).join('  ') || 'none', `  total ${sum(GREENS)}`);
console.log('\nall families, most used first:');
for (const [f, n] of sorted) console.log(`  ${f.padEnd(9)} ${n}`);

const arg = process.argv.find(a => a.startsWith('--max-hex='));
if (arg) {
  const max = Number(arg.split('=')[1]);
  if (hexSet.size > max) {
    console.error(`\nFAIL: ${hexSet.size} distinct hex values exceeds --max-hex=${max}`);
    process.exit(1);
  }
  console.log(`\nOK: ${hexSet.size} distinct hex values is within --max-hex=${max}`);
}
